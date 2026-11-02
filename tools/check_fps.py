"""摄像头帧率/模式诊断：测各分辨率下纯采集的实际帧率（不含推理开销）。

对每种 (宽×高×目标帧率) 组合纯读帧 3 秒，报告实际帧率。
用法：D:\\Anaconda\\envs\\gesture\\python.exe tools\\check_fps.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2

from src.capture import BACKENDS
from src.config import load_config

COMBOS = [
    (640, 480, 60),
    (640, 480, 120),
    (1280, 720, 60),
    (1280, 720, 30),
    (1920, 1080, 60),
    (1920, 1080, 30),
    (3840, 2160, 30),
]


def measure(index: int, backend, fourcc: str | None,
            width: int, height: int, fps: int) -> None:
    tag = f"{width}x{height}@{fps}"
    cap = cv2.VideoCapture(index, backend)
    if not cap.isOpened():
        print(f"[{tag}] 打不开")
        return
    if fourcc:
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)
    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    # 预热 10 帧
    for _ in range(10):
        cap.read()
    frames = 0
    t0 = time.time()
    while time.time() - t0 < 3.0:
        ok, _ = cap.read()
        if ok:
            frames += 1
    actual_fps = frames / (time.time() - t0)
    mode_note = "" if (actual_w, actual_h) == (width, height) else f"（实际切到 {actual_w}x{actual_h}）"
    print(f"[{tag}] {mode_note} 实测 {actual_fps:.1f} FPS")
    cap.release()


def main() -> None:
    config = load_config()
    cam = config["camera"]
    backend = BACKENDS.get(cam.get("backend", "DSHOW"), cv2.CAP_DSHOW)
    print(f"=== 帧率诊断（后端 {cam.get('backend')}，编码 {cam.get('fourcc')}） ===")
    for w, h, fps in COMBOS:
        measure(cam["index"], backend, cam.get("fourcc"), w, h, fps)
    print("\n解读：实测值远低于目标值 = 该模式硬件不支持或带宽不足；")
    print("若 720p@60 实测接近 60，说明 60fps 可用，把 config 里 width/height 保持 720p 即可。")


if __name__ == "__main__":
    main()
