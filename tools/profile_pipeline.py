"""识别管线帧耗时探针（2026-09-13 实测反馈"书写/平移卡顿且预览同步卡"的定位工具）。

不依赖 GUI，独立跑 摄像头采集 → MediaPipe 检测 → 预览渲染 三段，逐段统计帧耗时，
定位卡顿尖峰到底出在哪一段：
- capture：取帧+镜像（应 <5ms）；
- track：HandTracker.process（MediaPipe 手部检测 + 偶发 BlazePose 定位）；
- preview：骨骼绘制 + BGR→QImage 缩放（与 worker._emit_preview 同代码路径）。

输出：各段 avg / p95 / max，以及 >100ms 的停顿事件明细（用于复现"画一段直线"）。
可选 --seconds N 控制时长；--writing 模拟书写期的笔级事件输出（观察争用）。

用法：D:\\Anaconda\\envs\\gesture\\python.exe tools\\profile_pipeline.py [--seconds 10] [--writing]
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import cv2  # noqa: E402

from src.config import load_config  # noqa: E402


def pct(sorted_vals, q):
    return sorted_vals[min(len(sorted_vals) - 1, int(len(sorted_vals) * q))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=10.0)
    ap.add_argument("--writing", action="store_true", help="模拟书写期的 ink 事件输出")
    args = ap.parse_args()

    from src.capture import CameraCapture
    from src.control.keyboard import CursorStreamer
    from src.tracking import HandTracker

    config = load_config()
    cam = config["camera"]
    streamer = CursorStreamer(hz=120, tau_ms=50, ink_hz=60) if args.writing else None
    ink_moves = 0

    seg = {"capture": [], "track": [], "preview": []}
    stalls = []  # (t, total_ms, track_ms)
    cam_ts = []  # 摄像头帧时间戳（算实际送达帧率）
    t_start = time.perf_counter()
    warmup_until = t_start + 2.0  # 前 2 秒模型加载不计入统计
    last_ts = 0.0
    bpf_frames = 0

    print(f"探针运行 {args.seconds:.0f} 秒"
          f"（{'含书写事件模拟，' if args.writing else ''}请正常做手势/书写动作）……")
    with CameraCapture(cam["index"], cam["width"], cam["height"], cam["fps"],
                       cam.get("fourcc"), cam.get("backend", "MSMF")) as cap, \
         HandTracker(config) as tracker:
        while time.perf_counter() - t_start < args.seconds:
            frame, ts = cap.read_latest()
            if frame is None or ts == last_ts:
                time.sleep(0.001)
                continue
            last_ts = ts
            if time.perf_counter() < warmup_until:
                continue  # 预热期不计入统计
            cam_ts.append(ts)
            t0 = time.perf_counter()
            frame = cv2.flip(frame, 1)
            t1 = time.perf_counter()
            hf = tracker.process(frame)
            t2 = time.perf_counter()
            # 与 worker._emit_preview 等价的渲染路径
            if hf is not None:
                import mediapipe as mp
                h, w = frame.shape[:2]
                pts = [(int(x * w), int(y * h)) for x, y, _ in hf.landmarks]
                for a, b in mp.solutions.hands.HAND_CONNECTIONS:
                    cv2.line(frame, pts[a], pts[b], (0, 200, 0), 2)
                for x, y in pts:
                    cv2.circle(frame, (x, y), 4, (0, 0, 255), -1)
                if hf.source == "bpf":
                    bpf_frames += 1
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            from PySide6.QtGui import QImage
            QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).scaled(960, 540)
            t3 = time.perf_counter()
            if streamer is not None and hf is not None:
                knuckle = hf.point(9)
                streamer.set_target(knuckle[0] * 300, knuckle[1] * 200, ink=True)
                ink_moves += 1
            c_ms, tr_ms, p_ms = (t1 - t0) * 1000, (t2 - t1) * 1000, (t3 - t2) * 1000
            seg["capture"].append(c_ms)
            seg["track"].append(tr_ms)
            seg["preview"].append(p_ms)
            if (t3 - t0) * 1000 > 100:
                stalls.append((t3 - t_start, (t3 - t0) * 1000, tr_ms))

    total = len(seg["track"])
    cam_fps = (len(cam_ts) - 1) / (cam_ts[-1] - cam_ts[0]) if len(cam_ts) > 1 else 0.0
    print(f"\n=== 帧耗时统计（{total} 帧，BPF 检出 {bpf_frames} 帧，"
          f"摄像头实际送达 {cam_fps:.1f} FPS）===")
    for name, vals in seg.items():
        vals = sorted(vals)
        print(f"  {name:8s} avg={statistics.mean(vals):5.1f}ms  "
              f"p95={pct(vals, 0.95):5.1f}ms  max={vals[-1]:6.1f}ms")
    print(f"\n=== >100ms 停顿事件（{len(stalls)} 次）===")
    for t, total_ms, tr_ms in stalls[:20]:
        print(f"  t={t:6.1f}s  总耗时={total_ms:6.1f}ms（其中检测 {tr_ms:.1f}ms）")
    if streamer is not None:
        streamer.close()
    print("\n提示：书写/快速运动期间 track 段的 p95/max 若显著高于 avg，"
          "说明 MediaPipe 跟踪丢失重检是尖峰来源。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
