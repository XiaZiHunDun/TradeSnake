"""
数据获取模块 - TradeSnake Data Fetcher
优化版：多数据源 + 缓存 + 智能选择 + 重试机制 + 错误处理
"""

import os
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)

import akshare as ak
import requests
import pandas as pd
import re
import time
import json
import hashlib
import threading
import baostock as bs
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from collections import OrderedDict

# ==================== 常量配置 ====================
# 重试配置
MAX_RETRIES = 3
RETRY_DELAY = 1  # 秒

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


# ==================== 内存缓存（LRU）====================

class MemoryCache:
    """线程安全的内存LRU缓存"""

    def __init__(self, maxsize: int = 128, ttl_seconds: int = 60):
        self._cache = OrderedDict()
        self._timestamps = {}
        self._maxsize = maxsize
        self._ttl = ttl_seconds
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[any]:
        """获取缓存值"""
        with self._lock:
            if key not in self._cache:
                return None

            # 检查TTL
            if time.time() - self._timestamps[key] > self._ttl:
                del self._cache[key]
                del self._timestamps[key]
                return None

            # 移到末尾（最近使用）
            self._cache.move_to_end(key)
            return self._cache[key]

    def set(self, key: str, value: any):
        """设置缓存值"""
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            else:
                if len(self._cache) >= self._maxsize:
                    # 删除最旧的条目
                    oldest = next(iter(self._cache))
                    del self._cache[oldest]
                    del self._timestamps[oldest]

            self._cache[key] = value
            self._timestamps[key] = time.time()

    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._timestamps.clear()


# 全局内存缓存实例
_memory_cache = MemoryCache(maxsize=256, ttl_seconds=30)


# ==================== 工具函数 ====================

def ensure_dir(path: str):
    """确保目录存在"""
    os.makedirs(path, exist_ok=True)


def get_cache_path(cache_type: str) -> str:
    """获取缓存文件路径"""
    ensure_dir(CACHE_DIR)
    return os.path.join(CACHE_DIR, f"{cache_type}_cache.json")


def read_cache(cache_type: str) -> Optional[Dict]:
    """读取缓存（优先从内存缓存读取）"""
    # 优先从内存缓存读取
    mem_value = _memory_cache.get(cache_type)
    if mem_value is not None:
        return mem_value

    # 内存缓存未命中，从磁盘读取
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

        data = cache.get('data')
        # 写入内存缓存
        if data is not None:
            _memory_cache.set(cache_type, data)
        return data
    except Exception as e:
        print(f"读取缓存失败 {cache_type}: {e}")
        return None


