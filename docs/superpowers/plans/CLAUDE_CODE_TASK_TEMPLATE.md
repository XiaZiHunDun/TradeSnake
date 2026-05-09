# Claude Code Task Template

> Use this template for TradeSnake tasks executed by Claude Code.  
> Copy this file into `docs/superpowers/plans/YYYY-MM-DD-<topic>-implementation.md`, then replace the template text with task-specific content.

---

## For Claude Code

You are executing a TradeSnake task designed by the Cursor planning/review agent.

Your default behavior:

- Work continuously within the task scope.
- Make routine engineering decisions yourself.
- Preserve user changes and avoid unrelated rewrites.
- Verify your work before reporting completion.
- Stop only when a stop condition is met.

Do not ask the user for decisions about small implementation details. Use existing project patterns, choose the smallest safe change, and keep going.

---

## Goal

Describe the exact outcome expected from this task.

Acceptance criteria:

- The task has a concrete, reviewable result.
- The result can be verified by commands, tests, file checks, or documented evidence.
- Any remaining risk is explicitly reported.

---

## Context

Relevant project facts:

- Backend: FastAPI under `backend/`.
- Frontend: React + Vite under `frontend/`.
- Main project facts are tracked in `docs/superpowers/plans/PROJECT_FACT_BASE.md`.
- Design and execution documents live under `docs/superpowers/specs` and `docs/superpowers/plans`.

Fact-source priority:

1. Current code and passing tests.
2. Latest dated `docs/superpowers/specs` and `docs/superpowers/plans`.
3. `docs/plans/PROJECT_OVERVIEW.md` and module architecture docs.
4. Root `README.md`.
5. Older references and review documents.

If facts conflict, continue with the highest-priority source that makes the task executable, then report the conflict.

---

## Scope

Allowed changes:

- List files or directories Claude Code may create or modify.
- Include tests and docs that must be updated.

Out of scope:

- List files, modules, or behaviors Claude Code must not change.
- Explicitly exclude unrelated cleanup and broad refactors.

---

## Autonomy

Claude Code may decide these independently:

- Local code structure that follows existing patterns.
- Names for helper functions, tests, fixtures, or small files.
- Focused fixes needed to make the task pass verification.
- Documentation wording that preserves the approved meaning.
- Whether to add narrow tests for behavior touched by this task.

Claude Code must prefer:

- Minimal, reviewable changes.
- Existing module boundaries and helper APIs.
- Tests close to the changed behavior.
- Clear reporting of assumptions and conflicts.

---

## Stop Conditions

Stop and ask the user before proceeding if any of these occur:

- The task requires changing product scope, stock universe, trading rules, CP formula, data-source priority, or backtest evaluation policy.
- The task requires credentials, paid APIs, new infrastructure, external services, or deployment changes.
- The task requires deleting data, migrating persisted formats, or breaking existing public API contracts.
- The task conflicts with user changes in a way that cannot be safely merged.
- Baseline tests fail broadly and the cause cannot be isolated.
- A destructive git command would be needed.

Do not stop for routine implementation choices.

---

## Files

Create:

- List every new file and the reason it is needed.

Modify:

- List every existing file and the reason it is in scope.

Do not modify:

- List protected files or directories and why they are out of scope.

---

## Steps

### Task 1: Prepare

- [ ] Read this task file completely.
- [ ] Check `git status --short` and identify existing user changes.
- [ ] Read the relevant files listed in the Context and Files sections.
- [ ] Record any fact conflicts that affect implementation.

### Task 2: Implement

- [ ] Make the smallest changes that satisfy the Goal.
- [ ] Follow the Scope and Autonomy rules.
- [ ] Add or update focused tests if behavior changes.
- [ ] Update docs only when they are part of the task or needed to remove direct contradictions.

### Task 3: Verify

- [ ] Run the required verification commands.
- [ ] If a command cannot run, record the exact reason.
- [ ] Fix failures caused by this task and rerun verification.
- [ ] Do not claim success without evidence.

### Task 4: Report

- [ ] Summarize files changed.
- [ ] Summarize verification commands and results.
- [ ] List remaining risks or known pre-existing issues.
- [ ] Suggest the next best task if applicable.

---

## Verification

Choose commands that match the task:

```bash
# Backend focused tests
python -m pytest backend/tests/<test_file>.py -v

# Backtester focused tests
python -m pytest tests/backtester/<test_file>.py -v

# Backend broader tests
python -m pytest backend/tests/ -v

# Frontend build
cd frontend && npm run build
```

For documentation-only tasks, use checks such as:

```bash
rg -n "TO""DO|TB""D|PLACE""HOLDER|待补""充" docs/superpowers
test -f docs/superpowers/plans/PROJECT_FACT_BASE.md
```

Use the narrowest useful verification first, then broaden if the task touches shared behavior.

---

## Completion Report Format

Use this format when reporting completion:

```markdown
## Summary
- State what changed and why.

## Verification
- `<command>`: pass, fail, or not run with reason.

## Existing Issues Or Risks
- List pre-existing issues, unresolved risks, or state "None identified".

## Next Task Recommendation
- Recommend one concrete next task.
```

Keep the report factual and concise.
