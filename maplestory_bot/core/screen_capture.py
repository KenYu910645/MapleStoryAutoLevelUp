"""屏幕截图模块。

使用 Win32 API 的 ``PrintWindow`` / ``BitBlt`` 捕获游戏窗口画面，并转为
OpenCV 可用的 numpy 数组（BGR 顺序）。
"""

from __future__ import annotations

from typing import Optional

import numpy as np


class ScreenCapture:
    """游戏窗口截图。"""

    # PrintWindow 标志：PW_RENDERFULLCONTENT（用于捕获 DirectX/硬件加速内容）
    PW_RENDERFULLCONTENT = 0x00000002

    @staticmethod
    def capture(hwnd: int) -> Optional[np.ndarray]:
        """捕获指定窗口客户区，返回 BGR numpy 数组；失败返回 None。"""
        try:
            import win32gui  # type: ignore
            import win32ui  # type: ignore
            import win32con  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("screen_capture 需要 pywin32，请运行 pip install pywin32") from e

        if not hwnd:
            return None

        try:
            left, top, right, bottom = win32gui.GetClientRect(hwnd)
        except Exception:
            return None

        width = right - left
        height = bottom - top
        if width <= 0 or height <= 0:
            return None

        hwnd_dc = None
        mfc_dc = None
        save_dc = None
        bitmap = None
        try:
            hwnd_dc = win32gui.GetWindowDC(hwnd)
            mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
            save_dc = mfc_dc.CreateCompatibleDC()

            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
            save_dc.SelectObject(bitmap)

            # 优先 PrintWindow（可捕获被遮挡/硬件加速内容）
            result = win32gui.PrintWindow(hwnd, save_dc.GetSafeHdc(),
                                           ScreenCapture.PW_RENDERFULLCONTENT)
            if result != 1:
                # 回退 BitBlt
                save_dc.BitBlt((0, 0), (width, height), mfc_dc, (0, 0),
                               win32con.SRCCOPY)

            bitmap_info = bitmap.GetInfo()
            bitmap_str = bitmap.GetBitmapBits(True)
            img = np.frombuffer(bitmap_str, dtype=np.uint8)
            if img.size != bitmap_info["bmHeight"] * bitmap_info["bmWidth"] * 4:
                return None
            img = img.reshape(bitmap_info["bmHeight"],
                              bitmap_info["bmWidth"], 4)
            img = img[:, :, :3]  # 丢弃 alpha，保留 BGR
            img = np.ascontiguousarray(img)
            return img
        except Exception:
            return None
        finally:
            # 释放 GDI 资源，避免内存泄漏
            try:
                if save_dc is not None:
                    save_dc.DeleteDC()
            except Exception:
                pass
            try:
                if mfc_dc is not None:
                    mfc_dc.DeleteDC()
            except Exception:
                pass
            try:
                if hwnd_dc is not None and hwnd:
                    import win32gui  # type: ignore
                    win32gui.ReleaseDC(hwnd, hwnd_dc)
            except Exception:
                pass
            try:
                if bitmap is not None:
                    import win32gui  # type: ignore
                    win32gui.DeleteObject(bitmap.GetHandle())
            except Exception:
                pass

    @staticmethod
    def capture_region(hwnd: int, x: int, y: int, w: int, h: int
                        ) -> Optional[np.ndarray]:
        """捕获客户区内指定子区域 ``(x, y, w, h)``。"""
        full = ScreenCapture.capture(hwnd)
        if full is None:
            return None
        H, W = full.shape[:2]
        x0 = max(0, min(int(x), W - 1))
        y0 = max(0, min(int(y), H - 1))
        x1 = max(x0 + 1, min(int(x + w), W))
        y1 = max(y0 + 1, min(int(y + h), H))
        return full[y0:y1, x0:x1].copy()
