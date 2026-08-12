"""输入模拟模块。

提供两种按键模式：
- ``keybd_event``  前台模拟（需要游戏窗口在前台）
- ``PostMessage``  后台模拟（向指定窗口句柄发送按键消息，窗口可后台）

按键字符串支持：
- 单字符：``"a"``、``"x"``、``"1"``、``"F1"`` 等
- 方向键名称：``"left"`` / ``"right"`` / ``"up"`` / ``"down"``
- 控制键名称：``"shift"`` / ``"ctrl"`` / ``"alt"`` / ``"space"``
"""

from __future__ import annotations

import time
from typing import Optional

# 名称 -> Windows 虚拟键码
_VK_NAMES = {
    "left": 0x25,   # VK_LEFT
    "up": 0x26,     # VK_UP
    "right": 0x27,  # VK_RIGHT
    "down": 0x28,   # VK_DOWN
    "shift": 0x10,  # VK_SHIFT
    "ctrl": 0x11,   # VK_CONTROL
    "alt": 0x12,    # VK_MENU
    "space": 0x20,  # VK_SPACE
    "enter": 0x0D,  # VK_RETURN
    "tab": 0x09,    # VK_TAB
    "esc": 0x1B,    # VK_ESCAPE
    "home": 0x24,   # VK_HOME
    "end": 0x23,    # VK_END
    "pageup": 0x21, # VK_PRIOR
    "pagedown": 0x22, # VK_NEXT
    "insert": 0x2D, # VK_INSERT
    "delete": 0x2E, # VK_DELETE
    "backspace": 0x08, # VK_BACK
}

# F1-F12
for _i in range(1, 13):
    _VK_NAMES[f"f{_i}"] = 0x70 + _i - 1


class InputSimulator:
    """键盘输入模拟器。"""

    # ------------------------------------------------------------------ 按键映射
    @staticmethod
    def char_to_vk(key: Optional[str]) -> Optional[int]:
        """将按键字符串转为 Windows 虚拟键码。"""
        if not key:
            return None
        s = key.strip().lower()
        if not s:
            return None
        if s in _VK_NAMES:
            return _VK_NAMES[s]
        if len(s) == 1:
            try:
                import win32api  # type: ignore
                return win32api.VkKeyScan(s) & 0xFF
            except ImportError:
                # 退化为 ASCII（对字母/数字基本可用）
                return ord(s.upper())
        return None

    # ------------------------------------------------------------------ 前台
    @staticmethod
    def press_key_foreground(key: Optional[str],
                              duration: float = 0.05) -> bool:
        """使用 keybd_event 模拟前台按键。"""
        try:
            import win32api  # type: ignore
            import win32con  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("input_simulator 需要 pywin32，请运行 pip install pywin32") from e

        vk = InputSimulator.char_to_vk(key)
        if vk is None:
            return False
        try:
            win32api.keybd_event(vk, 0, 0, 0)
            time.sleep(max(0.001, duration))
            win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------ 后台
    @staticmethod
    def press_key_background(hwnd: int, key: Optional[str]) -> bool:
        """使用 PostMessage 向指定窗口后台发送按键。"""
        try:
            import win32gui  # type: ignore
            import win32con  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("input_simulator 需要 pywin32，请运行 pip install pywin32") from e

        if not hwnd:
            return False
        vk = InputSimulator.char_to_vk(key)
        if vk is None:
            return False
        try:
            # lParam: 高16位=重复次数(1)，低16位=扫描码(简化为0)
            lparam_down = 1 | (0 << 16)
            lparam_up = 1 | (0xC000 << 16)  # 释放时 bit 30/31 置位
            win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, vk, lparam_down)
            time.sleep(0.02)
            win32gui.PostMessage(hwnd, win32con.WM_KEYUP, vk, lparam_up)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------ 统一接口
    @staticmethod
    def press_key(key: Optional[str],
                  hwnd: Optional[int] = None,
                  use_postmessage: bool = False,
                  duration: float = 0.05) -> bool:
        """统一按键接口。

        Args:
            key: 按键字符串。
            hwnd: 目标窗口句柄（后台模式必填）。
            use_postmessage: True 用 PostMessage 后台按键；False 用 keybd_event 前台按键。
            duration: 前台按键按下时长（秒）。
        """
        if use_postmessage:
            if not hwnd:
                return InputSimulator.press_key_foreground(key, duration)
            return InputSimulator.press_key_background(hwnd, key)
        return InputSimulator.press_key_foreground(key, duration)

    @staticmethod
    def hold_key(key: Optional[str], seconds: float,
                 hwnd: Optional[int] = None,
                 use_postmessage: bool = False) -> bool:
        """长按某键 ``seconds`` 秒（用于角色移动）。"""
        try:
            import win32api  # type: ignore
            import win32con  # type: ignore
            import win32gui  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("input_simulator 需要 pywin32") from e

        vk = InputSimulator.char_to_vk(key)
        if vk is None:
            return False
        if use_postmessage and hwnd:
            try:
                steps = max(1, int(seconds / 0.05))
                for _ in range(steps):
                    win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, vk, 0)
                    time.sleep(0.05)
                win32gui.PostMessage(hwnd, win32con.WM_KEYUP, vk, 0)
                return True
            except Exception:
                return False
        else:
            try:
                win32api.keybd_event(vk, 0, 0, 0)
                time.sleep(max(0.0, seconds))
                win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)
                return True
            except Exception:
                return False
