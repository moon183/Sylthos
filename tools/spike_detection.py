"""Spike A（PLAN 步骤 4）：不同距离下的 MediaPipe 手部检出率实测。

用法（需现场配合）：
    python tools/spike_detection.py
演讲者站在摄像头前，按提示分别在 1 米 / 2 米 / 3 米处站立挥手，
脚本统计各距离的检出率与帧率并输出报告。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2

from src.capture import BACKENDS
from src.config import load_config

DISTANCES = [1, 2, 3]
TEST_SECONDS = 20  # 每个距离测试时长


def measure_distance(cap, tracker, distance: int) -> dict:
    print(f"\n>>> 请站到距摄像头约 {distance} 米处，自然抬手挥手。{TEST_SECONDS} 秒倒计时开始。")
    total = detected = 0
    t_start = time.time()
    while time.time() - t_start < TEST_SECONDS:
        ok, frame = cap.read()
        if not ok:
            continue
        total += 1
        frame = cv2.flip(frame, 1)
        hf = tracker.process(frame)  # 走完整 HandTracker（含 BPF 三态），与真实管线一致
        if hf is not None:
            detected += 1
            h, w = frame.shape[:2]
            # 画骨架：绿色=整帧直检，青色=BPF/跟踪路径
            color = (0, 255, 0) if hf.source == "direct" else (255, 255, 0)
            pts = [(int(x * w), int(y * h)) for x, y, _ in hf.landmarks]
            connections = [(0,1),(1,2),(2,3),(3,4),(0,5),(5,6),(6,7),(7,8),
                           (5,9),(9,10),(10,11),(11,12),(9,13),(13,14),(14,15),(15,16),
                           (13,17),(17,18),(18,19),(19,20),(0,17)]
            for a, b in connections:
                cv2.line(frame, pts[a], pts[b], color, 2)
            for p in pts:
                cv2.circle(frame, p, 4, (0, 0, 255), -1)
        remain = TEST_SECONDS - int(time.time() - t_start)
        cv2.putText(frame, f"{distance}m  remain:{remain}s", (20, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 2)
        cv2.imshow("Spike A - Detection Rate", frame)
        if cv2.waitKey(1) & 0xFF == 27:
            break
    fps = total / max(time.time() - t_start, 1e-6)
    rate = detected / max(total, 1)
    print(f"    {distance} 米：检出率 {rate:.1%}，帧率 {fps:.1f} FPS")
    return {"distance_m": distance, "detect_rate": rate, "fps": fps}


def main() -> None:
    config = load_config()
    cam = config["camera"]
    cap = cv2.VideoCapture(cam["index"], BACKENDS.get(cam.get("backend", "DSHOW"), cv2.CAP_DSHOW))
    if cam.get("fourcc"):
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*cam["fourcc"]))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cam["width"])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cam["height"])
    if not cap.isOpened():
        print("错误：无法打开摄像头，请检查连接与 camera.index 配置。")
        sys.exit(1)

    from src.tracking import HandTracker

    tracker = HandTracker(config)

    print("=== Spike A：3 米检出率实测（含 BPF）===")
    results = []
    try:
        for d in DISTANCES:
            input(f"\n准备好后按回车开始 {d} 米测试……")
            results.append(measure_distance(cap, tracker, d))
    finally:
        tracker.close()
        cap.release()
        cv2.destroyAllWindows()

    print("\n=== 实测报告 ===")
    for r in results:
        verdict = "达标" if r["detect_rate"] >= 0.95 else "不达标"
        print(f"  {r['distance_m']} 米：检出率 {r['detect_rate']:.1%}（{verdict}），{r['fps']:.1f} FPS")
    worst = min(r["detect_rate"] for r in results if r["distance_m"] <= 2.5)
    if worst >= 0.95:
        print("结论：1-2.5 米检出率达标，继续推进 MVP 实测。")
    else:
        print("结论：仍不达标 → 把报告发给开发者，调整 BPF 参数（裁剪边长/置信度/触发阈值）。")


if __name__ == "__main__":
    main()
