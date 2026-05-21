"""代理管理工具

处理 Windows 系统代理的启用/禁用，以及 akshare 对代理的依赖。
东方财富 (em) 源需要代理才能访问，新浪/同花顺源可以直连。
"""
import os
import winreg
import urllib.request

# 注册表路径
IE_PROXY_KEY = r'Software\Microsoft\Windows\CurrentVersion\Internet Settings'


class ProxyManager:
    """Windows 系统代理管理器"""

    def __init__(self, proxy_addr="127.0.0.1:7897"):
        self.proxy_addr = proxy_addr
        self._saved_getproxies = None

    @property
    def is_enabled(self) -> bool:
        """检查系统代理是否启用"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, IE_PROXY_KEY, 0, winreg.KEY_READ)
            enabled, _ = winreg.QueryValueEx(key, 'ProxyEnable')
            winreg.CloseKey(key)
            return bool(enabled)
        except Exception:
            return False

    def enable(self):
        """启用系统代理"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, IE_PROXY_KEY, 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, 'ProxyEnable', 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, 'ProxyServer', 0, winreg.REG_SZ, self.proxy_addr)
            winreg.CloseKey(key)
        except Exception as e:
            print(f"[代理] 启用失败: {e}")

        # 恢复环境变量代理
        self._apply_env_proxy()

    def disable(self):
        """禁用系统代理"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, IE_PROXY_KEY, 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, 'ProxyEnable', 0, winreg.REG_DWORD, 0)
            winreg.CloseKey(key)
        except Exception as e:
            print(f"[代理] 禁用失败: {e}")

        # 清除环境变量代理
        self._clear_env_proxy()

    def disable_for_request(self):
        """在请求前禁用代理的临时措施"""
        self._clear_env_proxy()
        # 覆盖 urllib 的代理检测
        self._saved_getproxies = urllib.request.getproxies
        urllib.request.getproxies = lambda: {}

    def restore_getproxies(self):
        """恢复 urllib 代理检测"""
        if self._saved_getproxies:
            urllib.request.getproxies = self._saved_getproxies
            self._saved_getproxies = None

    def _apply_env_proxy(self):
        """设置环境变量代理"""
        os.environ['HTTP_PROXY'] = f'http://{self.proxy_addr}'
        os.environ['HTTPS_PROXY'] = f'http://{self.proxy_addr}'
        os.environ['http_proxy'] = f'http://{self.proxy_addr}'
        os.environ['https_proxy'] = f'http://{self.proxy_addr}'

    def _clear_env_proxy(self):
        """清除环境变量代理"""
        for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
            os.environ.pop(key, None)
        os.environ['NO_PROXY'] = '*'
        os.environ['no_proxy'] = '*'


# 全局单例
proxy_manager = ProxyManager()
