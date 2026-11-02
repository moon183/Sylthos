"""用 Qt Multimedia（走 Windows Media Foundation，与系统相机同源）枚举摄像头支持的全部模式。

直接回答"这颗摄像头到底给 Windows 开放了哪些 分辨率×帧率 组合"。
用法：D:\\Anaconda\\envs\\gesture\\python.exe tools\\check_qt_modes.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QCoreApplication
from PySide6.QtMultimedia import QMediaDevices


def main() -> None:
    app = QCoreApplication(sys.argv)
    cameras = QMediaDevices.videoInputs()
    if not cameras:
        print("未发现摄像头")
        return
    for cam in cameras:
        print(f"\n=== {cam.description()} ===")
        rows = []
        for fmt in cam.videoFormats():
            res = fmt.resolution()
            rows.append((res.width(), res.height(),
                         fmt.minFrameRate(), fmt.maxFrameRate(),
                         str(fmt.pixelFormat()).split(".")[-1]))
        # 按分辨率汇总帧率范围
        seen = {}
        for w, h, fmin, fmax, pix in rows:
            key = (w, h, pix)
            seen[key] = (max(seen.get(key, (0,))[0], fmax), fmin) if key in seen else (fmax, fmin)
        for (w, h, pix), (fmax, fmin) in sorted(seen.items()):
            print(f"  {w}x{h}  {pix:12s}  {fmin:.0f}-{fmax:.0f} fps")


if __name__ == "__main__":
    main()
