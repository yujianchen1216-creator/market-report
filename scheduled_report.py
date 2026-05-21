"""定时任务入口 - 被 Windows 任务计划程序调用

用法:
  python scheduled_report.py midday    -> A股午盘 (11:30)
  python scheduled_report.py aclose    -> A股收盘 (15:00)
  python scheduled_report.py usclose   -> 美股收盘 (次日早 7:00)
"""
import sys
import os
from datetime import datetime

# 确保能在任务计划程序中找到项目
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from generate_report import generate
from reporter.wechat_template import save_report

LOG_DIR = os.path.join(BASE_DIR, "reports")
os.makedirs(LOG_DIR, exist_ok=True)

# 标题前缀
TITLE_PREFIX = {
    "midday": "A股午盘速览",
    "aclose": "A股收盘复盘",
    "usclose": "美股收盘简报",
}


def log(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(os.path.join(LOG_DIR, "scheduler.log"), "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {msg}\n")
    print(f"[{timestamp}] {msg}")


def run_report(report_type: str):
    log(f"开始生成报告 [{report_type}]")
    try:
        include_kronos = report_type != "midday"
        content, filepath = generate(include_kronos=include_kronos)
        log(f"报告完成 [{report_type}]: {filepath}")

        # 推送微信公众号
        try:
            from reporter.wechat_publisher import WeChatPublisher
            publisher = WeChatPublisher()
            if publisher.is_configured:
                prefix = TITLE_PREFIX.get(report_type, "市场报告")
                date_str = datetime.now().strftime("%Y-%m-%d")
                title = f"{prefix} | {date_str}"
                ok = publisher.publish_report(content, title=title)
                log(f"微信公众号推送 {'成功' if ok else '跳过（未配置）'}")
        except Exception as e:
            log(f"微信公众号推送失败: {e}")

    except Exception as e:
        log(f"报告失败 [{report_type}]: {e}")
        raise


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python scheduled_report.py [midday|aclose|usclose]")
        sys.exit(1)

    report_type = sys.argv[1]
    if report_type not in ("midday", "aclose", "usclose"):
        print(f"未知报告类型: {report_type}")
        sys.exit(1)

    run_report(report_type)
