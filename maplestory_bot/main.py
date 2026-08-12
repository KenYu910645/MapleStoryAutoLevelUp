"""冒险岛怀旧服自动挂机工具 - 入口文件。

运行方式::

    python main.py
"""

from __future__ import annotations

import os
import signal
import sys

# 将项目根目录加入 sys.path，保证 ``from config import ...`` 等导入可用
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def _check_dependencies() -> bool:
    """检查关键依赖是否安装，缺失则给出友好提示。"""
    missing = []
    try:
        import cv2  # noqa: F401
    except ImportError:
        missing.append("opencv-python")
    try:
        import numpy  # noqa: F401
    except ImportError:
        missing.append("numpy")
    try:
        import PyQt5  # noqa: F401
    except ImportError:
        missing.append("PyQt5")
    try:
        import win32gui  # noqa: F401  (仅 Windows)
    except ImportError:
        missing.append("pywin32")
    if missing:
        print("=" * 60)
        print("缺少以下依赖:")
        for m in missing:
            print(f"  - {m}")
        print("请运行: pip install -r requirements.txt")
        print("=" * 60)
        return False
    return True


def main() -> int:
    if not _check_dependencies():
        return 1

    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import Qt

    # 高 DPI 自适应
    try:
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    except AttributeError:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName("MapleStoryBot")

    # Ctrl-C 优雅退出
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    from ui.main_window import MainWindow
    window = MainWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
