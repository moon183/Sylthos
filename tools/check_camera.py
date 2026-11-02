"""摄像头诊断工具：排查黑屏/打不开问题。

针对 4K 摄像头增强版：尝试 索引 × 后端(DSHOW/MSMF/ANY) × 编码(默认/MJPG) × 分辨率(720p/原生)，
报告每个组合的实际分辨率与画面亮度（判断是否黑屏）。
用法：D:\\Anaconda\\envs\\gesture\\python.exe tools\\check_camera.py
"""
from __future__ import annotations

import time

import cv2

BACKENDS = [("DSHOW", cv2.CAP_DSHOW), ("MSMF", cv2.CAP_MSMF), ("ANY", cv2.CAP_ANY)]


def try_combo(index: int, backend_name: str, backend, use_mjpg: bool, set_720p: bool) -> None:
    tag = f"idx{index}/{backend_name}/{'MJPG' if use_mjpg else '默认'}/{'720p' if set_720p else '原生'}"
    cap = cv2.VideoCapture(index, backend)
    if not cap.isOpened():
        print(f"[{tag}] 打不开")
        return
    if use_mjpg:
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    if set_720p:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    brightness = []
    for i in range(30):
        ok, frame = cap.read()
        if ok and frame is not None and i >= 10:
            brightness.append(float(frame.mean()))
        time.sleep(0.03)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if not brightness:
        print(f"[{tag}] 打开了但读不到帧")
    else:
        mean = sum(brightness) / len(brightness)
        verdict = "黑屏!" if mean < 5 else f"画面正常 <<<"
        print(f"[{tag}] {w}x{h}，亮度 {mean:.1f} → {verdict}")
    cap.release()


def main() -> None:
    print("=== 摄像头诊断（增强版） ===")
    print("提示：若全部组合黑屏，请检查 Windows 自带「相机」应用是否正常，")
    print("以及 设置→隐私和安全性→相机→允许桌面应用访问。\n")
    for backend_name, backend in BACKENDS:
        for use_mjpg in (False, True):
            for set_720p in (True, False):
                try_combo(0, backend_name, backend, use_mjpg, set_720p)


if __name__ == "__main__":
    main()
