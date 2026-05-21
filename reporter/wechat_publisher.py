"""微信公众号文章发布器

将生成的 Markdown 报告转换为公众号草稿（或自动发布）。

用法:
  from reporter.wechat_publisher import WeChatPublisher

  publisher = WeChatPublisher()
  publisher.publish_report(markdown_content)
"""
import json
import os
import sys
import struct
import zlib
import requests
from datetime import datetime
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".wechat_cache.json")


def _make_thumb_png() -> bytes:
    """生成 200x200 蓝色纯色 PNG 作为默认封面图"""
    width, height = 200, 200
    raw = b""
    for _ in range(height):
        raw += b"\x00"  # filter byte
        raw += b"\x00\x00\xff\xff" * width  # RGBA blue

    def chunk(t, d):
        c = t + d
        return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


class WeChatPublisher:
    """微信公众号 API 发布器"""

    API_BASE = "https://api.weixin.qq.com/cgi-bin"

    def __init__(self):
        self._appid = None
        self._secret = None
        self._mode = "draft"
        self._token = None
        self._thumb_media_id = None
        self._load_config()
        self._load_cache()

    def _load_config(self):
        """从配置文件加载密钥（优先环境变量，兼容 GitHub Actions Secrets）"""
        self._appid = os.environ.get("WECHAT_APPID") or ""
        self._secret = os.environ.get("WECHAT_APPSECRET") or ""
        self._mode = os.environ.get("PUBLISH_MODE") or "draft"
        if not self._appid:
            try:
                from wechat_config import WECHAT_APPID, WECHAT_APPSECRET, PUBLISH_MODE
                self._appid = WECHAT_APPID
                self._secret = WECHAT_APPSECRET
                self._mode = PUBLISH_MODE
            except ImportError:
                pass

    def _load_cache(self):
        """读取缓存的 media_id"""
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r") as f:
                    data = json.load(f)
                    self._thumb_media_id = data.get("thumb_media_id", "")
            except Exception:
                pass

    def _save_cache(self):
        """持久化缓存"""
        try:
            with open(CACHE_FILE, "w") as f:
                json.dump({"thumb_media_id": self._thumb_media_id}, f)
        except Exception:
            pass

    @property
    def is_configured(self) -> bool:
        return bool(self._appid and self._secret)

    def _get_access_token(self) -> Optional[str]:
        """获取 access_token"""
        if self._token:
            return self._token
        url = f"{self.API_BASE}/token"
        params = {"grant_type": "client_credential", "appid": self._appid, "secret": self._secret}
        try:
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            if "access_token" in data:
                self._token = data["access_token"]
                return self._token
            else:
                print(f"[WeChat] token 获取失败: {data}")
        except Exception as e:
            print(f"[WeChat] token 请求异常: {e}")
        return None

    @staticmethod
    def _escape(text: str) -> str:
        """HTML 转义"""
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    @staticmethod
    def _inline_format(text: str) -> str:
        """处理行内格式：**bold** 和 emoji 保持原样"""
        # 先 HTML 转义
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        # 处理 **bold** -> <strong>
        import re
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        return text

    def _markdown_to_wechat_html(self, md_content: str) -> str:
        """将 Markdown 转为公众号可用的极简 HTML

        微信只支持最基础的 HTML 标签，不能有复杂 CSS。
        """
        html_parts = []
        lines = md_content.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            if not line:
                i += 1
                continue
            if line == "---":
                html_parts.append("<hr/>")
                i += 1
                continue
            if line.startswith("# ") or line.startswith("## "):
                text = self._inline_format(line.lstrip("# ").strip())
                html_parts.append(f"<p><strong>{text}</strong></p>")
                i += 1
                continue
            if line.startswith("**") and line.endswith("**") and line.count("**") == 2:
                text = self._inline_format(line.strip("*"))
                html_parts.append(f"<p><strong>{text}</strong></p>")
                i += 1
                continue
            if line.startswith("- "):
                text = self._inline_format(line[2:])
                html_parts.append(f"<p>&nbsp;&nbsp;{text}</p>")
                i += 1
                continue
            if line.startswith("*") and line.endswith("*") and line.count("*") == 2:
                text = self._escape(line.strip("*"))
                html_parts.append(f"<p style=\"color:#888;font-size:13px;\">{text}</p>")
                i += 1
                continue
            text = self._inline_format(line)
            html_parts.append(f"<p>{text}</p>")
            i += 1

        return "\n".join(html_parts)

    def _get_thumb_media_id(self, token: str) -> Optional[str]:
        """获取封面图 media_id（缓存或上传）"""
        if self._thumb_media_id:
            return self._thumb_media_id
        try:
            png_data = _make_thumb_png()
            resp = requests.post(
                f"{self.API_BASE}/material/add_material?access_token={token}&type=image",
                files={"media": ("thumb.png", png_data, "image/png")},
                timeout=15,
            )
            data = resp.json()
            if "media_id" in data:
                self._thumb_media_id = data["media_id"]
                self._save_cache()
                return self._thumb_media_id
            print(f"[WeChat] 封面上传失败: {data}")
        except Exception as e:
            print(f"[WeChat] 封面上传异常: {e}")
        return None

    def create_draft(self, content: str, title: Optional[str] = None) -> Optional[str]:
        """创建公众号图文草稿

        Args:
            content: Markdown 报告内容
            title: 文章标题，默认自动生成

        Returns:
            media_id 成功则返回 media_id，否则 None
        """
        if not self.is_configured:
            print("[WeChat] 未配置 AppID/AppSecret，跳过发布")
            return None

        token = self._get_access_token()
        if not token:
            return None

        if title is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
            title = f"今日复盘 | {date_str}"

        # 获取封面图
        thumb_id = self._get_thumb_media_id(token)
        if not thumb_id:
            print("[WeChat] 无法获取封面图，跳过")
            return None

        html_content = self._markdown_to_wechat_html(content)

        body = {
            "articles": [
                {
                    "title": title,
                    "content": html_content,
                    "thumb_media_id": thumb_id,
                    "need_open_comment": 0,
                    "only_fans_can_comment": 0,
                }
            ]
        }

        try:
            resp = requests.post(
                f"{self.API_BASE}/draft/add?access_token={token}",
                json=body,
                timeout=30,
            )
            data = resp.json()
            if "media_id" in data:
                print(f"[WeChat] 草稿创建成功: media_id={data['media_id']}")
                return data["media_id"]
            else:
                print(f"[WeChat] 草稿创建失败: {data}")
        except Exception as e:
            print(f"[WeChat] 草稿请求异常: {e}")

        return None

    def publish_draft(self, media_id: str) -> bool:
        """发布草稿（仅服务号可用）

        Args:
            media_id: create_draft 返回的 media_id

        Returns:
            是否成功提交发布
        """
        if self._mode != "auto":
            print("[WeChat] 当前模式为 draft，需手动从公众号后台发布")
            return False

        token = self._get_access_token()
        if not token:
            return False

        url = f"{self.API_BASE}/freepublish/submit"
        body = {"media_id": media_id}

        try:
            resp = requests.post(
                f"{url}?access_token={token}",
                json=body,
                timeout=30,
            )
            data = resp.json()
            if data.get("errcode") == 0:
                print(f"[WeChat] 发布提交成功: publish_id={data.get('publish_id')}")
                return True
            else:
                print(f"[WeChat] 发布失败: {data}")
        except Exception as e:
            print(f"[WeChat] 发布请求异常: {e}")

        return False

    def publish_report(self, content: str, title: Optional[str] = None) -> bool:
        """完整流程：创建草稿 -> 可选自动发布

        Args:
            content: Markdown 报告内容
            title: 文章标题

        Returns:
            是否成功
        """
        if not self.is_configured:
            print("[WeChat] 未配置 AppID/AppSecret，跳过")
            return False

        media_id = self.create_draft(content, title)
        if not media_id:
            return False

        if self._mode == "auto":
            return self.publish_draft(media_id)

        print("[WeChat] 草稿已创建，请登录公众号后台手动发布")
        return True
