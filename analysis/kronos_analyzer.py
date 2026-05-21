"""Kronos AI 模型集成 - K线预测分析

使用 Kronos-small 模型对A股板块/指数进行短期走势预测。
"""
import sys
import os
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

# 添加 Kronos 路径
KRONOS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Kronos-ai")
MODEL_PATH = os.path.join(KRONOS_PATH, "models")
sys.path.insert(0, KRONOS_PATH)

# 常用指数代码映射
INDEX_MAP = {
    "sh000001": "上证指数",
    "sz399001": "深证成指",
    "sz399006": "创业板指",
    "sh000688": "科创50",
    "sh000300": "沪深300",
    "sh000016": "上证50",
    "sh000905": "中证500",
}


class KronosAnalyzer:
    """Kronos AI 分析器 - 用于板块/指数 K 线预测"""

    def __init__(self, device: str = "cpu"):
        self.device = device
        self._predictor = None
        self._tokenizer = None
        self._model = None
        self._ready = False

    def load(self):
        """加载模型和 tokenizer（优先本地，否则从 HuggingFace Hub 加载）"""
        if self._ready:
            return

        try:
            from model import Kronos, KronosTokenizer, KronosPredictor

            # 优先加载本地模型，否则从 HuggingFace Hub 拉取
            model_dir = os.path.join(MODEL_PATH, "Kronos-small")
            tokenizer_dir = os.path.join(MODEL_PATH, "Kronos-Tokenizer-base")
            model_id = "NeoQuasar/Kronos-small"
            tokenizer_id = "NeoQuasar/Kronos-Tokenizer-base"

            if os.path.isdir(model_dir):
                print(f"[Kronos] 加载本地模型: {model_dir}")
                self._tokenizer = KronosTokenizer.from_pretrained(tokenizer_dir)
                self._model = Kronos.from_pretrained(model_dir)
            else:
                print(f"[Kronos] 从 HuggingFace 下载模型: {model_id}")
                self._tokenizer = KronosTokenizer.from_pretrained(tokenizer_id)
                self._model = Kronos.from_pretrained(model_id)
            self._predictor = KronosPredictor(
                self._model, self._tokenizer,
                device=self.device, max_context=512
            )
            self._ready = True
            print(f"[Kronos] 模型加载完成 (device={self.device})")
        except Exception as e:
            print(f"[Kronos] 模型加载失败: {e}")

    @property
    def is_ready(self) -> bool:
        return self._ready

    def predict_indices(self, symbols: List[str] = None,
                        days_lookback: int = 60,
                        days_pred: int = 5) -> List[Dict]:
        """批量预测多个指数

        Args:
            symbols: 指数代码列表，默认预测四大指数
            days_lookback: 回看天数
            days_pred: 预测天数
        Returns:
            每个指数的预测结果列表
        """
        if symbols is None:
            symbols = ["sh000001", "sz399001", "sz399006", "sh000688"]
        results = []
        for sym in symbols:
            result = self.predict_index(sym, days_lookback, days_pred)
            if result:
                results.append(result)
        return results

    def predict_index(self, symbol: str = "sh000001",
                      days_lookback: int = 60,
                      days_pred: int = 5) -> Optional[Dict]:
        """预测指数未来走势

        Args:
            symbol: 指数代码 (如 sh000001 上证指数)
            days_lookback: 使用多少天历史数据
            days_pred: 预测未来几天

        Returns:
            {"symbol":, "name":, "current":, "prediction": [...], "trend":, "signal":}
        """
        if not self._ready:
            self.load()
        if not self._ready:
            return None

        # 获取历史数据
        df = self._get_index_data(symbol, days_lookback + days_pred)
        if df is None or len(df) < days_lookback:
            return None

        recent = df.tail(days_lookback).copy()

        # 准备 Kronos 输入（转为 Series，因为 Kronos 需要 .dt 访问器）
        timestamps = pd.Series(recent.index)
        x_df = recent[['open', 'high', 'low', 'close', 'volume']].copy()

        try:
            last_date = timestamps.iloc[-1]
            pred_df = self._predictor.predict(
                df=x_df,
                x_timestamp=timestamps,
                y_timestamp=pd.Series(pd.date_range(
                    start=last_date + timedelta(days=1),
                    periods=days_pred, freq='D'
                )),
                pred_len=days_pred,
                T=0.8,
                top_p=0.9,
                sample_count=1,
                verbose=False
            )

            if pred_df is None or pred_df.empty:
                return None

            # 解析预测结果
            current_close = recent['close'].iloc[-1]
            pred_close = pred_df['close'].values if 'close' in pred_df else None

            if pred_close is None or len(pred_close) == 0:
                return None

            # 判断趋势
            last_pred = pred_close[-1]
            trend_pct = (last_pred - current_close) / current_close * 100

            if trend_pct > 2:
                signal = "看涨"
                trend = "上涨"
            elif trend_pct > 0.5:
                signal = "偏多"
                trend = "震荡偏强"
            elif trend_pct > -0.5:
                signal = "中性"
                trend = "震荡"
            elif trend_pct > -2:
                signal = "偏空"
                trend = "震荡偏弱"
            else:
                signal = "看跌"
                trend = "下跌"

            return {
                "symbol": symbol,
                "name": INDEX_MAP.get(symbol, symbol),
                "current": current_close,
                "prediction": [round(float(x), 2) for x in pred_close],
                "trend": trend,
                "trend_pct": round(trend_pct, 2),
                "signal": signal,
            }

        except Exception as e:
            print(f"[Kronos] 预测失败 ({symbol}): {e}")

        return None

    def predict_sector(self, sector_name: str,
                       days_lookback: int = 60,
                       days_pred: int = 5) -> Optional[Dict]:
        """预测行业板块走势

        通过同花顺板块代码获取板块指数 K 线数据
        """
        try:
            import akshare as ak
            # 获取板块代码
            df_names = ak.stock_board_industry_name_ths()
            match = df_names[df_names['name'] == sector_name]
            if match.empty:
                # 模糊匹配
                match = df_names[df_names['name'].str.contains(sector_name, na=False)]
            if match.empty:
                return None

            board_code = match.iloc[0]['code']
            print(f"[Kronos] 板块 {sector_name} 代码: {board_code}")

            # 获取板块指数历史数据
            df_idx = ak.stock_board_industry_index_ths(symbol=board_code)
            if df_idx is None or df_idx.empty:
                return None

            # 重命名列为标准 OHLCV
            df_idx = df_idx.rename(columns={
                'date': '日期', 'open': 'open', 'high': 'high',
                'low': 'low', 'close': 'close', 'volume': 'volume'
            })
            df_idx = df_idx.set_index('日期')
            df_idx.index = pd.to_datetime(df_idx.index)

            cutoff = pd.Timestamp.now() - pd.Timedelta(days=days_lookback + 10)
            df_idx = df_idx[df_idx.index >= cutoff]

            if len(df_idx) < days_lookback:
                print(f"[Kronos] 板块数据不足: {len(df_idx)} < {days_lookback}")
                return None

            recent = df_idx.tail(days_lookback).copy()
            timestamps = pd.Series(recent.index)
            x_df = recent[['open', 'high', 'low', 'close', 'volume']].copy()

            if not self._ready:
                self.load()
            if not self._ready:
                return None

            last_date = timestamps.iloc[-1]
            pred_df = self._predictor.predict(
                df=x_df,
                x_timestamp=timestamps,
                y_timestamp=pd.Series(pd.date_range(
                    start=last_date + timedelta(days=1),
                    periods=days_pred, freq='D'
                )),
                pred_len=days_pred,
                T=0.8, top_p=0.9,
                sample_count=1, verbose=False
            )

            if pred_df is None or pred_df.empty:
                return None

            current_close = recent['close'].iloc[-1]
            pred_close = pred_df['close'].values
            last_pred = pred_close[-1]
            trend_pct = (last_pred - current_close) / current_close * 100

            signal = "看涨" if trend_pct > 2 else "偏多" if trend_pct > 0.5 else \
                     "中性" if trend_pct > -0.5 else "偏空" if trend_pct > -2 else "看跌"

            trend = ("上涨" if trend_pct > 2 else "震荡偏强" if trend_pct > 0.5 else
                     "震荡" if trend_pct > -0.5 else "震荡偏弱" if trend_pct > -2 else "下跌")
            return {
                "symbol": sector_name,
                "current": current_close,
                "prediction": [round(float(x), 2) for x in pred_close],
                "trend": trend,
                "trend_pct": round(trend_pct, 2),
                "signal": signal,
            }

        except Exception as e:
            print(f"[Kronos] 板块预测失败 ({sector_name}): {e}")

        return None

    def _get_index_data(self, symbol: str, days: int) -> Optional[pd.DataFrame]:
        """获取指数日线数据（取足够多的日历天数以确保有 days 个交易日）"""
        try:
            import akshare as ak
            df = ak.stock_zh_index_daily(symbol=symbol)
            if df is None or df.empty:
                return None
            df = df.set_index('date')
            df.index = pd.to_datetime(df.index)
            # 取 2.5 倍日历天数，确保有足够交易日
            cutoff = pd.Timestamp.now() - pd.Timedelta(days=int(days * 2.5))
            df = df[df.index >= cutoff]
            if len(df) < days:
                print(f"[Kronos] 数据不足: {len(df)} < {days}，尝试扩大范围")
                # 扩大范围，取全部数据
                df = ak.stock_zh_index_daily(symbol=symbol)
                df = df.set_index('date')
                df.index = pd.to_datetime(df.index)
            return df
        except Exception as e:
            print(f"[Kronos] 获取数据失败 ({symbol}): {e}")
        return None
