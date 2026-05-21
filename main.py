"""
市场数据获取演示入口
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from data.a_share import AShareData
from data.global_market import GlobalMarketData
from config import GLOBAL_INDICES


def main():
    print("=" * 70)
    print("[市场数据获取演示]")
    print("=" * 70)

    a_share = AShareData()
    global_market = GlobalMarketData()

    # 1. A股主要指数
    print("\n[ A股主要指数 ]")
    df = a_share.get_index_spot()
    if not df.empty:
        for _, row in df.iterrows():
            chg = row.get('涨跌幅')
            chg_s = f"{chg:+.2f}%" if chg is not None else "N/A"
            pri = row.get('最新价')
            pri_s = f"{pri:.2f}" if pri is not None else "N/A"
            print(f"  {row['名称']}: {pri_s} ({chg_s})")

    # 2. 全球主要指数
    print("\n[ 全球主要指数 ]")
    df_g = global_market.get_index_spot()
    if not df_g.empty:
        for _, row in df_g.iterrows():
            chg = row.get('涨跌幅')
            chg_s = f"{chg:+.2f}%" if chg is not None else "N/A"
            pri = row.get('最新价')
            pri_s = f"{pri:.2f}" if pri is not None else "N/A"
            print(f"  {row['名称']}: {pri_s} ({chg_s})")

    # 3. A股权重股
    print("\n[ A股权重股 ]")
    df_w = a_share.get_weight_stocks()
    if df_w is not None and not df_w.empty:
        for _, row in df_w.iterrows():
            chg = row.get('涨跌幅')
            chg_s = f"{chg:+.2f}%" if pd.notna(chg) and chg is not None else "N/A"
            pri = row.get('最新价')
            pri_s = f"{pri:.2f}" if pri is not None else "N/A"
            print(f"  {row['名称']}: {pri_s} ({chg_s})")

    # 4. 行业板块列表
    print("\n[ 行业板块 ]")
    df_b = a_share.get_board_industry()
    if not df_b.empty:
        print(f"  共 {len(df_b)} 个行业板块")

    # 5. 概念板块（需代理）
    print("\n[ 概念板块（需代理）]")
    concepts = a_share.get_board_concept_top()
    if concepts.get("gainers"):
        for item in concepts["gainers"][:5]:
            print(f"  涨: {item.get('板块名称', '?')}: {item.get('涨跌幅', 'N/A')}%")
    else:
        print("  (东方财富源不可用，需启动 Clash 代理)")

    print("\n" + "=" * 70)
    print("演示完成")
    print("=" * 70)


import pandas as pd

if __name__ == "__main__":
    main()