def write_cache(cache_type: str, data: Dict, expire_minutes: int = CACHE_EXPIRE_MINUTES):
    """写入缓存（同时写入内存和磁盘）"""
    # 先写入内存缓存
    _memory_cache.set(cache_type, data)

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
        """从腾讯API获取行情（带重试）"""
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

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                r = self._tencent_session.get(url, timeout=10)
                r.encoding = 'gbk'
                return self._parse_tencent_data(r.text)
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (2 ** attempt))
                    print(f"  腾讯API重试 {attempt + 2}/{MAX_RETRIES}: {e}")

        print(f"  腾讯API获取失败: {last_error}")
        return []

    def _fetch_from_sina(self, codes: List[str]) -> List[Dict]:
        """从新浪API获取行情（备用，带重试）"""
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

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                r = requests.get(url, headers=headers, timeout=10)
                r.encoding = 'gbk'
                return self._parse_sina_data(r.text)
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (2 ** attempt))
                    print(f"  新浪API重试 {attempt + 2}/{MAX_RETRIES}: {e}")

        print(f"  新浪API获取失败: {last_error}")
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
                    except Exception:
                        pass  # 市值解析失败不影响其他数据

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
        # 先尝试东方财富（更快）
        em_data = self._fetch_from_eastmoney(symbol, market)

        # 同时获取baostock数据（更全面）
        bs_data = self._fetch_from_baostock(symbol)

        # 合并数据：优先使用东方财富的值，baostock补充缺失字段
        if em_data and bs_data:
            # 东方财富有数据，baostock补充缺失字段
            result = em_data.copy()
            if result.get('gross_margin', 0) == 0 and bs_data.get('gross_margin', 0) > 0:
                result['gross_margin'] = bs_data['gross_margin']
            if result.get('revenue', 0) == 0 and bs_data.get('revenue', 0) > 0:
                result['revenue'] = bs_data['revenue']
            if result.get('debt_ratio', 0) == 0 and bs_data.get('debt_ratio', 0) > 0:
                result['debt_ratio'] = bs_data['debt_ratio']
            if result.get('cashflow', 0) == 0 and bs_data.get('cashflow', 0) != 0:
                result['cashflow'] = bs_data['cashflow']
            # 股息数据用baostock的
            if bs_data.get('dividend_per_share'):
                result['dividend_per_share'] = bs_data['dividend_per_share']
            # 数据源标记
            result['source'] = 'eastmoney+baostock'
        elif em_data:
            result = em_data
        elif bs_data:
            result = bs_data
        else:
            result = None

        # 用akshare补充流动比率、利息保障倍数、扣非净利润等字段
        try:
            df_ak = ak.stock_financial_analysis_indicator(symbol=symbol, start_year='2023')
            if df_ak is not None and len(df_ak) > 0:
                latest_ak = df_ak.iloc[-1]
                if result is None:
                    result = {}
                # 流动比率
                current_ratio = latest_ak.get('流动比率', 0)
                if current_ratio is not None and str(current_ratio) != 'nan':
                    result['current_ratio'] = round(float(current_ratio), 2)
                # 利息保障倍数
                interest_coverage = latest_ak.get('利息支付倍数', 0)
                if interest_coverage is not None and str(interest_coverage) != 'nan':
                    result['interest_coverage'] = round(float(interest_coverage), 2)
                # 扣非净利润（亿元）
                deducted_net_profit = latest_ak.get('扣除非经常性损益后的净利润(元)', 0)
                if deducted_net_profit is not None and str(deducted_net_profit) != 'nan':
                    result['deducted_net_profit'] = round(float(deducted_net_profit) / 100000000, 2)
        except Exception as e:
            print(f"  akshare补充字段失败 {symbol}: {e}")

        if result:
            write_cache(cache_key, result, expire_minutes=60 * 24)
            return result

        # 都失败，返回空数据（带标记）
        return {
            'roe': 0, 'net_profit_growth': 0, 'revenue_growth': 0,
            'gross_margin': 0, 'revenue': 0, 'cashflow': 0, 'debt_ratio': 0,
            'current_ratio': 0, 'interest_coverage': 0, 'deducted_net_profit': 0,
            'dividend_yield': 0, 'turnover_rate': 0,
            'data_quality': 'low',  # 数据质量标记
            'source': 'none'
        }

    def _fetch_from_eastmoney(self, symbol: str, market: str) -> Optional[Dict]:
        """从东方财富获取财务数据（带重试）"""
        # 注意：东方财富RPT_LICO_FN_CPD报告的部分字段已更名或废弃
        # 目前仅确认以下字段可用：WEIGHTAVG_ROE, YSTZ, SJLTZ
        # 其他字段（GPZYTZXJ, MAIN_BUSINESS_INCOME, OPERATE_CASHFLOW等）已不存在
        url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
        params = {
            "reportName": "RPT_LICO_FN_CPD",
            "columns": "WEIGHTAVG_ROE,YSTZ,SJLTZ",
            "filter": f"(SECUCODE=\"{symbol}.{market}\")",
            "pageNumber": 1,
            "pageSize": 1,
            "sortTypes": -1,
            "sortColumns": "REPORTDATE",
            "source": "DataCenter",
            "client": "PC"
        }

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                r = self.session.get(url, params=params, timeout=10)
                result = r.json()

                if result.get('result') and result['result'].get('data'):
                    d = result['result']['data'][0]
                    return {
                        'roe': round(float(d.get('WEIGHTAVG_ROE', 0) or 0), 2),
                        'net_profit_growth': round(float(d.get('SJLTZ', 0) or 0), 2),
                        'revenue_growth': round(float(d.get('YSTZ', 0) or 0), 2),
                        # 其他字段由baostock补充
                        'gross_margin': 0,
                        'revenue': 0,
                        'cashflow': 0,
                        'debt_ratio': 0,
                        'dividend_yield': 0,
                        'data_quality': 'high',
                        'source': 'eastmoney'
                    }
                return None  # 数据为空，不重试

            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (2 ** attempt))
                    print(f"  东方财富API重试 {attempt + 2}/{MAX_RETRIES} ({symbol}): {e}")

        print(f"  东方财富财务API失败 {symbol}: {last_error}")
        return None

    def _fetch_from_baostock(self, symbol: str) -> Optional[Dict]:
        """从baostock获取财务数据"""
        try:
            # 转换代码格式
            if symbol.startswith('6'):
                baostock_code = f'sh.{symbol}'
            else:
                baostock_code = f'sz.{symbol}'

            lg = bs.login()
            if lg.error_code != '0':
                bs.logout()
                return None

            result = {
                'roe': 0,
                'net_profit_growth': 0,
                'revenue_growth': 0,
                'gross_margin': 0,
                'revenue': 0,
                'cashflow': 0,
                'debt_ratio': 0,
                'dividend_yield': 0,
                'data_quality': 'low',
                'source': 'baostock'
            }

            # 获取盈利能力数据 (ROE, 毛利率, 营收)
            try:
                rs = bs.query_profit_data(code=baostock_code, year=2024, quarter=4)
                if rs.error_code == '0':
                    data = rs.get_data()
                    if len(data) > 0:
                        row = data.iloc[-1]
                        # roeAvg 是 ROE 小数 (如 0.384 表示 38.4%)
                        roe = row.get('roeAvg')
                        if roe is not None and str(roe) != '' and str(roe) != 'nan':
                            result['roe'] = round(float(roe) * 100, 2)
                        # gpMargin 是毛利率小数 (如 0.92 表示 92%)
                        gp = row.get('gpMargin')
                        if gp is not None and str(gp) != '' and str(gp) != 'nan':
                            result['gross_margin'] = round(float(gp) * 100, 2)
                        # MBRevenue 是主营业务收入 (元)，转为亿元
                        mbrevenue = row.get('MBRevenue')
                        if mbrevenue is not None and str(mbrevenue) != '' and str(mbrevenue) != 'nan':
                            result['revenue'] = round(float(mbrevenue) / 100000000, 2)
            except Exception as e:
                print(f"  baostock盈利能力获取失败 {symbol}: {e}")

            # 获取成长能力数据 (净利润增长率)
            try:
                rs = bs.query_growth_data(code=baostock_code, year=2024, quarter=4)
                if rs.error_code == '0':
                    data = rs.get_data()
                    if len(data) > 0:
                        row = data.iloc[-1]
                        # YOYNI 是净利润同比增长百分比
                        yoyni = row.get('YOYNI')
                        if yoyni is not None and str(yoyni) != '' and str(yoyni) != 'nan':
                            result['net_profit_growth'] = round(float(yoyni) * 100, 2)
                        # YOYOR 营收增长率
                        yoyor = row.get('YOYOR')
                        if yoyor is not None and str(yoyor) != '' and str(yoyor) != 'nan':
                            result['revenue_growth'] = round(float(yoyor) * 100, 2)
            except Exception as e:
                print(f"  baostock成长能力获取失败 {symbol}: {e}")

            # 获取资产负债表数据 (资产负债率)
            # 注意：baostock的liabilityToAsset字段值异常，改用assetToEquity计算
            # debt_ratio = (assets - equity) / assets = 1 - equity/assets = 1 - 1/(assetToEquity)
            try:
                rs = bs.query_balance_data(code=baostock_code, year=2024, quarter=4)
                if rs.error_code == '0':
                    data = rs.get_data()
                    if len(data) > 0:
                        row = data.iloc[-1]
                        asset_to_equity = row.get('assetToEquity')
                        if asset_to_equity is not None and str(asset_to_equity) != '' and str(asset_to_equity) != 'nan':
                            ate = float(asset_to_equity)
                            if ate > 0:
                                result['debt_ratio'] = round((1 - 1/ate) * 100, 2)
            except Exception as e:
                print(f"  baostock资产负债表获取失败 {symbol}: {e}")

            # 获取现金流数据 (经营现金流)
            # baostock只提供比率字段(CFOToNP=经营现金流/净利润, CFOToOR=经营现金流/营收)
            # 用CFOToNP判断正负，如果CFOToNP为空则用CFOToOR
            try:
                rs = bs.query_cash_flow_data(code=baostock_code, year=2024, quarter=4)
                if rs.error_code == '0':
                    data = rs.get_data()
                    if len(data) > 0:
                        row = data.iloc[-1]
                        # 优先用CFOToNP，如果为空则用CFOToOR
                        cfo_to_np = row.get('CFOToNP')
                        cfo_ratio = None
                        if cfo_to_np is not None and str(cfo_to_np) != '' and str(cfo_to_np) != 'nan':
                            cfo_ratio = float(cfo_to_np)
                        elif cfo_to_np is not None and str(cfo_to_np) == '':
                            # CFOToNP为空，尝试用CFOToOR
                            cfo_to_or = row.get('CFOToOR')
                            if cfo_to_or is not None and str(cfo_to_or) != '' and str(cfo_to_or) != 'nan':
                                cfo_ratio = float(cfo_to_or)
                        if cfo_ratio is not None and cfo_ratio > 0:
                            result['cashflow'] = 1  # 正现金流标记
                        elif cfo_ratio is not None and cfo_ratio < 0:
                            result['cashflow'] = -1  # 负现金流标记
            except Exception as e:
                print(f"  baostock现金流获取失败 {symbol}: {e}")

            # 获取股息数据 (每股派息)
            # 股息率需要用股价计算，这里先获取每股派息
            try:
                rs = bs.query_dividend_data(code=baostock_code, year=2024)
                if rs.error_code == '0':
                    data = rs.get_data()
                    if len(data) > 0:
                        row = data.iloc[-1]
                        # dividCashPsBeforeTax 是每股派息(含税)，单位元
                        dividend_ps = row.get('dividCashPsBeforeTax')
                        if dividend_ps is not None and str(dividend_ps) != '' and str(dividend_ps) != 'nan':
                            result['dividend_per_share'] = round(float(dividend_ps), 2)
            except Exception as e:
                print(f"  baostock股息数据获取失败 {symbol}: {e}")

            bs.logout()

            # 用akshare补充现金流绝对值（每股经营性现金流 × 总股本）
            # 注意：baostock在logout后需要重新登录才能查询
            try:
                # 获取每股经营性现金流
                df_ak = ak.stock_financial_analysis_indicator(symbol=symbol, start_year='2023')
                if df_ak is not None and len(df_ak) > 0:
                    latest_ak = df_ak.iloc[-1]
                    ocf_per_share = latest_ak.get('每股经营性现金流(元)', 0)
                    if ocf_per_share and float(ocf_per_share) > 0:
                        # 重新登录baostock获取总股本
                        lg2 = bs.login()
                        if lg2.error_code == '0':
                            rs_bs = bs.query_profit_data(code=baostock_code, year=2024, quarter=4)
                            if rs_bs.error_code == '0':
                                data_bs = rs_bs.get_data()
                                if len(data_bs) > 0:
                                    total_share = float(data_bs.iloc[-1].get('totalShare', 0)) / 100000000  # 转为亿股
                                    if total_share > 0:
                                        ocf_abs = float(ocf_per_share) * total_share
                                        result['cashflow'] = round(ocf_abs, 2)  # 存储现金流绝对值（亿元）
                                        result['cashflow_source'] = 'akshare+baostock'
                                        print(f"  {symbol} 经营现金流绝对值: {ocf_abs:.2f}亿元 (每股{ocf_per_share}元 × {total_share:.2f}亿股)")
                            bs.logout()
            except Exception as e:
                print(f"  akshare现金流补充失败 {symbol}: {e}")
                # 清理可能导致的问题
                if 'cashflow' in result and isinstance(result.get('cashflow'), str):
                    result['cashflow'] = 0

            # 如果获取到有效数据，提升质量标记
            if result['roe'] > 0 or result['net_profit_growth'] != 0:
                result['data_quality'] = 'medium'

            return result

        except Exception as e:
            try:
                bs.logout()
            except:
                pass
            print(f"  baostock获取财务数据失败 {symbol}: {e}")
            return None

    def _fetch_backup(self, symbol: str, market: str) -> Optional[Dict]:
        """从备用源获取财务数据（优先baostock，其次akshare）"""
        # 先尝试baostock
        data = self._fetch_from_baostock(symbol)
        if data and (data['roe'] > 0 or data['net_profit_growth'] != 0):
            return data

        # 再尝试akshare
        try:
            # 使用akshare获取财务数据作为备用
            try:
                df = ak.stock_financial_analysis_indicator(symbol=symbol)
                if df is not None and len(df) > 0:
                    latest = df.iloc[-1]

                    # 尝试获取ROE（兼容新旧列名）
                    roe = (
                        latest.get('加权净资产收益率（%）', 0) or
                        latest.get('净资产收益率（%）', 0) or
                        latest.get('加权平均净资产收益率', 0) or
                        latest.get('净资产收益率(%)', 0) or
                        0
                    )

                    # 尝试获取净利润增长率
                    net_profit_growth = (
                        latest.get('净利润增长率（%）', 0) or
                        latest.get('净利润增长率', 0) or
                        latest.get('净利润增长率(%)', 0) or
                        0
                    )

                    # 尝试获取营收增长率
                    revenue_growth = (
                        latest.get('主营业务收入增长率（%）', 0) or
                        latest.get('主营业务收入增长率', 0) or
                        latest.get('主营业务收入增长率(%)', 0) or
                        0
                    )

                    # 尝试获取毛利率
                    gross_margin = (
                        latest.get('销售毛利率（%）', 0) or
                        latest.get('销售毛利率', 0) or
                        latest.get('销售毛利率(%)', 0) or
                        0
                    )

                    # 尝试获取流动比率
                    current_ratio = latest.get('流动比率', 0)
                    if current_ratio is None or str(current_ratio) == 'nan':
                        current_ratio = 0

                    # 尝试获取利息保障倍数
                    interest_coverage = latest.get('利息支付倍数', 0)
                    if interest_coverage is None or str(interest_coverage) == 'nan':
                        interest_coverage = 0

                    # 尝试获取扣非净利润（元转为亿元）
                    deducted_net_profit = latest.get('扣除非经常性损益后的净利润(元)', 0)
                    if deducted_net_profit is None or str(deducted_net_profit) == 'nan':
                        deducted_net_profit = 0
                    deducted_net_profit = round(float(deducted_net_profit or 0) / 100000000, 2)

                    return {
                        'roe': round(float(roe or 0), 2),
                        'net_profit_growth': round(float(net_profit_growth or 0), 2),
                        'revenue_growth': round(float(revenue_growth or 0), 2),
                        'gross_margin': round(float(gross_margin or 0), 2),
                        'revenue': 0, 'cashflow': 0, 'debt_ratio': 0,
                        'current_ratio': round(float(current_ratio or 0), 2),
                        'interest_coverage': round(float(interest_coverage or 0), 2),
                        'deducted_net_profit': deducted_net_profit,
                        'dividend_yield': 0,
                        'data_quality': 'medium',
                        'source': 'akshare'
                    }
            except Exception as e:
                print(f"  akshare获取财务数据失败 {symbol}: {e}")

            # 如果akshare也失败，返回估算值
            return {
                'roe': 0, 'net_profit_growth': 0, 'revenue_growth': 0,
                'gross_margin': 0, 'revenue': 0, 'cashflow': 0, 'debt_ratio': 0,
                'dividend_yield': 0,
                'data_quality': 'low',  # 备用源质量标记
                'source': 'backup'
            }
        except Exception:
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

    def get_batch_market_data(self, limit: int = 300, prefer_top: bool = True, page: int = 0) -> List[Dict]:
        """批量获取市场数据（智能选择）

        Args:
            limit: 获取数量
            prefer_top: 是否优先选择成交额高的股票
            page: 页码，用于分页获取不同股票（每页limit个）
                     page > 0 时自动使用随机采样
        """
        stock_df = self.stock_list_fetcher.get_stock_list()

        # 基础过滤：沪深主板，排除ST
        main_stocks = stock_df[
            stock_df['code'].str.startswith(('6', '0')) &
            ~stock_df['name'].str.contains('ST', na=False)
        ]

        # page > 0 时强制使用随机采样，确保获取不同的股票
        if prefer_top and page == 0:
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
            # 使用页码作为随机种子的一部分，实现分页随机采样
            seed = 42 + page * 17  # 不同的质数乘数确保分页随机性
            sample = main_stocks.sample(n=min(limit, len(main_stocks)), random_state=seed)

        # 分批获取行情
        all_data = []
        batch_size = 50
        failed_batches = 0

        for i in range(0, len(sample), batch_size):
            batch = sample.iloc[i:i+batch_size]
            codes = batch['code'].tolist()
            try:
                market_data = self.market_fetcher.get_market_data(codes)
                if market_data:
                    all_data.extend(market_data)
                else:
                    failed_batches += 1
            except Exception as e:
                failed_batches += 1
                print(f"  批次获取失败 ({i//batch_size + 1}): {e}")
            time.sleep(0.05)  # 避免请求过快

        # 如果成功率太低，输出警告
        if failed_batches > 0 and len(all_data) == 0:
            print(f"  警告: 所有批次获取失败，共 {failed_batches} 个批次")

        return all_data

    def get_full_stock_data(self, limit: int = 100, prefer_top: bool = True, page: int = 0) -> List[Dict]:
        """获取完整股票数据（行情+财务）

        Args:
            limit: 获取数量
            prefer_top: 是否优先选择成交额高的股票
            page: 页码，用于分页获取不同股票
        """
        # 获取行情
        market_data = self.get_batch_market_data(limit, prefer_top, page=page)

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
            price = mkt.get('price', 0)
            # 计算股息率：如果有每股派息和股价，计算股息率 = 每股派息/股价*100
            dividend_per_share = fin.get('dividend_per_share', 0)
            dividend_yield = 0
            if price > 0 and dividend_per_share > 0:
                dividend_yield = round(dividend_per_share / price * 100, 2)

            data = {
                'code': code,
                'name': mkt.get('name', ''),
                'price': price,
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
                'dividend_yield': dividend_yield,
                'data_quality': fin.get('data_quality', 'low'),
                'data_source': mkt.get('source', 'unknown')
            }

            full_data.append(data)

            # 统计 - high和medium都算成功
            if fin.get('data_quality') in ('high', 'medium'):
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

