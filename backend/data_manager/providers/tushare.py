"""
Tushare数据源提供者
====================
使用Tushare Pro API获取数据

配置:
    - Token: d1548397f09fdff5c3a356326f018c0d8f84691ef94415735c33fc4a
    - 积分: 2000点 (200次/分钟)
    - 代理: http://192.168.13.218:10808

可用接口:
    - pro.daily() - 日线数据
    - pro.stock_basic() - 股票列表
    - pro.income() - 利润表
    - pro.balancesheet() - 资产负债表
    - pro.cashflow() - 现金流量表
    - pro.daily_basic() - 每日指标
"""

import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any

# 设置代理
os.environ['http_proxy'] = 'http://192.168.13.218:10808'
os.environ['https_proxy'] = 'http://192.168.13.218:10808'

import tushare as ts

from .base import BaseDataProvider, ProviderConfig
from ..circuit_breaker import get_circuit_manager, TushareBudgetExhaustedError


# Tushare积分接口消耗
INTERFACE_COSTS = {
    'stock_basic': 0,       # 基础数据，0积分
    'daily': 5,             # 日线行情，5积分/次
    'daily_basic': 100,     # 每日指标，100积分
    'income': 300,         # 利润表，300积分
    'balancesheet': 300,   # 资产负债表，300积分
    'cashflow': 300,       # 现金流量表，300积分
    'fina_indicator': 500, # 财务指标，500积分
    'moneyflow': 200,      # 资金流向，200积分
}


