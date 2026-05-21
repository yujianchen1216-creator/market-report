"""微信公众号文章模板生成

输出格式为 WeChat-compatible HTML 和 Markdown。
"""
from typing import Dict, List, Optional
from datetime import datetime


def render_report(summary: Dict, sector_analysis: Dict, portfolio_advice: List[Dict]) -> str:
    """生成完整的公众号文章（Markdown 格式）

    Args:
        summary: 大盘总结（来自 MarketAnalyzer）
        sector_analysis: 板块分析
        portfolio_advice: 持仓建议
    Returns:
        Markdown 文本（可复制到公众号编辑器）
    """
    lines = []
    date_str = summary.get("date", datetime.now().strftime("%Y-%m-%d"))
    weekday = datetime.now().strftime("%A")

    # 标题
    lines.append(f"# 今日复盘 | {date_str} {weekday}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 一、大盘走势
    lines.append("## 一、大盘走势")
    lines.append("")
    char = summary.get("market_char", "")
    lines.append(f"**市场特征：{char}**")
    lines.append("")

    for idx in summary.get("a_share_indices", []):
        name = idx["name"]
        price = idx["price"]
        chg = idx["change_pct"]
        if chg is not None:
            arrow = "📈" if chg > 0 else "📉"
            lines.append(f"- {arrow} **{name}**: {price:.2f} （{chg:+.2f}%）")
        else:
            lines.append(f"- {name}: N/A")

    lines.append("")

    # 权重股
    weights = summary.get("weight_stocks", [])
    if weights:
        lines.append("**权重股表现：**")
        up = [w for w in weights if w.get("change_pct") and w["change_pct"] > 0]
        down = [w for w in weights if w.get("change_pct") and w["change_pct"] < 0]
        if up:
            up_names = "、".join([f"{w['name']}({w['change_pct']:+.2f}%)" for w in up[:3]])
            lines.append(f"- 上涨：{up_names}")
        if down:
            down_names = "、".join([f"{w['name']}({w['change_pct']:+.2f}%)" for w in down[:3]])
            lines.append(f"- 下跌：{down_names}")
        lines.append("")

    # 二、AI 智能预测（Kronos）
    kronos_preds = summary.get("kronos_predictions", [])
    kronos_sector_preds = summary.get("kronos_sector_predictions", [])
    if kronos_preds or kronos_sector_preds:
        lines.append("---")
        lines.append("## 二、AI 智能预测（Kronos）")
        lines.append("")

    if kronos_preds:
        lines.append("**主要指数预测：**")
        lines.append("")
        for p in kronos_preds:
            name = p.get("name", p.get("symbol", "?"))
            curr = p.get("current", 0)
            pred = p.get("prediction", [])
            trend = p.get("trend", "")
            signal = p.get("signal", "")
            trend_pct = p.get("trend_pct", 0)
            if pred:
                target = pred[-1]
                arrow = "📈" if signal in ("看涨", "偏多") else "📉"
                lines.append(f"- {arrow} **{name}**: {curr:.2f} → {target:.2f}（{trend_pct:+.2f}%）")
                lines.append(f"  · 趋势：{trend} | 信号：{signal}")
        lines.append("")

    if kronos_sector_preds:
        lines.append("**你的持仓板块预测：**")
        lines.append("")
        for p in kronos_sector_preds:
            name = p.get("name", p.get("symbol", "?"))
            curr = p.get("current", 0)
            pred = p.get("prediction", [])
            trend = p.get("trend", "")
            signal = p.get("signal", "")
            trend_pct = p.get("trend_pct", 0)
            if pred:
                target = pred[-1]
                arrow = "📈" if signal in ("看涨", "偏多") else "📉"
                lines.append(f"- {arrow} **{name}**: {curr:.2f} → {target:.2f}（{trend_pct:+.2f}%）")
                lines.append(f"  · 趋势：{trend} | 信号：{signal}")
        lines.append("")

    # 三、板块轮动
    lines.append("---")
    lines.append("## 三、板块轮动")
    lines.append("")

    industries = sector_analysis.get("industries", {})
    gainers = industries.get("gainers", [])
    losers = industries.get("losers", [])
    total = industries.get("count", 0)

    if total:
        lines.append(f"全市场 **{total}** 个行业板块中有涨有跌。")
        lines.append("")

    if gainers:
        lines.append("**涨幅居前板块：**")
        lines.append("")
        for g in gainers:
            name = g.get("板块", "?")
            chg = g.get("涨跌幅", "N/A")
            vol = g.get("总成交量", "N/A")
            leader = g.get("领涨股", "")
            leader_chg = g.get("领涨股-涨跌幅", "")
            chg_str = f"{chg:+.2f}%" if isinstance(chg, (int, float)) else f"{chg}%"
            lines.append(f"- **{name}** {chg_str} | 成交量{vol}亿 | 领涨: {leader}({leader_chg}%)")
        lines.append("")

    if losers:
        lines.append("**跌幅居前板块：**")
        lines.append("")
        for l in losers:
            name = l.get("板块", "?")
            chg = l.get("涨跌幅", "N/A")
            vol = l.get("总成交量", "N/A")
            chg_str = f"{chg:+.2f}%" if isinstance(chg, (int, float)) else f"{chg}%"
            lines.append(f"- **{name}** {chg_str} | 成交量{vol}亿")
        lines.append("")

    # 资金流向
    fund_flow = sector_analysis.get("fund_flow", {})
    inflow = fund_flow.get("inflow", [])
    outflow = fund_flow.get("outflow", [])
    if inflow:
        lines.append("**主力资金流入板块：**")
        for i, f in enumerate(inflow[:3], 1):
            lines.append(f"  {i}. {f.get('名称', '?')} （净流入{f.get('主力净流入', 'N/A')}）")
        lines.append("")
    if outflow:
        lines.append("**主力资金流出板块：**")
        for i, f in enumerate(outflow[:3], 1):
            lines.append(f"  {i}. {f.get('名称', '?')} （净流出{f.get('主力净流入', 'N/A')}）")
        lines.append("")

    # 四、外围市场（影响次日A股）
    lines.append("---")
    lines.append("## 四、外围市场（影响次日A股）")
    lines.append("")

    for gi in summary.get("global_indices", []):
        name = gi["name"]
        chg = gi.get("change_pct")
        if chg is not None:
            arrow = "📈" if chg > 0 else "📉"
            lines.append(f"- {arrow} **{name}**: {gi.get('price', 'N/A'):.2f}（{chg:+.2f}%）")
        else:
            lines.append(f"- {name}: N/A")
    lines.append("")

    # 北向资金
    nb = summary.get("northbound")
    if nb:
        lines.append(f"**北向资金：** 净流入/流出数据待补充")
        lines.append("")

    # 五、持仓建议
    if portfolio_advice:
        lines.append("---")
        lines.append("## 五、你的持仓板块操作建议")
        lines.append("")
        for adv in portfolio_advice:
            lines.append(f"**{adv['板块']}**：{adv['建议']}")
            lines.append("")

    # 风险提示
    lines.append("---")
    lines.append("*风险提示：以上分析仅供参考，不构成投资建议。市场有风险，投资需谨慎。*")
    lines.append("")
    lines.append(f"*报告生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

    return "\n".join(lines)


def render_premarket_report(global_indices: List[Dict],
                            kronos_pred: Optional[Dict] = None,
                            sector_preds: Optional[List[Dict]] = None) -> str:
    """生成盘前指引报告

    在 A 股开盘前发送，包含隔夜全球市场和 Kronos AI 预测。

    Args:
        global_indices: 全球指数数据
        kronos_pred: Kronos 对 上证指数 的预测
        sector_preds: Kronos 对持仓板块的预测
    Returns:
        Markdown 文本
    """
    lines = []
    date_str = datetime.now().strftime("%Y-%m-%d")
    weekday = datetime.now().strftime("%A")

    lines.append(f"# 盘前指引 | {date_str} {weekday}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 一、隔夜外围市场
    lines.append("## 一、隔夜外围市场")
    lines.append("")

    us_names = {"道琼斯", "纳斯达克综合", "标普500"}
    asia_names = {"日经225", "韩国KOSPI", "恒生指数", "恒生科技指数"}

    lines.append("**美股收盘：**")
    lines.append("")
    for gi in global_indices:
        name = gi.get("name", "")
        if name in us_names:
            chg = gi.get("change_pct")
            if chg is not None:
                arrow = "📈" if chg > 0 else "📉"
                lines.append(f"- {arrow} **{name}**: {gi.get('price', 0):.2f}（{chg:+.2f}%）")
    lines.append("")

    lines.append("**亚太市场（交易中）：**")
    lines.append("")
    for gi in global_indices:
        name = gi.get("name", "")
        if name in asia_names:
            chg = gi.get("change_pct")
            if chg is not None:
                arrow = "📈" if chg > 0 else "📉"
                lines.append(f"- {arrow} **{name}**: {gi.get('price', 0):.2f}（{chg:+.2f}%）")
    lines.append("")

    # 二、今日A股预测
    lines.append("---")
    lines.append("## 二、今日A股预测（Kronos AI）")
    lines.append("")

    if kronos_pred:
        name = kronos_pred.get("name", "上证指数")
        curr = kronos_pred.get("current", 0)
        pred = kronos_pred.get("prediction", [])
        trend = kronos_pred.get("trend", "")
        signal = kronos_pred.get("signal", "")
        trend_pct = kronos_pred.get("trend_pct", 0)
        if pred:
            target = pred[-1]
            arrow = "📈" if signal in ("看涨", "偏多") else "📉"
            lines.append(f"{arrow} **{name}**：{curr:.2f} → {target:.2f}")
            lines.append("")
            lines.append(f"- 预测趋势：{trend}")
            lines.append(f"- 预测涨跌幅：{trend_pct:+.2f}%")
            lines.append(f"- 信号强度：{signal}")
    else:
        lines.append("（Kronos 模型未加载，跳过预测）")
    lines.append("")

    # 持仓板块预测
    if sector_preds:
        lines.append("**你的持仓板块预测：**")
        lines.append("")
        for p in sector_preds:
            name = p.get("name", p.get("symbol", "?"))
            trend = p.get("trend", "")
            signal = p.get("signal", "")
            trend_pct = p.get("trend_pct", 0)
            arrow = "📈" if signal in ("看涨", "偏多") else "📉"
            lines.append(f"- {arrow} **{name}**: {trend}（{trend_pct:+.2f}%）信号：{signal}")
        lines.append("")

    # 风险提示
    lines.append("---")
    lines.append("*风险提示：以上分析仅供参考，不构成投资建议。市场有风险，投资需谨慎。*")
    lines.append("")
    lines.append(f"*报告生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

    return "\n".join(lines)


def save_report(content: str, filepath: Optional[str] = None) -> str:
    """保存报告到文件

    Args:
        content: Markdown 内容
        filepath: 输出路径，默认自动生成
    Returns:
        文件路径
    """
    import os
    if filepath is None:
        date_str = datetime.now().strftime("%Y%m%d_%H%M")
        filepath = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "reports", f"report_{date_str}.md"
        )
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath
