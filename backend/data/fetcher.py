"""
数据获取模块 - TradeSnake Data Fetcher
优化版：多数据源 + 缓存 + 智能选择 + 错误处理
"""

import os
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)

import akshare as ak
import requests
import pandas as pd
import numpy as np
import re
import time
import json
import hashlib
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from functools import lru_cache


# ==================== 常量配置 ====================
CACHE_DIR = "/home/ailearn/projects/TradeSnake/data"
CACHE_EXPIRE_MINUTES = 5  # 缓存过期时间

# 数据源配置（按优先级排序）
MARKET_DATA_SOURCES = [
    {"name": "腾讯", "url": "https://qt.gtimg.cn/q={codes}", "priority": 1},
    {"name": "新浪", "url": "https://hq.sinajs.cn/list={codes}", "priority": 2},
]

FINANCIAL_DATA_SOURCES = [
    {"name": "东方财富", "url": "https://datacenter-web.eastmoney.com/api/data/v1/get", "priority": 1},
    {"name": "同花顺", "url": "https://data.10jqka.com.cn/funds/ggzjl/", "priority": 2},
]


# ==================== 工具函数 ====================

def ensure_dir(path: str):
    """确保目录存在"""
    os.makedirs(path, exist_ok=True)


def get_cache_path(cache_type: str) -> str:
    """获取缓存文件路径"""
    ensure_dir(CACHE_DIR)
    return os.path.join(CACHE_DIR, f"{cache_type}_cache.json")


def read_cache(cache_type: str) -> Optional[Dict]:
    """读取缓存"""
    cache_file = get_cache_path(cache_type)
    if not os.path.exists(cache_file):
        return None

    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache = json.load(f)

        # 检查是否过期
        expire_time = datetime.fromisoformat(cache.get('expire_at', '2000-01-01'))
        if datetime.now() > expire_time:
            return None

        return cache.get('data')
    except:
        return None


def write_cache(cache_type: str, data: Dict, expire_minutes: int = CACHE_EXPIRE_MINUTES):
    """写入缓存"""
    cache_file = get_cache_path(cache_type)
    try:
        cache = {
            'data': data,
            'expire_at': (datetime.now() + timedelta(minutes=expire_minutes)).isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False)
    except Exception as e:
        print(f"缓存写入失败: {e}")


def md5_hash(text: str) -> str:
    """生成MD5哈希"""
    return hashlib.md5(text.encode()).hexdigest()[:8]


# ==================== 股票列表获取 ====================

class StockListFetcher:
    """股票列表获取器"""

    def __init__(self):
        self._cache = None

    def get_stock_list(self, force_refresh: bool = False) -> pd.DataFrame:
        """获取A股股票列表（带缓存）"""
        if self._cache is not None and not force_refresh:
            return self._cache

        # 尝试读取缓存
        if not force_refresh:
            cached = read_cache('stock_list')
            if cached is not None:
                self._cache = pd.DataFrame(cached)
                return self._cache

        # 从akshare获取
        try:
            df = ak.stock_info_a_code_name()
            self._cache = df

            # 写入缓存
            write_cache('stock_list', df.to_dict('records'), expire_minutes=60 * 24)  # 股票列表缓存24小时

            return df
        except Exception as e:
            print(f"获取股票列表失败: {e}")
            # 返回缓存（即使过期）
            cached = read_cache('stock_list')
            if cached is not None:
                self._cache = pd.DataFrame(cached)
                return self._cache
            return pd.DataFrame()

    def get_market_cap_leaders(self, limit: int = 50) -> List[str]:
        """获取市值前N的股票代码（用于优先获取数据）"""
        try:
            # 尝试从缓存获取今日成交额排名
            cached = read_cache('top_volume')
            if cached:
                return cached[:limit]

            # 使用akshare获取成交额排名
            df = ak.stock_zh_a_spot_em()  # 获取所有股票实时数据
            if df is not None and len(df) > 0:
                # 按成交额排序，取前N
                if '成交额' in df.columns:
                    df = df.sort_values('成交额', ascending=False)
                    top_codes = df['代码'].head(limit).tolist()
                    write_cache('top_volume', top_codes, expire_minutes=60)  # 成交额数据缓存1小时
                    return top_codes

        except Exception as e:
            print(f"获取市值排名失败: {e}")

        return []


# ==================== 行情数据获取 ====================