class TushareProvider(BaseDataProvider):
    """
    Tushare数据源提供者

    使用Tushare Pro API获取:
    - 股票列表
    - 日K线数据
    - 财务数据（利润表、资产负债表、现金流量表）
    """

    # 使用正确的Token
    TOKEN = '0c754ce86eb55d62047cb390339cb33231e57fda7c8093b146264ce0'

    def __init__(self, config: Optional[ProviderConfig] = None):
        super().__init__(config or ProviderConfig(
            name='tushare',
            enabled=True,
            priority=50,  # Tushare优先级较高
            timeout=30.0
        ))

        self._pro = None
        self._init_session()
        self._budget = get_circuit_manager()._tushare_budget
        self._stats = {
            'total_calls': 0,
            'success_calls': 0,
            'failed_calls': 0,
            'points_used': 0,
        }

    def _init_session(self):
        """初始化Tushare会话"""
        try:
            ts.set_token(self.TOKEN)
            self._pro = ts.pro_api()
        except Exception as e:
            print(f"Tushare会话初始化失败: {e}")
            self._pro = None

    @property
    def pro(self):
        """获取pro API实例"""
        if self._pro is None:
            self._init_session()
        return self._pro

    def _call_with_budget(self, interface: str, func, *args, **kwargs) -> Any:
        """
        带预算检查的调用

        Args:
            interface: 接口名称
            func: 要调用的函数
            *args, **kwargs: 函数参数

        Returns:
            函数返回值

        Raises:
            TushareBudgetExhaustedError: 积分不足时抛出
        """
        cost = INTERFACE_COSTS.get(interface, 100)

        # 检查预算
        if not self._budget.check_and_use(interface):
            raise TushareBudgetExhaustedError(
                f"Tushare积分不足，接口 {interface} 需要 {cost} 积分"
            )

        self._stats['total_calls'] += 1

        try:
            result = func(*args, **kwargs)
            self._stats['success_calls'] += 1
            self._stats['points_used'] += cost
            return result
        except Exception as e:
            self._stats['failed_calls'] += 1
            raise

    def get_stock_list(self, force_refresh: bool = False) -> List[Dict]:
        """
        获取股票列表

        Returns:
            股票列表，每只股票包含:
            - ts_code: Tushare代码 (e.g., 000001.SZ)
            - symbol: 股票代码 (e.g., 000001)
            - name: 股票名称
            - area: 地域
            - industry: 行业
            - market: 市场 (主板/科创板/创业板)
        """
        if self.pro is None:
            return []

        try:
            # 不带过滤参数以确保返回数据
            df = self.pro.stock_basic(
                fields='ts_code,symbol,name,area,industry,market,list_date'
            )

            if df is None or len(df) == 0:
                return []

            return df.to_dict('records')

        except Exception as e:
            print(f"获取Tushare股票列表失败: {e}")
            return []

    def get_market_data(self, codes: List[str]) -> List[Dict]:
        """
        获取实时行情（通过Tushare每日指标）

        注意: Tushare不提供真正的实时行情，此方法返回最近交易日的每日指标

        Args:
            codes: 股票代码列表

        Returns:
            行情数据列表
        """
        if self.pro is None or not codes:
            return []

        results = []
        today = datetime.now().strftime('%Y%m%d')

        for code in codes:
            try:
                # 转换代码格式
                ts_code = self._to_ts_code(code)
                if not ts_code:
                    continue

                # 获取每日指标
                df = self.pro.daily_basic(
                    ts_code=ts_code,
                    trade_date=today,
                    fields='ts_code,close,turnover_rate,pe,pb,ps,mktcap,circ_mktcap'
                )

                if df is not None and len(df) > 0:
                    row = df.iloc[0]
                    results.append({
                        'code': code,
                        'ts_code': row['ts_code'],
                        'close': row.get('close', 0),
                        'turnover_rate': row.get('turnover_rate', 0),
                        'pe': row.get('pe', 0),
                        'pb': row.get('pb', 0),
                        'ps': row.get('ps', 0),
                        'mktcap': row.get('mktcap', 0),
                        'circ_mktcap': row.get('circ_mktcap', 0),
                    })

            except Exception as e:
                print(f"获取 {code} 行情失败: {e}")
                continue

            time.sleep(0.06)  # 避免超过120次/分钟限制

        return results

    def get_daily_kline(
        self,
        code: str,
        start_date: str,
        end_date: str,
        asset: str = 'E'  # E=股票, I=指数
    ) -> List[Dict]:
        """
        获取日K线数据

        Args:
            code: 股票代码
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
            asset: 资产类型 (E=股票, I=指数)

        Returns:
            K线数据列表，每条包含:
            - ts_code: Tushare代码
            - trade_date: 交易日期
            - open: 开盘价
            - high: 最高价
            - low: 最低价
            - close: 收盘价
            - volume: 成交量
            - amount: 成交额
            - change_pct: 涨跌幅
        """
        if self.pro is None:
            return []

        try:
            ts_code = self._to_ts_code(code)
            if not ts_code:
                return []

            # pro.daily 接口
            df = self.pro.daily(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date
            )

            if df is None or len(df) == 0:
                return []

            # 转换日期格式
            results = []
            for _, row in df.iterrows():
                results.append({
                    'ts_code': row['ts_code'],
                    'trade_date': row['trade_date'],
                    'open': row['open'],
                    'high': row['high'],
                    'low': row['low'],
                    'close': row['close'],
                    'volume': row['vol'],
                    'amount': row['amount'],
                    'change_pct': row['pct_chg'],
                    'source': 'tushare'
                })

            return results

        except Exception as e:
            print(f"获取 {code} 日K线失败: {e}")
            return []

    def get_weekly_kline(
        self,
        code: str,
        start_date: str,
        end_date: str
    ) -> List[Dict]:
        """
        获取周K线数据

        Args:
            code: 股票代码
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)

        Returns:
            周K线数据列表
        """
        if self.pro is None:
            return []

        try:
            ts_code = self._to_ts_code(code)
            if not ts_code:
                return []

            # 使用pro.weekly接口
            df = self.pro.weekly(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date
            )

            if df is None or len(df) == 0:
                return []

            results = []
            for _, row in df.iterrows():
                results.append({
                    'ts_code': row['ts_code'],
                    'trade_date': row['trade_date'],
                    'open': row['open'],
                    'high': row['high'],
                    'low': row['low'],
                    'close': row['close'],
                    'volume': row['vol'],
                    'amount': row['amount'],
                    'change_pct': row['pct_chg'],
                    'source': 'tushare'
                })

            return results

        except Exception as e:
            print(f"获取 {code} 周K线失败: {e}")
            return []

    def get_monthly_kline(
        self,
        code: str,
        start_date: str,
        end_date: str
    ) -> List[Dict]:
        """
        获取月K线数据

        Args:
            code: 股票代码
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)

        Returns:
            月K线数据列表
        """
        if self.pro is None:
            return []

        try:
            ts_code = self._to_ts_code(code)
            if not ts_code:
                return []

            # 使用pro.monthly接口
            df = self.pro.monthly(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date
            )

            if df is None or len(df) == 0:
                return []

            results = []
            for _, row in df.iterrows():
                results.append({
                    'ts_code': row['ts_code'],
                    'trade_date': row['trade_date'],
                    'open': row['open'],
                    'high': row['high'],
                    'low': row['low'],
                    'close': row['close'],
                    'volume': row['vol'],
                    'amount': row['amount'],
                    'change_pct': row['pct_chg'],
                    'source': 'tushare'
                })

            return results

        except Exception as e:
            print(f"获取 {code} 月K线失败: {e}")
            return []

    def get_financial_data(self, code: str) -> Dict:
        """
        获取财务数据（利润表）

        Args:
            code: 股票代码

        Returns:
            财务数据字典
        """
        if self.pro is None:
            return {}

        try:
            ts_code = self._to_ts_code(code)
            if not ts_code:
                return {}

            # 获取利润表数据
            df_income = self.pro.income(
                ts_code=ts_code,
                start_date='20230101',
                end_date='',
                fields='ts_code,ann_date,end_date,revenue,oper_profit,net_profit'
            )

            result = {}

            if df_income is not None and len(df_income) > 0:
                latest = df_income.iloc[0]
                result['revenue'] = latest.get('revenue', 0) / 100000000  # 转为亿元
                result['oper_profit'] = latest.get('oper_profit', 0) / 100000000
                result['net_profit'] = latest.get('net_profit', 0) / 100000000

                # 计算净利润增长率（需要对比去年同期）
                if len(df_income) >= 2:
                    current_net_profit = df_income.iloc[0].get('net_profit', 0)
                    last_year_net_profit = df_income.iloc[1].get('net_profit', 0)
                    if last_year_net_profit and last_year_net_profit != 0:
                        result['net_profit_growth'] = round(
                            (current_net_profit - last_year_net_profit) / abs(last_year_net_profit) * 100, 2
                        )

            return result

        except Exception as e:
            print(f"获取 {code} 财务数据失败: {e}")
            return {}

    def get_income_statement(self, code: str, start_year: int = 2023) -> Optional[pd.DataFrame]:
        """
        获取利润表

        Args:
            code: 股票代码
            start_year: 起始年份

        Returns:
            利润表DataFrame
        """
        if self.pro is None:
            return None

        try:
            ts_code = self._to_ts_code(code)
            if not ts_code:
                return None

            df = self.pro.income(
                ts_code=ts_code,
                start_date=f'{start_year}0101',
                fields='ts_code,ann_date,end_date,revenue,oper_profit,net_profit,total_profit'
            )

            return df

        except Exception as e:
            print(f"获取 {code} 利润表失败: {e}")
            return None

    def get_balance_sheet(self, code: str, start_year: int = 2023) -> Optional[pd.DataFrame]:
        """
        获取资产负债表

        Args:
            code: 股票代码
            start_year: 起始年份

        Returns:
            资产负债表DataFrame
        """
        if self.pro is None:
            return None

        try:
            ts_code = self._to_ts_code(code)
            if not ts_code:
                return None

            df = self.pro.balancesheet(
                ts_code=ts_code,
                start_date=f'{start_year}0101',
                fields='ts_code,ann_date,end_date,total_assets,total_liab,equity'
            )

            return df

        except Exception as e:
            print(f"获取 {code} 资产负债表失败: {e}")
            return None

    def get_cash_flow(self, code: str, start_year: int = 2023) -> Optional[pd.DataFrame]:
        """
        获取现金流量表

        Args:
            code: 股票代码
            start_year: 起始年份

        Returns:
            现金流量表DataFrame
        """
        if self.pro is None:
            return None

        try:
            ts_code = self._to_ts_code(code)
            if not ts_code:
                return None

            df = self.pro.cashflow(
                ts_code=ts_code,
                start_date=f'{start_year}0101',
                fields='ts_code,ann_date,end_date,net_operate_cashflow,net_invest_cashflow,net_financing_cashflow'
            )

            return df

        except Exception as e:
            print(f"获取 {code} 现金流量表失败: {e}")
            return None

    def _to_ts_code(self, code: str) -> Optional[str]:
        """
        将股票代码转换为Tushare格式

        Args:
            code: 股票代码 (e.g., 000001, sh000001)

        Returns:
            Tushare格式代码 (e.g., 000001.SZ)
        """
        code = str(code).strip()

        # 已经是Tushare格式
        if '.' in code:
            return code

        # 去除sh/sz前缀
        if code.startswith('sh') or code.startswith('sz'):
            code = code[2:]

        # 判断市场
        if code.startswith('6'):
            return f'{code}.SH'
        elif code.startswith(('0', '3')):
            return f'{code}.SZ'
        else:
            return f'{code}.SZ'  # 默认深市

    def health_check(self) -> bool:
        """健康检查"""
        if self.pro is None:
            return False

        try:
            # 尝试获取一只股票的基本信息
            df = self.pro.stock_basic(ts_code='000001.SZ', fields='ts_code')
            return df is not None and len(df) > 0
        except Exception:
            return False

    def get_stats(self) -> Dict:
        """获取统计信息"""
        base_stats = super().get_stats()
        return {
            **base_stats,
            'tushare_stats': self._stats,
            'budget_remaining': self._budget.get_remaining() if self._budget else 0,
        }


# ==================== 全局单例 ====================

_tushare_provider = None


def get_tushare_provider() -> TushareProvider:
    """获取Tushare提供者单例"""
    global _tushare_provider
    if _tushare_provider is None:
        _tushare_provider = TushareProvider()
    return _tushare_provider
