"""全球市场数据获取模块

数据源：
- 全球主要指数：新浪 API（直连，无需代理）
  - gb_$dji, gb_$ixic, gb_$inx (美股)
  - int_nikkei (日经)
  - hkHSI, hkHSCEI (港股)
  - KOSPI 使用 yfinance 备用
- 美股板块：新浪/akshare
"""
import time
from typing import Dict, Optional, List
import urllib.request
import ssl
import re

import pandas as pd

from config import GLOBAL_INDICES, US_SECTOR_ETFS


class GlobalMarketData:
    """全球市场数据获取"""

    def get_index_spot(self) -> pd.DataFrame:
        """获取全球主要指数实时行情（新浪源 + yfinance 补充）"""
        rows = []

        # 1. 从新浪获取
        sina_codes = [v for v in GLOBAL_INDICES.values() if v is not None]
        quotes = self._sina_quotes(sina_codes)

        for cn_name, code in GLOBAL_INDICES.items():
            if code is not None and code in quotes:
                d = quotes[code]
                rows.append({
                    "名称": cn_name,
                    "最新价": d.get('price'),
                    "涨跌幅": d.get('change_pct'),
                    "涨跌额": d.get('change'),
                    "昨收": d.get('prev_close'),
                    "最高": d.get('high'),
                    "最低": d.get('low'),
                })
            elif code is None:
                # 需要备用数据源
                result = self._yfinance_quote(cn_name)
                if result:
                    rows.append(result)

        return pd.DataFrame(rows) if rows else pd.DataFrame()

    def get_us_sector_etfs(self) -> pd.DataFrame:
        """获取美股板块 ETF 行情（新浪美股 + akshare 补充）"""
        # 如果用 proxy, 尝试 akshare 的美股行情
        try:
            import akshare as ak
            from utils.proxy import proxy_manager
            proxy_manager.enable()
            time.sleep(0.5)
            df = ak.stock_us_spot_em()
            if df is not None and not df.empty:
                proxy_manager.disable()
                return self._map_us_sectors(df)
        except Exception:
            pass
        finally:
            try:
                from utils.proxy import proxy_manager
                proxy_manager.disable()
            except:
                pass

        return pd.DataFrame()

    def _sina_quotes(self, codes: List[str]) -> Dict[str, Dict]:
        """从新浪获取行情（支持多种代码格式）"""
        ssl._create_default_https_context = ssl._create_unverified_context
        url = "http://hq.sinajs.cn/list=" + ",".join(codes)
        result = {}

        try:
            req = urllib.request.Request(url)
            req.add_header('Referer', 'https://finance.sina.com.cn')
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode('gbk')

            for line in raw.strip().split('\n'):
                if not line.strip():
                    continue
                try:
                    prefix, data = line.split('="', 1)
                    data = data.rstrip('";')
                    fields = data.split(',')
                    code = prefix.replace('var hq_str_', '')

                    if code.startswith('gb_$'):
                        # 美股格式: name,price,change_pct,time,change,...
                        result[code] = {
                            'name': fields[0],
                            'price': float(fields[1]) if fields[1] else None,
                            'change_pct': float(fields[2]) if fields[2] else None,
                            'change': float(fields[4]) if len(fields) > 4 and fields[4] else None,
                            'prev_close': float(fields[7]) if len(fields) > 7 and fields[7] else None,
                            'high': float(fields[5]) if len(fields) > 5 and fields[5] else None,
                            'low': float(fields[6]) if len(fields) > 6 and fields[6] else None,
                            'time': fields[3] if len(fields) > 3 else None,
                        }
                    elif code.startswith('int_'):
                        # 国际市场: name,price,change,change_pct
                        result[code] = {
                            'name': fields[0],
                            'price': float(fields[1]) if fields[1] else None,
                            'change_pct': float(fields[3]) if len(fields) > 3 and fields[3] else None,
                            'change': float(fields[2]) if len(fields) > 2 and fields[2] else None,
                        }
                    elif code.startswith('hk'):
                        # 港股格式: name,cn_name,open,price,high,low,prev_close,change,change_pct,...
                        result[code] = {
                            'name': fields[1] if fields[1] else fields[0],
                            'price': float(fields[3]) if fields[3] else None,
                            'change': float(fields[7]) if len(fields) > 7 and fields[7] else None,
                            'change_pct': float(fields[8]) if len(fields) > 8 and fields[8] else None,
                            'high': float(fields[4]) if len(fields) > 4 and fields[4] else None,
                            'low': float(fields[5]) if len(fields) > 5 and fields[5] else None,
                            'prev_close': float(fields[6]) if len(fields) > 6 and fields[6] else None,
                            'time': fields[16] if len(fields) > 16 else None,
                        }
                except (ValueError, IndexError) as e:
                    print(f"[Sina] 解析失败: {line[:60]}... {e}")
                    continue

        except Exception as e:
            print(f"[Sina] 请求失败: {e}")

        return result

    def _yfinance_quote(self, market_name: str) -> Optional[Dict]:
        """通过 yfinance 获取指数行情（备用）"""
        import yfinance as yf

        yf_map = {
            "韩国KOSPI": "^KS11",
            "日经225": "^N225",
            "恒生指数": "^HSI",
        }
        ticker = yf_map.get(market_name)
        if not ticker:
            return None

        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="5d")
            if not hist.empty:
                close = hist['Close'].iloc[-1]
                prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else close
                change = close - prev_close
                change_pct = (change / prev_close) * 100 if prev_close else 0
                return {
                    "名称": market_name,
                    "最新价": round(close, 2),
                    "涨跌幅": round(change_pct, 2),
                    "涨跌额": round(change, 2),
                }
        except Exception as e:
            print(f"[yfinance] {market_name} 失败: {e}")
            time.sleep(3)

        return None

    def _map_us_sectors(self, df) -> pd.DataFrame:
        """从美股全行情中过滤出板块 ETF"""
        etf_tickers = list(US_SECTOR_ETFS.values())
        etf_names = {v: k for k, v in US_SECTOR_ETFS.items()}
        filtered = df[df['代码'].isin(etf_tickers)].copy()
        if filtered.empty:
            return pd.DataFrame()
        filtered['板块'] = filtered['代码'].map(etf_names)
        filtered['涨跌幅'] = filtered.get('涨跌幅', 0)
        return filtered[['板块', '代码', '最新价', '涨跌幅']].rename(
            columns={'代码': 'ETF代码'}
        )
