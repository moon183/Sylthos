"""手型判定分解调试工具：实时打印当前手型的各判定条件数值。

当某个手势被误判时（如八字被识别成 ✌️），摆出该手势运行本工具，
输出每个判定条件的实际数值，精确定位是哪个条件没通过。
用法：D:\\Anaconda\\envs\\gesture\\python.exe tools\\debug_pose.py
"""
from __future__ import annotations

import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2

from src.capture import BACKENDS
from src.config import load_config
from src.gestures.static_pose import FINGERS, PoseClassifier
from src.tracking import HandTracker


def main() -> None:
    config = load_config()
    cam = config["camera"]
    cap = cv2.VideoCapture(cam["index"], BACKENDS.get(cam.get("backend", "DSHOW"), cv2.CAP_DSHOW))
    if cam.get("fourcc"):
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*cam["fourcc"]))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cam["width"])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cam["height"])
    if not cap.isOpened():
        print("摄像头打不开")
        sys.exit(1)

    clf = PoseClassifier(config)
    tracker = HandTracker(config)
    print("摆出目标手势，每秒打印一次判定分解。Ctrl+C 退出。\n")
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                continue
            hf = tracker.process(cv2.flip(frame, 1))
            if hf is None:
                print("（未检测到手）")
                time.sleep(1)
                continue
            ext = {name: clf._finger_extended(hf, *idx) for name, idx in FINGERS.items()}
            thumb_ext = clf._thumb_extended(hf)
            thumb_ratio = _ratio(hf)
            cos = clf._thumb_index_angle_ok(hf)
            cos_val = _angle_cos(hf)
            print(f"手型={clf.classify(hf).name:10s} | 伸直: " +
                  " ".join(f"{n}={'Y' if e else 'N'}" for n, e in ext.items()) +
                  f" | 拇指外展={'Y' if thumb_ext else 'N'}({thumb_ratio:.2f})"
                  f" | 拇食夹角ok={'Y' if cos else 'N'}(cos={cos_val:.2f})")
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        tracker.close()
        cap.release()


def _ratio(hf):
    return _d(hf.point(4), hf.point(17)) / max(hf.hand_scale, 1e-6)


def _angle_cos(hf):
    wrist = hf.point(0)
    vt = tuple(b - a for a, b in zip(wrist, hf.point(4)))
    vi = tuple(b - a for a, b in zip(wrist, hf.point(8)))
    dot = sum(x * y for x, y in zip(vt, vi))
    na = math.sqrt(sum(x * x for x in vt))
    nb = math.sqrt(sum(x * x for x in vi))
    return dot / (na * nb) if na > 1e-9 and nb > 1e-9 else 0.0


def _d(p, q):
    return math.dist(p, q)


if __name__ == "__main__":
    main()
