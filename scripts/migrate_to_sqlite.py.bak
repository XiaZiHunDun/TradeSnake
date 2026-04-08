"""
数据迁移脚本 - 从JSON迁移到SQLite (v17)

功能：
1. 迁移股票列表数据
2. 迁移财务数据
3. 迁移战力历史记录
4. 数据一致性校验

使用方法：
    python -m backend.core.migrate_to_sqlite [--dry-run] [--verify]
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Tuple

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.core.database import get_db
from backend.core.cp_engine import CPEngine, WEIGHTS

DATA_DIR = "/home/ailearn/projects/TradeSnake/data"
HISTORY_FILE = os.path.join(DATA_DIR, "cp_history.json")


def load_stock_list() -> List[Dict]:
    """加载股票列表"""
    stock_list_file = os.path.join(DATA_DIR, "stock_list_cache.json")
    if not os.path.exists(stock_list_file):
        print(f"❌ 股票列表文件不存在: {stock_list_file}")
        return []

    with open(stock_list_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 提取股票列表
    if isinstance(data, dict):
        stocks = data.get('data', data.get('stocks', []))
    else:
        stocks = data

    print(f"📊 加载股票列表: {len(stocks)} 只")
    return stocks


def load_financial_data(code: str) -> Dict:
    """加载单只股票财务数据"""
    # 统一code格式：去掉前缀0
    clean_code = code.replace('sz', '').replace('sh', '')
    fin_file = os.path.join(DATA_DIR, f"fin_{clean_code}_cache.json")

    if os.path.exists(fin_file):
        with open(fin_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('data', {})
    return {}


def load_market_data() -> Dict[str, Dict]:
    """加载市场行情数据"""
    market_stocks = {}

    for filename in os.listdir(DATA_DIR):
        if filename.startswith('market_') and filename.endswith('.json'):
            market_file = os.path.join(DATA_DIR, filename)
            try:
                with open(market_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    market_list = data.get('data', [])
                    for stock in market_list:
                        code = stock.get('code', '')
                        market_stocks[code] = stock
            except Exception as e:
                print(f"⚠️ 加载市场数据失败 {filename}: {e}")

    print(f"📊 加载市场数据: {len(market_stocks)} 只")
    return market_stocks


def merge_stock_data(stock_list: List[Dict], market_stocks: Dict) -> List[Dict]:
    """合并股票列表、财务数据、市场数据"""

    # 构建code到市场数据的映射
    market_map = {}
    for code, data in market_stocks.items():
        # 标准化code
        normalized = code.replace('sz', 'sz').replace('sh', 'sh')
        market_map[normalized] = data

    merged_stocks = []

    for stock in stock_list:
        code = stock.get('code', '')
        name = stock.get('name', '')

        # 优先使用市场数据中的信息
        market_data = market_map.get(code, {})

        # 加载财务数据
        fin_data = load_financial_data(code)

        # 合并数据
        merged = {
            'code': code,
            'name': name,
            'price': market_data.get('price', 0),
            'pe': market_data.get('pe', fin_data.get('pe', 0)),
            'roe': fin_data.get('roe', 0),
            'net_profit_growth': fin_data.get('net_profit_growth', 0),
            'revenue_growth': fin_data.get('revenue_growth', 0),
            'change_pct': market_data.get('change_pct', 0),
            'pb': market_data.get('pb', 0),
            'gross_margin': fin_data.get('gross_margin', 0),
            'revenue': fin_data.get('revenue', 0),
            'cashflow': fin_data.get('cashflow', 0),
            'debt_ratio': fin_data.get('debt_ratio', 0),
            'volume': market_data.get('volume', 0),
            'amount': market_data.get('amount', 0),
            'dividend_yield': fin_data.get('dividend_yield', 0),
            'market_cap': market_data.get('market_cap', 0),
            'high': market_data.get('high', 0),
            'low': market_data.get('low', 0),
            'data_quality': fin_data.get('data_quality', 'low'),
        }
        merged_stocks.append(merged)

    return merged_stocks


def calculate_cp_scores(stocks: List[Dict]) -> List[Dict]:
    """计算战力分数"""
    # 使用CPEngine计算
    from backend.core.cp_engine import CPEngine, create_stock_from_raw

    cp_engine = CPEngine()

    for stock in stocks:
        stock_cp = create_stock_from_raw(
            code=stock['code'],
            name=stock['name'],
            price=stock['price'],
            pe=stock['pe'],
            roe=stock['roe'],
            net_profit_growth=stock['net_profit_growth'],
            revenue_growth=stock['revenue_growth'],
            change_pct=stock['change_pct'],
            pb=stock['pb'],
            gross_margin=stock['gross_margin'],
            revenue=stock['revenue'],
            cashflow=stock['cashflow'],
            debt_ratio=stock['debt_ratio'],
            volume=stock['volume'],
            amount=stock['amount'],
            dividend_yield=stock['dividend_yield'],
            market_cap=stock['market_cap'],
            high=stock['high'],
            low=stock['low'],
            data_quality=stock['data_quality']
        )
        cp_engine.add_stock(stock_cp)

    # 计算所有分数
    cp_engine.calculate_all()

    # 转换为字典
    return [s.to_dict() for s in cp_engine.stocks]


def load_cp_history() -> Dict:
    """加载战力历史记录"""
    if not os.path.exists(HISTORY_FILE):
        print(f"⚠️ 历史记录文件不存在: {HISTORY_FILE}")
        return {}

    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        history = json.load(f)

    print(f"📊 加载战力历史: {len(history)} 天")
    return history


def migrate_stocks(db, dry_run: bool = False) -> Tuple[int, int]:
    """迁移股票数据"""
    print("\n" + "="*60)
    print("📦 迁移股票数据")
    print("="*60)

    # 1. 加载数据
    stock_list = load_stock_list()
    market_stocks = load_market_data()
    merged_stocks = merge_stock_data(stock_list, market_stocks)
    stocks_with_cp = calculate_cp_scores(merged_stocks)

    print(f"\n✅ 合并后股票数量: {len(stocks_with_cp)}")

    if dry_run:
        print("🔍 [DRY RUN] 跳过实际写入")
        return len(stocks_with_cp), 0

    # 2. 写入数据库
    count = db.batch_upsert_stocks(stocks_with_cp)
    print(f"✅ 写入数据库: {count} 条记录")

    return len(stocks_with_cp), count


def migrate_history(db, dry_run: bool = False) -> Tuple[int, int]:
    """迁移战力历史"""
    print("\n" + "="*60)
    print("📦 迁移战力历史记录")
    print("="*60)

    history = load_cp_history()
    if not history:
        return 0, 0

    total_records = 0
    if dry_run:
        for date, data in history.items():
            total_records += len(data.get('stocks', {}))
        print(f"🔍 [DRY RUN] 跳过实际写入，共 {total_records} 条历史记录")
        return total_records, 0

    # 写入每天的历史记录
    for date, data in sorted(history.items()):
        stocks = list(data.get('stocks', {}).values())
        count = db.record_cp_history(stocks, date)
        total_records += count
        print(f"  📅 {date}: {count} 条记录")

    print(f"✅ 写入历史记录: {total_records} 条")
    return total_records, total_records


def verify_migration(db, expected_stocks: int, expected_history: int) -> bool:
    """验证迁移结果"""
    print("\n" + "="*60)
    print("🔍 数据一致性校验")
    print("="*60)

    # 1. 检查股票数量
    actual_stocks = len(db.get_all_stocks())
    print(f"📊 股票数量: 预期 {expected_stocks}, 实际 {actual_stocks}", end="")
    if actual_stocks >= expected_stocks * 0.9:  # 允许10%误差
        print(" ✅")
    else:
        print(" ❌")

    # 2. 检查战力分布
    stocks = db.get_all_stocks()
    if stocks:
        cp_values = [s['total_cp'] for s in stocks]
        print(f"📈 战力分布: min={min(cp_values):.1f}, max={max(cp_values):.1f}, avg={sum(cp_values)/len(cp_values):.1f}")

    # 3. 检查历史记录
    top_stocks = db.get_top_stocks(10)
    if top_stocks:
        print(f"🏆 TOP10第一: {top_stocks[0]['name']}({top_stocks[0]['code']}) 战力 {top_stocks[0]['total_cp']:.1f}")

    # 4. 数据库信息
    cursor = db.conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM cp_history")
    history_count = cursor.fetchone()['count']
    print(f"📜 历史记录总数: {history_count}")

    return actual_stocks >= expected_stocks * 0.9


def main():
    import argparse
    parser = argparse.ArgumentParser(description='迁移数据到SQLite')
    parser.add_argument('--dry-run', action='store_true', help='仅预览不写入')
    parser.add_argument('--verify', action='store_true', help='执行校验')
    parser.add_argument('--skip-history', action='store_true', help='跳过历史记录迁移')
    args = parser.parse_args()

    print("="*60)
    print("🚀 TradeSnake v17 数据迁移工具")
    print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    db = get_db()

    # 检查是否已迁移
    version = db.get_schema_version()
    if version != '0' and not args.dry_run:
        print(f"\n⚠️ 数据库已迁移到版本 {version}")
        response = input("是否重新迁移？(y/N): ")
        if response.lower() != 'y':
            print("取消迁移")
            return

    # 执行迁移
    total_stocks, written_stocks = migrate_stocks(db, args.dry_run)

    total_history = 0
    written_history = 0
    if not args.skip_history:
        total_history, written_history = migrate_history(db, args.dry_run)

    # 更新版本
    if not args.dry_run:
        db.set_schema_version('v17.0')
        print(f"\n✅ 数据库版本已更新为 v17.0")

    # 验证
    if args.verify and not args.dry_run:
        success = verify_migration(db, written_stocks, written_history)
        if success:
            print("\n🎉 迁移成功！")
        else:
            print("\n⚠️ 迁移完成但数据异常，请检查")

    print(f"\n⏰ 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)


if __name__ == '__main__':
    main()