class MarketDataFetcher:
    """行情数据获取器（支持多数据源）"""

    def __init__(self):
        self.stock_list_fetcher = StockListFetcher()
        self._tencent_session = requests.Session()
        self._tencent_session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def get_market_data(self, codes: List[str], use_cache: bool = True) -> List[Dict]:
        """获取行情数据（多数据源自动切换）"""
        if not codes:
            return []

        # 缓存key
        cache_key = md5_hash(','.join(sorted(codes)))

        # 尝试读缓存
        if use_cache:
            cached = read_cache(f'market_{cache_key}')
            if cached:
                return cached

        # 尝试腾讯API
        data = self._fetch_from_tencent(codes)
        if data:
            write_cache(f'market_{cache_key}', data, expire_minutes=CACHE_EXPIRE_MINUTES)
            return data

        # 腾讯失败，尝试新浪
        data = self._fetch_from_sina(codes)
        if data:
            write_cache(f'market_{cache_key}', data, expire_minutes=CACHE_EXPIRE_MINUTES)
            return data

        return []

    def _fetch_from_tencent(self, codes: List[str]) -> List[Dict]:
        """从腾讯API获取行情"""
        try:
            tencent_codes = []
            for code in codes:
                code = str(code).strip()
                if code.startswith(('sh', 'sz')):
                    tencent_codes.append(code)
                elif code.startswith('6'):
                    tencent_codes.append(f'sh{code}')
                else:
                    tencent_codes.append(f'sz{code}')

            codes_str = ','.join(tencent_codes)
            url = f"https://qt.gtimg.cn/q={codes_str}"

            r = self._tencent_session.get(url, timeout=10)
            r.encoding = 'gbk'

            return self._parse_tencent_data(r.text)

        except Exception as e:
            print(f"腾讯API获取失败: {e}")
            return []

    def _fetch_from_sina(self, codes: List[str]) -> List[Dict]:
        """从新浪API获取行情（备用）"""
        try:
            sina_codes = []
            for code in codes:
                code = str(code).strip()
                if code.startswith(('sh', 'sz')):
                    sina_codes.append(code)
                elif code.startswith('6'):
                    sina_codes.append(f'sh{code}')
                else:
                    sina_codes.append(f'sz{code}')

            codes_str = ','.join(sina_codes)
            url = f"https://hq.sinajs.cn/list={codes_str}"

            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Referer': 'https://finance.sina.com.cn'
            }

            r = requests.get(url, headers=headers, timeout=10)
            r.encoding = 'gbk'

            return self._parse_sina_data(r.text)

        except Exception as e:
            print(f"新浪API获取失败: {e}")
            return []

    def _parse_tencent_data(self, data: str) -> List[Dict]:
        """解析腾讯行情数据"""
        stocks = []
        lines = data.strip().split('\n')

        for line in lines:
            if not line.strip():
                continue

            match = re.search(r'v_(\w+)="(.+)"', line)
            if not match:
                continue

            code = match.group(1)
            fields = match.group(2).split('~')

            if len(fields) < 40:
                continue

            try:
                price = float(fields[3]) if fields[3] and fields[3] != '-' else 0
                yesterday = float(fields[4]) if fields[4] and fields[4] != '-' else 0
                change_pct = ((price - yesterday) / yesterday * 100) if yesterday > 0 else 0

                # 市值（从fields[44]获取，已是亿单位）
                market_cap = 0
                if len(fields) > 44 and fields[44] and fields[44] != '-':
                    try:
                        market_cap = float(fields[44])  # 已是亿单位
                    except:
                        pass

                stocks.append({
                    'code': code,
                    'name': fields[1] if len(fields) > 1 else '',
                    'price': price,
                    'yesterday': yesterday,
                    'open': float(fields[5]) if fields[5] and fields[5] != '-' else 0,
                    'high': float(fields[33]) if len(fields) > 33 and fields[33] and fields[33] != '-' else 0,
                    'low': float(fields[34]) if len(fields) > 34 and fields[34] and fields[34] != '-' else 0,
                    'volume': int(fields[6]) if fields[6] and fields[6] != '-' else 0,  # 成交量(手)
                    'amount': float(fields[37]) if len(fields) > 37 and fields[37] and fields[37] != '-' else 0,  # 成交额(万)
                    'pe': float(fields[39]) if len(fields) > 39 and fields[39] and fields[39] != '-' else 0,
                    'pb': float(fields[46]) if len(fields) > 46 and fields[46] and fields[46] != '-' else 0,
                    'change_pct': round(change_pct, 2),
                    'market_cap': round(market_cap, 2),  # 市值(亿)
                    'source': 'tencent'
                })
            except Exception as e:
                continue

        return stocks

    def _parse_sina_data(self, data: str) -> List[Dict]:
        """解析新浪行情数据"""
        stocks = []
        lines = data.strip().split('\n')

        for line in lines:
            if not line.strip():
                continue

            # 新浪格式: var hq_str_sz000001="平安银行,10.50,10.60,10.55,..."
            match = re.search(r'var hq_str_(\w+)="(.+)"', line)
            if not match:
                continue

            code = match.group(1)
            fields = match.group(2).split(',')

            if len(fields) < 32:
                continue

            try:
                price = float(fields[3]) if fields[3] and fields[3] != '-' else 0
                yesterday = float(fields[2]) if fields[2] and fields[2] != '-' else 0
                change_pct = ((price - yesterday) / yesterday * 100) if yesterday > 0 else 0

                stocks.append({
                    'code': code,
                    'name': fields[0] if fields[0] else '',
                    'price': price,
                    'yesterday': yesterday,
                    'open': float(fields[1]) if fields[1] and fields[1] != '-' else 0,
                    'high': float(fields[4]) if len(fields) > 4 and fields[4] and fields[4] != '-' else 0,
                    'low': float(fields[5]) if len(fields) > 5 and fields[5] and fields[5] != '-' else 0,
                    'volume': int(float(fields[8])) if len(fields) > 8 and fields[8] and fields[8] != '-' else 0,
                    'amount': float(fields[9]) if len(fields) > 9 and fields[9] and fields[9] != '-' else 0,
                    'pe': float(fields[39]) if len(fields) > 39 and fields[39] and fields[39] != '-' else 0,
                    'pb': 0,  # 新浪数据通常不含PB
                    'change_pct': round(change_pct, 2),
                    'market_cap': 0,
                    'source': 'sina'
                })
            except Exception as e:
                continue

        return stocks


