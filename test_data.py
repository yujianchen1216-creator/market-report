"""
测试 akshare 数据获取能力 - 增加 Windows 代理处理
"""
import sys
import os
import winreg
from contextlib import contextmanager


@contextmanager
def temp_disable_proxy():
    """临时禁用 Windows 系统代理，退出时恢复"""
    key_path = r'Software\Microsoft\Windows\CurrentVersion\Internet Settings'
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE)
        original_enable, _ = winreg.QueryValueEx(key, 'ProxyEnable')
        original_server, _ = winreg.QueryValueEx(key, 'ProxyServer')
        winreg.SetValueEx(key, 'ProxyEnable', 0, winreg.REG_DWORD, 0)
        winreg.CloseKey(key)
    except Exception as e:
        print(f"代理禁用失败: {e}")
        original_enable = 0
        original_server = ""

    # 覆盖 env 变量
    saved_env = {}
    for k in ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"]:
        saved_env[k] = os.environ.pop(k, None)
    os.environ["NO_PROXY"] = "*"

    # 覆盖 urllib
    import urllib.request
    saved_getproxies = urllib.request.getproxies
    urllib.request.getproxies = lambda: {}

    try:
        yield
    finally:
        # 恢复代理
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, 'ProxyEnable', 0, winreg.REG_DWORD, original_enable)
            winreg.CloseKey(key)
        except:
            pass
        # 恢复 env 变量
        for k, v in saved_env.items():
            if v is not None:
                os.environ[k] = v
        urllib.request.getproxies = saved_getproxies


# 进入测试环境时自动禁用代理
with temp_disable_proxy():
    import akshare as ak
    import pandas as pd

    # 验证代理已被禁用
    import urllib.request
    print("当前代理状态:", urllib.request.getproxies())

    def test_a_share_index():
        print("\n===== A股主要指数 =====")
        df = ak.stock_zh_index_spot_em()
        cols = ["序号", "名称", "最新价", "涨跌幅", "涨跌额", "成交量", "成交额"]
        indices = ["上证指数", "深证成指", "创业板指", "科创50", "沪深300", "中证500", "上证50", "中证1000"]
        df_filtered = df[df["名称"].isin(indices)][cols]
        print(df_filtered.to_string(index=False))

    def test_board_industry():
        print("\n===== 行业板块涨跌 Top 10 =====")
        df = ak.stock_board_industry_name_em()
        print(f"行业板块总数: {len(df)}")
        df_spot = ak.stock_board_industry_spot_em()
        cols = ["板块名称", "最新价", "涨跌幅", "涨跌额", "总市值", "换手率", "上涨家数", "下跌家数"]
        print("\n--- 涨幅前10 ---")
        print(df_spot.head(10)[cols].to_string(index=False))
        print("\n--- 跌幅前10 ---")
        print(df_spot.tail(10)[cols].to_string(index=False))

    def test_concept_board():
        print("\n===== 概念板块涨跌 Top 5 =====")
        df = ak.stock_board_concept_spot_em()
        cols = ["板块名称", "最新价", "涨跌幅", "涨跌额", "总市值", "换手率"]
        print("\n--- 涨幅前5 ---")
        print(df.head(5)[cols].to_string(index=False))
        print("\n--- 跌幅前5 ---")
        print(df.tail(5)[cols].to_string(index=False))

    def test_sector_fund_flow():
        print("\n===== 行业板块资金流向（今日） =====")
        df = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流向")
        print("\n--- 流入前5 ---")
        print(df.head(5).to_string(index=False))
        print("\n--- 流出前5 ---")
        print(df.tail(5).to_string(index=False))

    def test_northbound():
        print("\n===== 北向资金概况 =====")
        try:
            df = ak.stock_hsgt_fund_flow_summary_em()
            print(df.to_string(index=False))
        except Exception as e:
            print(f"北向1失败: {e}")
            try:
                df = ak.stock_hsgt_hist_em()
                print("近5日北向资金:")
                print(df.tail(5).to_string(index=False))
            except Exception as e2:
                print(f"北向2也失败: {e2}")

    def test_global_indices():
        print("\n===== 全球主要指数 =====")
        df = ak.stock_info_global_em()
        cols = ["名称", "最新价", "涨跌幅", "涨跌额"]
        targets = [
            "道琼斯", "纳斯达克综合", "标普500",
            "日经225", "韩国KOSPI", "韩国KOSDAQ",
            "恒生指数", "恒生科技指数",
        ]
        for t in targets:
            match = df[df["名称"].str.contains(t, na=False)]
            if not match.empty:
                print(match[cols].head(1).to_string(index=False))

    def test_margin():
        print("\n===== 融资融券余额 =====")
        try:
            df = ak.stock_margin_sse()
            if df is not None and not df.empty:
                print("上交所融资融券（近3日）:")
                print(df.tail(3).to_string(index=False))
        except Exception as e:
            print(f"上交所两融失败: {e}")
        try:
            df2 = ak.stock_margin_szse()
            if df2 is not None and not df2.empty:
                print("深交所融资融券（近3日）:")
                print(df2.tail(3).to_string(index=False))
        except Exception as e:
            print(f"深交所两融失败: {e}")

    def test_individual_stocks():
        print("\n===== A股权重股 =====")
        df = ak.stock_zh_a_spot_em()
        cols = ["序号", "名称", "最新价", "涨跌幅", "涨跌额", "成交量", "成交额", "换手率", "市盈率-动态"]
        targets = ["贵州茅台", "宁德时代", "招商银行", "东方财富", "中国平安", "中信证券"]
        df_filtered = df[df["名称"].isin(targets)][cols]
        print(df_filtered.to_string(index=False))


    if __name__ == "__main__":
        print("=" * 60)
        print("akshare 数据获取测试")
        print("版本:", ak.__version__)
        print("Python:", sys.version)
        print("=" * 60)

        test_a_share_index()
        test_board_industry()
        test_concept_board()
        test_sector_fund_flow()
        test_northbound()
        test_global_indices()
        test_margin()
        test_individual_stocks()

        print("\n" + "=" * 60)
        print("测试完成")
        print("=" * 60)
