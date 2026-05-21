"""生成完整复盘报告"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from data.a_share import AShareData
from data.global_market import GlobalMarketData
from analysis.market_analyzer import MarketAnalyzer
from reporter.wechat_template import render_report, render_premarket_report, save_report
from datetime import datetime

# 优先从 user_config 读取，兼容旧 config
try:
    from user_config import USER_PORTFOLIO_SECTORS, ENABLE_KRONOS  # type: ignore
except ImportError:
    from config import USER_PORTFOLIO_SECTORS
    ENABLE_KRONOS = True


def generate(include_kronos=True):
    """生成完整报告，返回 (content, filepath)"""
    print(f"[{datetime.now():%H:%M}] 报告生成器 - 获取数据...")

    a_share = AShareData()
    global_market = GlobalMarketData()
    analyzer = MarketAnalyzer(a_share, global_market)

    print("  -> 大盘数据...")
    summary = analyzer.generate_summary()

    if include_kronos:
        print("  -> AI 预测（Kronos）...")
        try:
            user_sectors = USER_PORTFOLIO_SECTORS or ["半导体", "证券", "白酒"]
            summary = analyzer.enrich_with_kronos(summary, sector_names=user_sectors)
        except Exception as e:
            print(f"  Kronos 失败（跳过）: {e}")

    print("  -> 板块数据...")
    sectors = analyzer.analyze_sectors()

    print("  -> 持仓建议...")
    user_sectors = USER_PORTFOLIO_SECTORS or ["半导体", "证券", "白酒"]
    advice = analyzer.generate_portfolio_advice(user_sectors)

    print("  -> 生成报告...")
    content = render_report(summary, sectors, advice)
    filepath = save_report(content)
    print(f"  报告已保存: {filepath}")
    return content, filepath


def generate_premarket():
    """生成盘前指引报告

    在 A 股开盘前 10 分钟发送，包含隔夜全球市场和 Kronos AI 预测。
    """
    print(f"[{datetime.now():%H:%M}] 盘前指引 - 获取数据...")

    a_share = AShareData()
    global_market = GlobalMarketData()
    analyzer = MarketAnalyzer(a_share, global_market)

    # 1. 全球市场数据
    print("  -> 全球市场数据...")
    global_df = global_market.get_index_spot()
    global_indices = analyzer._summarize_global(global_df) if not global_df.empty else []

    # 2. Kronos 预测
    print("  -> AI 预测（Kronos）...")
    kronos_pred = None
    sector_preds = None
    try:
        from analysis.kronos_analyzer import KronosAnalyzer
        ka = KronosAnalyzer(device="cpu")
        ka.load()
        if ka.is_ready:
            kronos_pred = ka.predict_index("sh000001")
            # 板块预测
            user_sectors = USER_PORTFOLIO_SECTORS or ["半导体", "证券", "白酒"]
            sector_preds = []
            for sector in user_sectors:
                from analysis.market_analyzer import SECTOR_ALIAS
                mapped = SECTOR_ALIAS.get(sector, sector)
                try:
                    pred = ka.predict_sector(mapped)
                    if pred:
                        pred["name"] = sector
                        sector_preds.append(pred)
                except Exception as e:
                    print(f"  板块预测失败 {sector}: {e}")
    except Exception as e:
        print(f"  Kronos 失败（跳过）: {e}")

    # 3. 生成报告
    print("  -> 生成报告...")
    content = render_premarket_report(global_indices, kronos_pred, sector_preds)
    filepath = save_report(content)
    print(f"  报告已保存: {filepath}")
    return content, filepath


def main():
    content, filepath = generate(include_kronos=True)
    print(f"\n{content}")


if __name__ == "__main__":
    main()
