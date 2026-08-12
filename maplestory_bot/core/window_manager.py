"""窗口管理模块。

使用 Win32 API 枚举系统窗口，支持按标题关键字搜索和选中游戏窗口。
"""

from __future__ import annotations

from typing import List, Tuple


class WindowManager:
    """枚举并选择系统窗口。"""

    def __init__(self) -> None:
        self._windows: List[Tuple[int, str]] = []

    # ------------------------------------------------------------------ 枚举
    def enum_windows(self) -> List[Tuple[int, str]]:
        """枚举所有可见且具有标题的顶级窗口。

        Returns:
            形如 ``[(hwnd, title), ...]`` 的列表。
        """
        try:
            import win32gui  # type: ignore
        except ImportError as e:  # pragma: no cover - 仅 Windows 可用
            raise RuntimeError("window_manager 需要 pywin32，请运行 pip install pywin32") from e

        self._windows = []

        def _callback(hwnd: int, _) -> bool:
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    self._windows.append((hwnd, title))
            return True

        win32gui.EnumWindows(_callback, None)
        return list(self._windows)

    def search_windows(self, keyword: str) -> List[Tuple[int, str]]:
        """按标题关键字过滤窗口（大小写不敏感）。"""
        if not keyword:
            return self.enum_windows()
        keyword_lower = keyword.lower()
        all_windows = self.enum_windows()
        return [(h, t) for h, t in all_windows if keyword_lower in t.lower()]

    # ------------------------------------------------------------------ 选择
    @staticmethod
    def select_window(hwnd: int) -> bool:
        """选中指定窗口句柄。返回是否成功。"""
        try:
            import win32gui  # type: ignore
        except ImportError:  # pragma: no cover
            return False
        try:
            if not win32gui.IsWindow(hwnd):
                return False
            win32gui.SetForegroundWindow(hwnd)
            return True
        except Exception:
            return False

    @staticmethod
    def get_window_rect(hwnd: int) -> Tuple[int, int, int, int]:
        """返回窗口矩形 (left, top, right, bottom)。"""
        import win32gui  # type: ignore
        return win32gui.GetWindowRect(hwnd)

    @staticmethod
    def get_client_rect(hwnd: int) -> Tuple[int, int, int, int]:
        """返回客户区矩形 (left, top, right, bottom)，均相对窗口左上角。"""
        import win32gui  # type: ignore
        return win32gui.GetClientRect(hwnd)

    @staticmethod
    def bring_to_foreground(hwnd: int) -> None:
        """将窗口置前。"""
        try:
            import win32gui  # type: ignore
            win32gui.ShowWindow(hwnd, 9)  # SW_RESTORE
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass
