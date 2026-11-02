"""画线功能实证验证（真实 PowerPoint 环境）。

流程：COM 打开 demo.pptx 放映 → Ctrl+P 激活笔 → 按住左键拖一条线 → 松开 →
截图对比（红色笔迹应出现）→ 结束放映。
结论直接回答"按住-拖动能否在 PPT 放映里画线"（排查 pipeline 之外的嫌疑）。
用法：D:\\Anaconda\\envs\\gesture\\python.exe tools\\verify_writing.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pyautogui
import pythoncom
import win32com.client

from src.config import PROJECT_ROOT


def main() -> int:
    pptx = PROJECT_ROOT / "demo.pptx"
    if not pptx.exists():
        print("demo.pptx 不存在，先运行 tools/make_demo_ppt.py")
        return 1

    pythoncom.CoInitialize()
    app = win32com.client.Dispatch("PowerPoint.Application")
    pres = app.Presentations.Open(str(pptx), WithWindow=True)
    pres.SlideShowSettings.Run()
    time.sleep(2.5)  # 等放映全屏起来
    # 强制放映窗口到前台（实测：全屏游戏等会抢占前台，Ctrl+P 会发错地方）
    import win32gui

    def _raise_slideshow():
        def cb(hwnd, _):
            if "PowerPoint Slide Show" in win32gui.GetWindowText(hwnd):
                win32gui.SetForegroundWindow(hwnd)
        win32gui.EnumWindows(cb, None)

    _raise_slideshow()
    time.sleep(0.5)
    # 点击放映窗口获取焦点（会前进一页，属预期）
    sw, sh = pyautogui.size()
    pyautogui.click(sw * 0.5, sh * 0.6)
    time.sleep(0.5)

    pyautogui.hotkey("ctrl", "p")  # 笔模式
    time.sleep(0.5)
    pyautogui.screenshot().save(PROJECT_ROOT / "logs" / "writing_before.png")

    # 用项目的笔级 API 画一条斜线（mouse_event MOVE|ABSOLUTE，实证确认可用）
    from src.control.keyboard import KeyboardController

    kb = KeyboardController(check_foreground=False)
    sw, sh = pyautogui.size()
    kb.pen_down(sw * 0.3, sh * 0.3)
    for i in range(30):
        kb.pen_move(sw * (0.3 + 0.4 * i / 29), sh * (0.3 + 0.4 * i / 29))
        time.sleep(0.016)
    kb.pen_up(sw * 0.7, sh * 0.7)
    time.sleep(0.5)
    pyautogui.screenshot().save(PROJECT_ROOT / "logs" / "writing_after.png")

    pyautogui.press("esc")  # 退出放映
    time.sleep(1)
    pres.Close()
    app.Quit()
    print("已保存 logs/writing_before.png 和 logs/writing_after.png，请对比是否有红色斜线")
    return 0


if __name__ == "__main__":
    sys.exit(main())
