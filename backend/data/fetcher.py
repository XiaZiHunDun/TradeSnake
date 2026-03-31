"""
数据获取模块 - TradeSnake Data Fetcher
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
from typing import List, Dict, Optional
from datetime import datetime


class StockDataFetcher:
    """股票数据获取器"""

    def __init__(self):
        self.stock_list: Optional[pd.DataFrame] = None

    def get_stock_list(self) -> pd.DataFrame:
        """获取A股股票列表"""
        if self.stock_list is None:
            self.stock_list = ak.stock_info_a_code_name()
        return self.stock_list

    def get_market_data_tencent(self, codes: List[str]) -> List[Dict]:
        """腾讯API获取实时行情"""
        # 转换代码格式
        tencent_codes = []
        for code in codes:
            if code.startswith('6'):
                tencent_codes.append(f'sh{code}')
            else:
                tencent_codes.append(f'sz{code}')

        codes_str = ','.join(tencent_codes)
        url = f"https://qt.gtimg.cn/q={codes_str}"

        try:
            r = requests.get(url, timeout=15)
            r.encoding = 'gbk'
            return self._parse_tencent_data(r.text)
        except Exception as e:
            print(f"腾讯API获取失败: {e}")
            return []

    def _parse_tencent_data(self, data: str) -> List[Dict]:
        """解析腾讯行情数据"""
        stocks = []
        lines = data.strip().split('\n')
        for line in lines:
            match = re.search(r'v_(\w+)="(.+)"', line)
            if match:
                code = match.group(1)
                fields = match.group(2).split('~')
                if len(fields) > 40:
                    try:
                        stocks.append({
                            'code': code,
                            'name': fields[1],
                            'price': float(fields[3]) if fields[3] else 0,
                            'yesterday': float(fields[4]) if fields[4] else 0,
                            'pe': float(fields[39]) if fields[39] and fields[39] != '-' else 0,
                            'volume': int(fields[6]) if fields[6] else 0,
                        })
                    except:
                        pass
        return stocks

    def get_financial_data(self, symbol: str) -> Optional[Dict]:
        """获取单只股票财务数据（使用东方财富数据中心API）"""
        try:
            import requests

            # 判断市场
            if symbol.startswith('6'):
                market = 'SH'
            else:
                market = 'SZ'

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
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://data.eastmoney.com/"
            }

            r = requests.get(url, params=params, headers=headers, timeout=10)
            data = r.json()

            if data.get('result') and data['result'].get('data'):
                d = data['result']['data'][0]
                return {
                    'roe': round(float(d.get('WEIGHTAVG_ROE', 0) or 0), 2),
                    'net_profit_growth': round(float(d.get('SJLTZ', 0) or 0), 2),
                    'revenue_growth': round(float(d.get('YSTZ', 0) or 0), 2),
                }

            return {'roe': 0, 'net_profit_growth': 0, 'revenue_growth': 0}
        except Exception as e:
            print(f"财务数据获取失败 {symbol}: {e}")
            return {'roe': 0, 'net_profit_growth': 0, 'revenue_growth': 0}

    def get_batch_market_data(self, limit: int = 300) -> List[Dict]:
        """批量获取市场数据"""
        stock_df = self.get_stock_list()
        # 优先选择沪深主板（6开头和0开头的蓝筹股），排除ST和创业板早期股票
        main_stocks = stock_df[
            stock_df['code'].str.startswith(('6', '0')) &
            ~stock_df['name'].str.contains('ST', na=False)
        ]
        sample = main_stocks.sample(n=min(limit, len(main_stocks)), random_state=42)

        all_market_data = []
        batch_size = 50

        for i in range(0, len(sample), batch_size):
            batch = sample.iloc[i:i+batch_size]
            codes = batch['code'].tolist()
            market_data = self.get_market_data_tencent(codes)
            all_market_data.extend(market_data)

        return all_market_data

    def get_full_stock_data(self, limit: int = 100) -> List[Dict]:
        """获取完整股票数据（行情+财务）"""
        # 获取行情数据
        market_data = self.get_batch_market_data(limit)

        full_data = []
        for mkt in market_data:
            code = mkt['code']
            # 转换代码格式
            if code.startswith('sh'):
                symbol = code[2:]
            elif code.startswith('sz'):
                symbol = code[2:]
            else:
                continue

            # 获取财务数据
            fin = self.get_financial_data(symbol)

            data = {
                'code': code,
                'name': mkt['name'],
                'price': mkt['price'],
                'yesterday': mkt['yesterday'],
                'pe': mkt['pe'],
                'volume': mkt['volume'],
                'change_pct': ((mkt['price'] - mkt['yesterday']) / mkt['yesterday'] * 100) if mkt['yesterday'] > 0 else 0,
                'roe': fin['roe'] if fin else 0,
                'net_profit_growth': fin['net_profit_growth'] if fin else 0,
                'revenue_growth': fin['revenue_growth'] if fin else 0,
            }
            full_data.append(data)

            time.sleep(0.1)

        return full_data


def get_stock_data_api(limit: int = 100) -> List[Dict]:
    """便捷函数：获取股票数据"""
    fetcher = StockDataFetcher()
    return fetcher.get_full_stock_data(limit)


def get_single_stock_data(code: str) -> Optional[Dict]:
    """便捷函数：获取单只股票数据"""
    fetcher = StockDataFetcher()

    # 规范化代码格式（去掉sh/sz前缀）
    clean_code = code.upper()
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
    market_data = fetcher.get_market_data_tencent([clean_code])
    if not market_data:
        return None

    mkt = market_data[0]

    # 获取财务
    fin = fetcher.get_financial_data(clean_code)

    return {
        'code': tencent_code,
        'name': mkt['name'],
        'price': mkt['price'],
        'pe': mkt['pe'],
        'change_pct': ((mkt['price'] - mkt['yesterday']) / mkt['yesterday'] * 100) if mkt['yesterday'] > 0 else 0,
        'roe': fin['roe'] if fin else 0,
        'net_profit_growth': fin['net_profit_growth'] if fin else 0,
        'revenue_growth': fin['revenue_growth'] if fin else 0,
    }
