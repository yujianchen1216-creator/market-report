"""市场分析引擎

整合多源数据，生成结构化的市场分析报告。
"""
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd


class MarketAnalyzer:
    """市场分析器"""

    def __init__(self, a_share_data, global_data):
        self.a_share = a_share_data
        self.global_data = global_data

    def generate_summary(self) -> Dict:
        """生成完整大盘总结"""
        index_df = self.a_share.get_index_spot()
        weights_df = self.a_share.get_weight_stocks()
        global_df = self.global_data.get_index_spot()
        northbound = self.a_share.get_northbound_flow()

        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "a_share_indices": self._summarize_indices(index_df),
            "weight_stocks": self._summarize_weights(weights_df),
            "global_indices": self._summarize_global(global_df),
            "northbound": northbound,
            "market_char": self._judge_market_character(index_df),
        }

    def analyze_sectors(self) -> Dict:
        """分析板块表现（同花顺源，直连）"""
        industries = self.a_share.get_board_industry_summary(top_n=10)
        concepts = self.a_share.get_board_concept_top()
        fund_flow = self.a_share.get_sector_fund_flow()
        return {
            "industries": industries,
            "concepts": concepts,
            "fund_flow": fund_flow,
        }

    def generate_portfolio_advice(self, user_sectors: List[str]) -> List[Dict]:
        """根据用户持仓板块生成建议

        基于行业板块涨跌幅、成交量等数据给出具体建议。
        """
        # 同花顺行业板块名称映射（用户常见叫法 -> THS 标准名）
        SECTOR_ALIAS = {
            "新能源汽车": "汽车整车",
            "新能源车": "汽车整车",
            "光伏": "光伏设备",
            "芯片": "半导体",
            "AI": "计算机应用",
            "人工智能": "计算机应用",
            "医药": "生物制品",
            "医疗": "生物制品",
            "军工": "军工装备",
            "锂电": "电池",
            "锂电池": "电池",
            "储能": "电力设备",
            "券商": "证券",
            "银行": "银行",
            "煤炭": "煤炭开采加工",
            "地产": "房地产开发",
            "房地产": "房地产开发",
            "保险": "保险及其他",
            "消费": "食品加工制造",
            "食品": "食品加工制造",
            "通信": "通信服务",
            "航运": "港口航运",
            "航空": "机场航运",
        }

        # 获取行业板块数据
        industry_data = self.a_share.get_board_industry_summary(top_n=90)
        all_sectors = (industry_data.get("gainers", []) +
                       industry_data.get("losers", []))

        # 建立板块 -> 数据 的查找表
        sector_map = {}
        for item in all_sectors:
            sector_map[item.get("板块", "")] = item

        results = []
        for sector in user_sectors:
            # 先精确匹配，再尝试别名映射
            info = sector_map.get(sector) or sector_map.get(SECTOR_ALIAS.get(sector))
            if info is None:
                results.append({
                    "板块": sector,
                    "涨跌幅": None,
                    "建议": "未找到该板块今日数据。",
                })
                continue

            chg = info.get("涨跌幅")
            volume = info.get("总成交量", 0)
            up_count = info.get("上涨家数", 0)
            down_count = info.get("下跌家数", 0)

            # 构建建议
            if chg is not None:
                if chg > 2:
                    advice = f"强势上涨({chg:+.2f}%)，成交量{volume}亿。短期偏强，可持有观察。"
                elif chg > 0:
                    advice = f"小幅上涨({chg:+.2f}%)，成交量{volume}亿。走势平稳，继续持有。"
                elif chg > -2:
                    advice = f"小幅回调({chg:+.2f}%)，成交量{volume}亿。正常调整，无需恐慌。"
                elif chg > -4:
                    advice = f"明显下跌({chg:+.2f}%)，成交量{volume}亿。短期承压，关注明日能否企稳。"
                else:
                    advice = f"大幅下跌({chg:+.2f}%)，成交量{volume}亿。风险释放中，不宜盲目抄底。"
            else:
                advice = "数据不足。"

            # 补充家数信息
            if up_count and down_count:
                total = up_count + down_count
                up_ratio = up_count / total * 100 if total > 0 else 0
                advice += f" 板块内上涨占比{up_ratio:.0f}%({up_count}/{total}家)。"

            results.append({
                "板块": sector,
                "涨跌幅": chg,
                "建议": advice,
            })

        return results

    def _summarize_indices(self, df: pd.DataFrame) -> List[Dict]:
        """提炼指数摘要"""
        if df.empty:
            return []
        results = []
        for _, row in df.iterrows():
            chg = row.get("涨跌幅")
            results.append({
                "name": row["名称"],
                "price": row.get("最新价"),
                "change_pct": chg,
                "direction": "up" if chg and chg > 0 else "down" if chg and chg < 0 else "flat",
            })
        return results

    def _summarize_weights(self, df: pd.DataFrame) -> List[Dict]:
        """提炼权重股表现"""
        if df.empty:
            return []
        return [
            {"name": r["名称"], "change_pct": r.get("涨跌幅")}
            for _, r in df.iterrows()
        ]

    def _summarize_global(self, df: pd.DataFrame) -> List[Dict]:
        """提炼全球指数"""
        if df.empty:
            return []
        return [
            {"name": r["名称"], "price": r.get("最新价"), "change_pct": r.get("涨跌幅")}
            for _, r in df.iterrows()
        ]

    def enrich_with_kronos(self, summary: Dict,
                           kronos_symbols: Optional[List[str]] = None) -> Dict:
        """用 Kronos AI 预测丰富报告数据

        Args:
            summary: generate_summary() 的输出
            kronos_symbols: 要预测的指数列表，默认四大指数
        Returns:
            添加了 kronos_predictions 字段的 summary
        """
        try:
            from analysis.kronos_analyzer import KronosAnalyzer
            ka = KronosAnalyzer(device="cpu")
            ka.load()
            if ka.is_ready:
                preds = ka.predict_indices(kronos_symbols)
                summary["kronos_predictions"] = preds
            else:
                summary["kronos_predictions"] = []
        except Exception as e:
            print(f"[Kronos] enrichment failed: {e}")
            summary["kronos_predictions"] = []
        return summary

    def _judge_market_character(self, df: pd.DataFrame) -> str:
        """判断市场特征"""
        if df.empty:
            return "数据不足"
        sh = df[df["名称"] == "上证指数"]
        if sh.empty:
            return "数据不足"
        chg = sh.iloc[0].get("涨跌幅")
        if chg is None:
            return "数据不足"
        if chg > 1:
            return "强势上涨"
        elif chg > 0:
            return "震荡偏强"
        elif chg > -1:
            return "震荡偏弱"
        elif chg > -2:
            return "明显下跌"
        else:
            return "大幅下跌"