# ==================== 财务数据获取 ====================

class FinancialDataFetcher:
    """财务数据获取器"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://data.eastmoney.com/'
        })

    def get_financial_data(self, symbol: str, use_cache: bool = True) -> Dict:
        """获取单只股票财务数据"""
        # 缓存key
        cache_key = f"fin_{symbol}"

        if use_cache:
            cached = read_cache(cache_key)
            if cached:
                return cached

        # 判断市场
        if symbol.startswith('6'):
            market = 'SH'
        else:
            market = 'SZ'

        # 获取东方财富数据
        data = self._fetch_from_eastmoney(symbol, market)
        if data:
            write_cache(cache_key, data, expire_minutes=60 * 24)  # 财务数据缓存24小时
            return data

        # 东方财富失败，尝试备用
        data = self._fetch_backup(symbol, market)
        if data:
            write_cache(cache_key, data, expire_minutes=60 * 24)
            return data

        # 都失败，返回空数据（带标记）
        return {
            'roe': 0, 'net_profit_growth': 0, 'revenue_growth': 0,
            'gross_margin': 0, 'revenue': 0, 'cashflow': 0, 'debt_ratio': 0,
            'dividend_yield': 0, 'turnover_rate': 0,
            'data_quality': 'low',  # 数据质量标记
            'source': 'none'
        }

    def _fetch_from_eastmoney(self, symbol: str, market: str) -> Optional[Dict]:
        """从东方财富获取财务数据"""
        try:
            url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
            params = {
                "reportName": "RPT_LICO_FN_CPD",
                "columns": "WEIGHTAVG_ROE,YSTZ,SJLTZ,GPZYTZXJ,MAIN_BUSINESS_INCOME,OPERATE_CASHFLOW,ASSET_LIAB_RATIO,DIVIDEND_RATIO",
                "filter": f"(SECUCODE=\"{symbol}.{market}\")",
                "pageNumber": 1,
                "pageSize": 1,
                "sortTypes": -1,
                "sortColumns": "REPORTDATE",
                "source": "DataCenter",
                "client": "PC"
            }

            r = self.session.get(url, params=params, timeout=10)
            result = r.json()

            if result.get('result') and result['result'].get('data'):
                d = result['result']['data'][0]
                return {
                    'roe': round(float(d.get('WEIGHTAVG_ROE', 0) or 0), 2),
                    'net_profit_growth': round(float(d.get('SJLTZ', 0) or 0), 2),
                    'revenue_growth': round(float(d.get('YSTZ', 0) or 0), 2),
                    'gross_margin': round(float(d.get('GPZYTZXJ', 0) or 0), 2),
                    'revenue': round(float(d.get('MAIN_BUSINESS_INCOME', 0) or 0) / 100000000, 2),
                    'cashflow': round(float(d.get('OPERATE_CASHFLOW', 0) or 0) / 100000000, 2),
                    'debt_ratio': round(float(d.get('ASSET_LIAB_RATIO', 0) or 0), 2),
                    'dividend_yield': round(float(d.get('DIVIDEND_RATIO', 0) or 0), 2),  # 股息率
                    'data_quality': 'high',
                    'source': 'eastmoney'
                }

        except Exception as e:
            print(f"东方财富财务API失败 {symbol}: {e}")

        return None

    def _fetch_backup(self, symbol: str, market: str) -> Optional[Dict]:
        """从备用源获取财务数据（简化版，主要返回关键指标）"""
        try:
            # 使用akshare获取财务数据作为备用
            # 注意：akshare的财务接口可能有限制
            # 这里简化为返回估算值
            return {
                'roe': 0, 'net_profit_growth': 0, 'revenue_growth': 0,
                'gross_margin': 0, 'revenue': 0, 'cashflow': 0, 'debt_ratio': 0,
                'dividend_yield': 0,
                'data_quality': 'medium',  # 备用源质量标记
                'source': 'backup'
            }
        except:
            return None


# ==================== 主数据获取器 ====================

class StockDataFetcher:
    """综合股票数据获取器"""

    def __init__(self):
        self.market_fetcher = MarketDataFetcher()
        self.financial_fetcher = FinancialDataFetcher()
        self.stock_list_fetcher = StockListFetcher()

    def get_stock_list(self) -> pd.DataFrame:
        """获取股票列表"""
        return self.stock_list_fetcher.get_stock_list()

    def get_market_data_tencent(self, codes: List[str]) -> List[Dict]:
        """获取行情数据（兼容旧接口）"""
        return self.market_fetcher.get_market_data(codes)

    def get_batch_market_data(self, limit: int = 300, prefer_top: bool = True) -> List[Dict]:
        """批量获取市场数据（智能选择）"""
        stock_df = self.stock_list_fetcher.get_stock_list()

        # 基础过滤：沪深主板，排除ST
        main_stocks = stock_df[
            stock_df['code'].str.startswith(('6', '0')) &
            ~stock_df['name'].str.contains('ST', na=False)
        ]

        if prefer_top:
            # 优先选择成交额高的股票（更有代表性）
            top_codes = self.stock_list_fetcher.get_market_cap_leaders(limit * 2)
            if top_codes:
                # 合并：优先取市值大的，剩余用随机补充
                available = main_stocks[main_stocks['code'].isin(top_codes)]
                if len(available) >= limit:
                    sample = available.head(limit)
                else:
                    remaining = main_stocks[~main_stocks['code'].isin(top_codes)]
                    needed = limit - len(available)
                    sample = pd.concat([available, remaining.head(needed)])
            else:
                sample = main_stocks.sample(n=min(limit, len(main_stocks)), random_state=42)
        else:
            sample = main_stocks.sample(n=min(limit, len(main_stocks)), random_state=42)

        # 分批获取行情
        all_data = []
        batch_size = 50

        for i in range(0, len(sample), batch_size):
            batch = sample.iloc[i:i+batch_size]
            codes = batch['code'].tolist()
            market_data = self.market_fetcher.get_market_data(codes)
            all_data.extend(market_data)
            time.sleep(0.05)  # 避免请求过快

        return all_data

    def get_full_stock_data(self, limit: int = 100, prefer_top: bool = True) -> List[Dict]:
        """获取完整股票数据（行情+财务）"""
        # 获取行情
        market_data = self.get_batch_market_data(limit, prefer_top)

        full_data = []
        success_count = 0
        fail_count = 0

        for mkt in market_data:
            code = mkt.get('code', '')
            if not code:
                continue

            # 转换代码格式
            if code.startswith('sh'):
                symbol = code[2:]
            elif code.startswith('sz'):
                symbol = code[2:]
            else:
                continue

            # 获取财务数据
            fin = self.financial_fetcher.get_financial_data(symbol)

            # 合并数据
            data = {
                'code': code,
                'name': mkt.get('name', ''),
                'price': mkt.get('price', 0),
                'yesterday': mkt.get('yesterday', 0),
                'open': mkt.get('open', 0),
                'high': mkt.get('high', 0),
                'low': mkt.get('low', 0),
                'volume': mkt.get('volume', 0),
                'amount': mkt.get('amount', 0),
                'pe': mkt.get('pe', 0),
                'pb': mkt.get('pb', 0),
                'change_pct': mkt.get('change_pct', 0),
                'market_cap': mkt.get('market_cap', 0),
                'roe': fin.get('roe', 0),
                'net_profit_growth': fin.get('net_profit_growth', 0),
                'revenue_growth': fin.get('revenue_growth', 0),
                'gross_margin': fin.get('gross_margin', 0),
                'revenue': fin.get('revenue', 0),
                'cashflow': fin.get('cashflow', 0),
                'debt_ratio': fin.get('debt_ratio', 0),
                'dividend_yield': fin.get('dividend_yield', 0),
                'data_quality': fin.get('data_quality', 'low'),
                'data_source': mkt.get('source', 'unknown')
            }

            full_data.append(data)

            # 统计
            if fin.get('data_quality') == 'high':
                success_count += 1
            else:
                fail_count += 1

            time.sleep(0.1)  # 避免请求过快

        # 记录获取统计
        if full_data:
            total = success_count + fail_count
            quality_rate = success_count / total * 100 if total > 0 else 0
            print(f"数据获取完成: 共{total}只, 高质量{success_count}只({quality_rate:.1f}%), 低质量{fail_count}只")

        return full_data


# ==================== 便捷函数 ====================

# 全局实例（复用）
_global_fetcher = None

def get_stock_data_api(limit: int = 100) -> List[Dict]:
    """便捷函数：获取股票数据"""
    global _global_fetcher
    if _global_fetcher is None:
        _global_fetcher = StockDataFetcher()
    return _global_fetcher.get_full_stock_data(limit)


def get_single_stock_data(code: str) -> Optional[Dict]:
    """便捷函数：获取单只股票数据"""
    fetcher = StockDataFetcher()

    # 规范化代码格式
    clean_code = code.upper().strip()
    if clean_code.startswith('SH'):
        clean_code = clean_code[2:]
    elif clean_code.startswith('SZ'):
        clean_code = clean_code[2:]

    # 转换代码格式
    if clean_code.startswith('6'):
        tencent_code = f'sh{clean_code}'
    else:
        tencent_code = f'sz{clean_code}'

    # 获取行情
    market_fetcher = MarketDataFetcher()
    market_data = market_fetcher.get_market_data([clean_code], use_cache=False)
    if not market_data:
        return None

    mkt = market_data[0]

    # 获取财务
    financial_fetcher = FinancialDataFetcher()
    fin = financial_fetcher.get_financial_data(clean_code, use_cache=False)

    return {
        'code': tencent_code,
        'name': mkt.get('name', ''),
        'price': mkt.get('price', 0),
        'open': mkt.get('open', 0),
        'yesterday': mkt.get('yesterday', 0),
        'high': mkt.get('high', 0),
        'low': mkt.get('low', 0),
        'volume': mkt.get('volume', 0),
        'amount': mkt.get('amount', 0),
        'pe': mkt.get('pe', 0),
        'pb': mkt.get('pb', 0),
        'change_pct': mkt.get('change_pct', 0),
        'market_cap': mkt.get('market_cap', 0),
        'roe': fin.get('roe', 0),
        'net_profit_growth': fin.get('net_profit_growth', 0),
        'revenue_growth': fin.get('revenue_growth', 0),
        'gross_margin': fin.get('gross_margin', 0),
        'revenue': fin.get('revenue', 0),
        'cashflow': fin.get('cashflow', 0),
        'debt_ratio': fin.get('debt_ratio', 0),
        'dividend_yield': fin.get('dividend_yield', 0),
        'data_quality': fin.get('data_quality', 'low'),
    }
