"""
股票代码标准化工具

功能：
- 统一股票代码格式（6位数字）
- 识别市场（沪市/深市/创业板/科创板）
- 验证代码有效性

示例：
- SH600519 -> 600519
- sz000001 -> 000001
- 1 -> 000001
"""

import re
from typing import Optional, Tuple


class CodeNormalizer:
    """
    股票代码标准化器
    """

    # 市场后缀映射
    MARKET_SUFFIXES = {
        "sh": "沪市",
        "sz": "深市",
        "bj": "北交所",  # 北京证券交易所
    }

    # 交易所代码前缀
    EXCHANGE_PREFIXES = {
        "6": "沪市",   # 600-688 沪市主板/科创板
        "0": "深市",   # 000 深市主板
        "1": "深市",   # 001 深圳A股
        "2": "深市",   # 002 创业板
        "3": "深市",   # 003 深圳A股
        "8": "北交所",  # 830/870 北交所
        "4": "北交所",  # 430/830 北交所
    }

    def __init__(self):
        pass

    def normalize(self, code: str) -> str:
        """
        标准化股票代码

        Args:
            code: 原始代码，可能带后缀

        Returns:
            6位数字字符串
        """
        return normalize_code(code)

    def get_market(self, code: str) -> str:
        """
        获取股票市场

        Returns:
            "沪市" | "深市" | "北交所" | "未知"
        """
        code = self.normalize(code)
        if not code:
            return "未知"

        first_digit = code[0]
        return self.EXCHANGE_PREFIXES.get(first_digit, "未知")

    def is_valid(self, code: str) -> bool:
        """
        检查代码是否有效

        Returns:
            是否有效
        """
        return is_valid_code(code)

    def split_code_suffix(self, code: str) -> Tuple[str, Optional[str]]:
        """
        分离代码和后缀

        Returns:
            (code, suffix)
        """
        code = code.lower()

        # 匹配后缀
        match = re.match(r"^(\d{6})\.(sh|sz|bj)?$", code)
        if match:
            return match.group(1), match.group(2)

        # 没有后缀
        return normalize_code(code), None

    def build_with_suffix(self, code: str, suffix: Optional[str] = None) -> str:
        """
        构建带后缀的代码

        Args:
            code: 6位代码
            suffix: 市场后缀（sh/sz/bj），如果为None则自动判断

        Returns:
            如 "600519.sh"
        """
        code = self.normalize(code)

        if suffix is None:
            market = self.get_market(code)
            suffix_map = {"沪市": "sh", "深市": "sz", "北交所": "bj"}
            suffix = suffix_map.get(market, "sz")

        return f"{code}.{suffix}"


def normalize_code(code: str) -> str:
    """
    标准化股票代码为6位数字

    Args:
        code: 原始代码

    Returns:
        6位数字字符串

    Examples:
        >>> normalize_code("600519")
        '600519'
        >>> normalize_code("1")
        '000001'
        >>> normalize_code("sh600519")
        '600519'
        >>> normalize_code("000001.sz")
        '000001'
    """
    if not code:
        return ""

    # 移除空白
    code = code.strip()

    # 移除后缀（.sh/.sz/.bj等）
    if "." in code:
        code = code.split(".")[0]

    # 移除前导标记（sh/sz等）
    if code.lower() in ("sh", "sz", "bj"):
        return ""

    # 只保留数字
    code = re.sub(r"\D", "", code)

    if not code:
        return ""

    # 补齐到6位
    return code.zfill(6)


def is_valid_code(code: str) -> bool:
    """
    检查是否是有效的A股代码

    Args:
        code: 股票代码

    Returns:
        是否有效

    有效前缀：
    - 600-688: 沪市主板/科创板
    - 000: 深市主板
    - 001: 深圳A股
    - 002: 创业板
    - 003: 深圳A股
    - 300: 创业板
    - 430/830/870: 北交所
    """
    code = normalize_code(code)

    if len(code) != 6:
        return False

    # 检查前缀
    valid_prefixes = (
        "000",   # 深市主板
        "001",   # 深圳A股
        "002",   # 创业板
        "003",   # 深圳A股
        "300",   # 创业板
        "600",   # 沪市主板
        "601",   # 沪市主板
        "603",   # 沪市主板
        "605",   # 沪市主板
        "688",   # 科创板
        "430",   # 北交所
        "830",   # 北交所
        "870",   # 北交所
    )

    return any(code.startswith(p) for p in valid_prefixes)


def get_market(code: str) -> str:
    """
    判断股票市场

    Args:
        code: 股票代码

    Returns:
        "沪市" | "深市" | "北交所" | "未知"
    """
    code = normalize_code(code)

    if not code:
        return "未知"

    market_map = {
        "6": "沪市",    # 600-688
        "0": "深市",    # 000-003
        "2": "深市",    # 002 创业板
        "3": "深市",    # 300 创业板
        "4": "北交所",  # 北交所
        "8": "北交所",  # 北交所
    }

    first = code[0]
    return market_map.get(first, "未知")


def is_shanghai(code: str) -> bool:
    """是否沪市"""
    return get_market(code) == "沪市"


def is_shenzhen(code: str) -> bool:
    """是否深市"""
    return get_market(code) == "深市"


def is_bj(code: str) -> bool:
    """是否北交所"""
    return get_market(code) == "北交所"