# 全局实例（复用，线程安全）
_global_fetcher = None
_global_fetcher_lock = threading.Lock()

def get_stock_data_api(limit: int = 100, page: int = 0) -> List[Dict]:
    """便捷函数：获取股票数据

    Args:
        limit: 获取数量
        page: 页码，用于分页获取不同股票（每页limit个）
    """
    global _global_fetcher
    if _global_fetcher is None:
        with _global_fetcher_lock:
            if _global_fetcher is None:  # 双重检查锁定
                _global_fetcher = StockDataFetcher()
    return _global_fetcher.get_full_stock_data(limit, page=page)


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

    # 计算股息率：如果有每股派息和股价，计算股息率 = 每股派息/股价*100
    price = mkt.get('price', 0)
    dividend_per_share = fin.get('dividend_per_share', 0)
    dividend_yield = 0
    if price > 0 and dividend_per_share > 0:
        dividend_yield = round(dividend_per_share / price * 100, 2)

    return {
        'code': tencent_code,
        'name': mkt.get('name', ''),
        'price': price,
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
        'dividend_yield': dividend_yield,
        'data_quality': fin.get('data_quality', 'low'),
        'current_ratio': fin.get('current_ratio', 0),
        'interest_coverage': fin.get('interest_coverage', 0),
        'deducted_net_profit': fin.get('deducted_net_profit', 0),
    }
