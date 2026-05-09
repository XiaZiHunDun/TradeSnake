#!/usr/bin/env python3
"""
Sync CI test failures to module ISSUES.md files.

Usage:
    python scripts/sync_errors_to_issues.py --report report.json
    python scripts/sync_errors_to_issues.py --module-prefix backend -- pytest output.txt

The script parses test failure output and updates the corresponding
docs/plans/{module}/ISSUES.md files.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


# Mapping from test file paths to module names
FILE_TO_MODULE = {
    # backend/tests/ -> various modules (test files directly test those modules)
    "backend/tests/test_cp_engine": "engine/cp_engine",
    "backend/tests/test_fusion": "recommender",
    "backend/tests/test_history": "engine/cp_engine",
    "backend/tests/test_ml_model": "ml",
    "backend/tests/test_momentum_enhanced": "engine/cp_engine",
    "backend/tests/test_prediction_engines": "engine/gain_predictor",
    "backend/tests/test_risk_manager": "risk",
    # backend/tests/test_router_*.py -> api module
    "backend/tests/test_router_": "api",
    "backend/tests/test_routes": "api",
    # backend/data_manager tests
    "backend/data_manager": "data_manager",
    # engine submodules
    "backend/engine/cp_engine": "engine/cp_engine",
    "backend/engine/gain_predictor": "engine/gain_predictor",
    "backend/engine/probability_predictor": "engine/probability_predictor",
    # top-level modules
    "backend/recommender": "recommender",
    "backend/backtester": "backtester",
    "backend/simulator": "simulator",
    "backend/api": "api",
    "backend/ml": "ml",
    "backend/risk": "risk",
    # tests/ directory (top-level integration tests)
    "tests/backtester": "backtester",
    "tests/test_simulator": "simulator",
}

ISSUES_DIR = Path("docs/plans")
TODAY = datetime.now().strftime("%Y-%m-%d")


def extract_module_from_path(file_path: str) -> Optional[str]:
    """Extract module name from test file path."""
    normalized = file_path.replace("\\", "/")
    for prefix, module in FILE_TO_MODULE.items():
        if prefix in normalized:
            return module
    return None


def parse_pytest_json(report_path: str) -> list[dict]:
    """Parse pytest JSON report."""
    with open(report_path, "r") as f:
        report = json.load(f)

    failures = []
    for test in report.get("report", {}).get("tests", []):
        if test.get("outcome") == "failed":
            # Extract file path and line number from test nodeid
            nodeid = test.get("nodeid", "")
            # nodeid format: path/to/test.py::TestClass::test_name or path/to/test.py:123
            # First split off any ::class::method suffix
            if "::" in nodeid:
                file_with_suffix = nodeid.split("::")[0]
            else:
                file_with_suffix = nodeid

            # Then extract line number (digits after final colon before non-colon)
            match = re.search(r":(\d+)(?!:)", file_with_suffix)
            if match:
                file_path = file_with_suffix.rsplit(":", 1)[0]
                line_no = match.group(1)
            else:
                file_path = file_with_suffix
                line_no = "?"

            module = extract_module_from_path(file_path)
            if module:
                failures.append({
                    "file": file_path,
                    "line": line_no,
                    "module": module,
                    "test": test.get("name", ""),
                    "message": test.get("call", {}).get("longrepr", "Unknown error"),
                })
    return failures


def parse_pytest_output(output_text: str) -> list[dict]:
    """Parse pytest plain text output."""
    failures = []
    # Pattern: FAILED path::test_name - message
    pattern = r"FAILED\s+([^\s:]+):(\d+)\s*::\s*([^\s-]+)\s*-?\s*(.*)"
    for match in re.finditer(pattern, output_text):
        file_path, line_no, test_name, message = match.groups()
        module = extract_module_from_path(file_path)
        if module:
            failures.append({
                "file": file_path,
                "line": line_no,
                "module": module,
                "test": test_name,
                "message": message.strip() if message else "Unknown error",
            })
    return failures


def get_issues_path(module: str) -> Path:
    """Get path to ISSUES.md for a module."""
    return ISSUES_DIR / module / "ISSUES.md"


def issue_key(entry: dict) -> str:
    """Generate a unique key for an issue entry."""
    return f"{entry['file']}:{entry['line']}"


def read_existing_issues(issues_path: Path) -> tuple[list[str], set[str]]:
    """Read existing issues file and extract issue keys.

    Returns:
        Tuple of (all_lines, existing_keys set)
    """
    if not issues_path.exists():
        return [], set()

    with open(issues_path, "r") as f:
        content = f.read()

    lines = content.splitlines()

    # Find table rows (starting with |)
    existing_keys = set()
    # Match: | date | problem | status | fix |
    # We want the problem column (2nd data column)
    key_pattern = re.compile(r"\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*([^\|]+?)\s*\|")

    for line in lines:
        match = key_pattern.match(line.strip())
        if match:
            date, problem = match.groups()
            # Extract file:line from problem if present
            key_match = re.search(r"(\[.*?\]|.*?:\d+)", problem)
            if key_match:
                # Remove brackets for consistent key format
                key = key_match.group(1).strip("[]")
                existing_keys.add(key)

    return lines, existing_keys


def truncate_message(message: str, max_len: int = 100) -> str:
    """Truncate message to fit in the table."""
    # Remove newlines and extra spaces
    message = re.sub(r"\s+", " ", message).strip()
    if len(message) > max_len:
        return message[:max_len - 3] + "..."
    return message


def format_issue_entry(failure: dict) -> str:
    """Format a failure as an ISSUES.md table row."""
    # Format: | date | [file:line] test_name: message | status | fix_note |
    file_line = f"[{failure['file']}:{failure['line']}]"
    test_name = failure.get("test", "unknown")
    message = truncate_message(failure.get("message", ""))

    return f"| {TODAY} | {file_line} {test_name}: {message} | 待调查 | - |"


def update_issues_file(issues_path: Path, failures: list[dict]) -> int:
    """Update ISSUES.md with new failure entries.

    Returns number of new entries added.
    """
    if not failures:
        return 0

    existing_lines, existing_keys = read_existing_issues(issues_path)

    # Group failures by module
    new_entries = []
    seen_keys = set()

    for failure in failures:
        key = issue_key(failure)
        if key not in existing_keys and key not in seen_keys:
            new_entries.append(failure)
            seen_keys.add(key)

    if not new_entries:
        return 0

    # Find insertion point (after the format header section)
    # Priority: marker > "## 已知限制" > end of file
    insert_idx = None
    marker_idx = None

    for i, line in enumerate(existing_lines):
        if "<!-- 在此下方添加历史问题记录 -->" in line:
            marker_idx = i + 1
            break

    if marker_idx is not None:
        insert_idx = marker_idx
    else:
        # Look for "## 已知限制" or similar section markers
        # Insert before any new section markers after "## 问题追踪"
        section_markers = ["## 已知限制", "## P2", "## Walk-Forward", "## 已解决问题", "## 验证结果", "## Kelly", "## Alpha"]
        after_problem_tracking = False
        for i, line in enumerate(existing_lines):
            if "## 问题追踪" in line:
                after_problem_tracking = True
                continue
            if after_problem_tracking and any(line.strip().startswith(m) for m in section_markers):
                insert_idx = i
                break

        # Default: append to end of file
        if insert_idx is None:
            insert_idx = len(existing_lines)

    # Build new entries
    new_lines = [format_issue_entry(f) for f in new_entries]

    # Merge
    result_lines = existing_lines[:insert_idx] + new_lines + [""] + existing_lines[insert_idx:]

    # Ensure directory exists
    issues_path.parent.mkdir(parents=True, exist_ok=True)

    with open(issues_path, "w") as f:
        f.write("\n".join(result_lines))

    return len(new_entries)


def main():
    parser = argparse.ArgumentParser(description="Sync CI failures to ISSUES.md")
    parser.add_argument("--module-prefix", default="backend",
                        help="Module prefix for file-to-module mapping")
    parser.add_argument("--report", help="Path to pytest JSON report")
    parser.add_argument("--output", help="Path to pytest output file (txt)")
    args = parser.parse_args()

    failures = []

    if args.report:
        failures.extend(parse_pytest_json(args.report))

    if args.output:
        with open(args.output, "r") as f:
            failures.extend(parse_pytest_output(f.read()))

    # If no specific files, read from stdin
    if not args.report and not args.output:
        failures.extend(parse_pytest_output(sys.stdin.read()))

    # Group by module
    by_module: dict[str, list[dict]] = {}
    for f in failures:
        module = f.get("module")
        if module:
            by_module.setdefault(module, []).append(f)

    # Update each module's ISSUES.md
    total_added = 0
    for module, module_failures in by_module.items():
        issues_path = get_issues_path(module)
        added = update_issues_file(issues_path, module_failures)
        if added > 0:
            print(f"Added {added} entries to {issues_path}")
            total_added += added

    if total_added == 0:
        print("No new issues to add.")
    else:
        print(f"Total: {total_added} entries added to ISSUES.md files.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
