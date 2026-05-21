"""生成完整复盘报告"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from data.a_share import AShareData
from data.global_market import GlobalMarketData
from analysis.market_analyzer import MarketAnalyzer
from reporter.wechat_template import render_report, save_report
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
            summary = analyzer.enrich_with_kronos(summary)
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


def main():
    content, filepath = generate(include_kronos=True)
    print(f"\n{content}")


if __name__ == "__main__":
    main()
