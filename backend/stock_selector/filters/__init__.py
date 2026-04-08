"""
股票筛选过滤器

提供多层过滤能力：
- BlacklistFilter: 黑名单过滤
- ManualListFilter: 手动白名单/黑名单管理
- AdmissionFilter: 准入条件过滤（递进式门槛）

设计文档: docs/plans/STOCK_SELECTOR_ARCHITECTURE.md v19.5.3
"""

from .blacklist import BlacklistFilter
from .manual_list import ManualListFilter
from .admission import AdmissionFilter

__all__ = [
    "BlacklistFilter",
    "ManualListFilter",
    "AdmissionFilter",
]
