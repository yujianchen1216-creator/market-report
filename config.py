"""项目配置"""
import os

# 代理设置 - 启用时 akshare 的东方财富源可以工作
PROXY_ENABLED = True
PROXY_HTTP = "http://127.0.0.1:7897"
PROXY_HTTPS = "http://127.0.0.1:7897"

# A股重要指数代码（新浪）
A_SHARE_INDICES = {
    "上证指数": "sh000001",
    "深证成指": "sz399001",
    "创业板指": "sz399006",
    "科创50":  "sh000688",
    "沪深300": "sh000300",
    "中证500": "sh000905",
    "上证50":  "sh000016",
    "中证1000":"sh000852",
}

# 全球指数代码（新浪）
# gb_$ = 美股, int_ = 国际市场, hk = 港股
GLOBAL_INDICES = {
    "道琼斯": "gb_$dji",
    "纳斯达克综合": "gb_$ixic",
    "标普500": "gb_$inx",
    "日经225": "int_nikkei",
    "韩国KOSPI": None,  # yfinance 备用
    "恒生指数": "hkHSI",
    "恒生科技指数": "hkHSCEI",
}

# 美股板块 ETF 代码（Yahoo Finance）
US_SECTOR_ETFS = {
    "金融": "XLF",
    "科技": "XLK",
    "能源": "XLE",
    "医疗": "XLV",
    "消费": "XLY",
    "工业": "XLI",
    "材料": "XLB",
    "公用事业": "XLU",
    "房地产": "XLRE",
}

# 重要 A 股权重股
A_SHARE_WEIGHTS = [
    "贵州茅台", "宁德时代", "招商银行", "中国平安",
    "东方财富", "中信证券", "五粮液", "比亚迪",
]

# 用户持仓板块（可配置，后续扩展为从文件读取）
USER_PORTFOLIO_SECTORS = []

# 报告输出目录
REPORT_DIR = os.path.join(os.path.dirname(__file__), "reports")
os.makedirs(REPORT_DIR, exist_ok=True)
