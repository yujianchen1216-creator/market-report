"""A股数据获取模块

数据源策略：
- 实时行情：新浪 API（直连，不需要代理）
- 指数历史：新浪（akshare 封装）
- 行业板块：同花顺（直连）
- 资金流向：东方财富（需要代理）
"""
import time
from typing import Dict, List, Optional
from datetime import datetime, timedelta

import pandas as pd

from config import A_SHARE_INDICES, A_SHARE_WEIGHTS
from utils.proxy import proxy_manager


class AShareData:
    """A股数据获取"""

    def __init__(self):
        self._sina_session = _SinaSession()

    def get_index_spot(self) -> pd.DataFrame:
        """获取A股主要指数实时行情（新浪源，直连）"""
        codes = list(A_SHARE_INDICES.values())
        df = self._sina_session.get_quotes(codes)
        if df is None or df.empty:
            # 降级到 akshare
            return self._get_index_spot_akshare()
        return df

    def get_index_daily(self, symbol: str = "sh000001", days: int = 60) -> pd.DataFrame:
        """获取指数日线历史数据

        Args:
            symbol: 指数代码，如 sh000001（上证指数）
            days: 获取最近 N 天数据
        """
        import akshare as ak
        df = ak.stock_zh_index_daily(symbol=symbol)
        if df is not None and not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
            df = df[df['date'] >= cutoff].reset_index(drop=True)
        return df

    def get_board_industry_summary(self, top_n: int = 10) -> Dict:
        """获取行业板块行情（同花顺源，直连）

        Returns:
            {"gainers": [...], "losers": [...], "count": int}
        """
        import akshare as ak
        result = {"gainers": [], "losers": [], "count": 0}

        try:
            df = ak.stock_board_industry_summary_ths()
            if df is not None and not df.empty:
                result["count"] = len(df)
                # 按涨跌幅降序排列
                df = df.sort_values("涨跌幅", ascending=False).reset_index(drop=True)
                cols = ["序号", "板块", "涨跌幅", "总成交量", "总成交额",
                        "上涨家数", "下跌家数", "领涨股", "领涨股-涨跌幅"]
                gainers = df.head(top_n)
                losers = df.tail(top_n).iloc[::-1]  # 跌幅大的在前
                result["gainers"] = gainers[cols].to_dict('records') if top_n > 0 else []
                result["losers"] = losers[cols].to_dict('records') if top_n > 0 else []
        except Exception as e:
            print(f"[行业板块] THS 失败: {e}")

        return result

    def get_board_concept_top(self, top_n: int = 10) -> Dict:
        """获取概念板块涨跌排行（同花顺源，直连）"""
        import akshare as ak
        result = {"gainers": [], "losers": []}

        try:
            df = ak.stock_board_concept_name_ths()
            if df is not None and not df.empty:
                # 同花顺概念板块只有列表，没有实时行情
                result["count"] = len(df)
        except Exception:
            pass

        return result

    def get_weight_stocks(self) -> pd.DataFrame:
        """获取A股权重股行情（直连新浪 API，快且准确）"""
        # 权重股的新浪代码映射
        weight_codes = {
            "sh600519": "贵州茅台", "sz300750": "宁德时代",
            "sh600036": "招商银行", "sh601318": "中国平安",
            "sz300059": "东方财富", "sh600030": "中信证券",
            "sz000858": "五粮液",   "sz002594": "比亚迪",
        }
        df = self._sina_session.get_quotes(list(weight_codes.keys()))
        if df is not None and not df.empty:
            return df
        return pd.DataFrame()

    def get_sector_fund_flow(self, top_n: int = 5) -> Dict:
        """获取行业板块资金流向

        东方财富源不可用，返回空数据（后续可通过其他方式补充）
        """
        return {"inflow": [], "outflow": [], "note": "东方财富API不可用，资金流向数据暂缺"}

    def get_northbound_flow(self) -> Optional[Dict]:
        """获取北向资金流向（东方财富API不可用）"""
        return None

    def _get_index_spot_akshare(self) -> pd.DataFrame:
        """降级方案：通过 akshare 获取指数行情"""
        import akshare as ak
        proxy_manager.disable_for_request()
        try:
            df = ak.stock_zh_a_spot()
            # 过滤指数（代码以 sh/sz 开头，名称为常见指数名）
            index_names = list(A_SHARE_INDICES.keys())
            filtered = df[df["名称"].isin(index_names)]
            return filtered
        finally:
            proxy_manager.restore_getproxies()


class _SinaSession:
    """新浪财经 API 直连封装（不需要代理）"""

    BASE_URL = "http://hq.sinajs.cn/list="

    def get_quotes(self, codes: List[str]) -> Optional[pd.DataFrame]:
        """批量获取行情

        Args:
            codes: 股票代码列表，如 ["sh000001", "sz399001"]
        """
        import urllib.request
        import ssl
        ssl._create_default_https_context = ssl._create_unverified_context

        url = self.BASE_URL + ",".join(codes)
        try:
            req = urllib.request.Request(url)
            req.add_header('Referer', 'https://finance.sina.com.cn')
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode('gbk')

            rows = []
            for line in raw.strip().split('\n'):
                if not line.strip():
                    continue
                try:
                    # 解析 var hq_str_sh000001="..." 格式
                    prefix, data = line.split('="', 1)
                    data = data.rstrip('";')
                    fields = data.split(',')
                    code = prefix.split('_')[-1]
                    name = fields[0]
                    # 新浪格式: name,open,prev_close,current,high,low,...
                    prev_close = float(fields[2]) if fields[2] else None
                    current_price = float(fields[3]) if fields[3] else None
                    change_pct = None
                    if prev_close and current_price and prev_close > 0:
                        change_pct = round((current_price - prev_close) / prev_close * 100, 2)
                    rows.append({
                        "代码": code,
                        "名称": name,
                        "最新价": current_price,
                        "涨跌幅": change_pct,
                        "今开": float(fields[1]) if fields[1] else None,
                        "昨收": prev_close,
                        "最高": float(fields[4]) if fields[4] else None,
                        "最低": float(fields[5]) if fields[5] else None,
                    })
                except (ValueError, IndexError) as e:
                    print(f"[Sina] 解析失败: {line[:50]}... {e}")
                    continue

            if rows:
                return pd.DataFrame(rows)
        except Exception as e:
            print(f"[Sina] 请求失败: {e}")

        return None

