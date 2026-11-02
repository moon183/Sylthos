"""自定义手势链路诊断工具（2026-09-12，针对用户实测"训练成功但激活后做动作零反应"）。

不复用任何 GUI/摄像头，离线回答四个问题：
1. 样本体检：每条样本的点数/路径长（handScale 归一）是否过得了 min_points / min_path_hs；
2. 训练体检：train_from_directory 的训练准确率、留一法泛化估计、各样本置信度分布；
3. 分段器体检：把样本当作"实时的 INDEX 帧序列"喂给 _StrokeSegmenter，
   再以"换成 OPEN_PALM 5 帧"收笔，验证笔画能否完成、MLP 是否触发；
4. 管线级体检：把同样帧序列喂给完整 Pipeline（ARMED 态），验证 CUSTOM_GESTURE
   事件能否穿过门控/宽限期/作画屏蔽最终分发到指令。

用法：D:\\Anaconda\\envs\\gesture\\python.exe tools\\diagnose_custom_gesture.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from src.config import load_config  # noqa: E402
from src.decision import GestureType, Mode  # noqa: E402
from src.gestures.static_pose import Pose  # noqa: E402
from src.gestures.trajectory import (  # noqa: E402
    CustomGestureDetector, _StrokeSegmenter, _load_csv, stroke_feature,
    train_from_directory,
)
from src.pipeline import Pipeline  # noqa: E402
from src.tracking import HandFrame  # noqa: E402

CG_ROOT = ROOT / "custom_gestures"
FPS = 30.0


def make_handframe(points, scales, i) -> HandFrame:
    """用轨迹点伪造一帧解剖学一致的食指手 HandFrame：
    食指 MCP→PIP→DIP→TIP 共线指向轨迹点（恒伸直，分类稳定为 INDEX），
    其余手指弯曲，腕点固定。i 越界时沿用最后一个轨迹点（手停在终点），
    但时间戳照常前进（收笔计时依赖真实流逝的时间）。"""
    ts = i / FPS
    i = min(i, len(points) - 1)
    tip = (points[i][0], points[i][1], 0.0)
    wrist = (0.5, 0.8, 0.0)
    mcp = (0.44, 0.55, 0.0)
    # 指节按比例位于 MCP→TIP 连线上（真实手的指节跟随指尖）
    pip = tuple(mcp[k] + (tip[k] - mcp[k]) * 0.45 for k in range(2)) + (0.0,)
    dip = tuple(mcp[k] + (tip[k] - mcp[k]) * 0.75 for k in range(2)) + (0.0,)
    lm = [(0.0, 0.0, 0.0)] * 21
    lm[0] = wrist
    lm[1], lm[2], lm[3], lm[4] = (0.42, 0.72, 0), (0.38, 0.65, 0), (0.36, 0.61, 0), (0.34, 0.58, 0)
    for base_x, idxs in ((0.44, (5, 6, 7, 8)), (0.50, (9, 10, 11, 12)),
                         (0.56, (13, 14, 15, 16)), (0.62, (17, 18, 19, 20))):
        lm[idxs[0]] = (base_x, 0.55, 0.0)
        if idxs[0] == 5:  # 食指：伸直指向轨迹点
            lm[5], lm[6], lm[7], lm[8] = mcp, pip, dip, tip
        else:             # 其余手指弯曲
            lm[idxs[1]] = (base_x, 0.52, 0.0)
            lm[idxs[2]] = (base_x, 0.54, 0.0)
            lm[idxs[3]] = (base_x, 0.56, 0.0)
    return HandFrame(handedness="Right", landmarks=lm,
                     hand_scale=scales[i] if scales else 0.25,
                     timestamp=ts)


def sample_stats(path: Path, config: dict) -> dict:
    pts = _load_csv(path)
    arr = np.array(pts)
    diffs = np.linalg.norm(np.diff(arr, axis=0), axis=1)
    path_len = float(diffs.sum())
    return {"n": len(pts), "path": path_len,
            "x_range": float(arr[:, 0].ptp()), "y_range": float(arr[:, 1].ptp()),
            "step_med": float(np.median(diffs)) if len(diffs) else 0.0}


def main() -> int:
    config = load_config()
    ccfg = config["custom_gestures"]
    print(f"配置: min_points={ccfg['min_points']} min_path_hs={ccfg['min_path_hs']} "
          f"stroke_end_frames={ccfg['stroke_end_frames']} prob_threshold={ccfg['prob_threshold']}")

    # ---- 1. 样本体检 ----
    print("\n== 1. 样本体检 ==")
    sample_files = sorted((CG_ROOT / "画圈").glob("*.csv"))
    stats = []
    for f in sample_files:
        s = sample_stats(f, config)
        stats.append(s)
        # 注意：样本 CSV 不含 handScale，路径长用归一化坐标直接衡量（假设 hand_scale≈0.2）
        est_hs = s["path"] / 0.2
        print(f"  {f.name}: 点数={s['n']} 路径={s['path']:.3f}（≈{est_hs:.1f} 手长@hs0.2） "
              f"x幅={s['x_range']:.3f} y幅={s['y_range']:.3f} 中位步长={s['step_med']:.4f}")
    print(f"  点数范围 {min(s['n'] for s in stats)}~{max(s['n'] for s in stats)}，"
          f"min_points={ccfg['min_points']}")

    # ---- 2. 训练体检 ----
    print("\n== 2. 训练体检 ==")
    model, report = train_from_directory(CG_ROOT)
    print(f"  类别: {report['classes']}，样本数 {report['n_samples']}（含拒绝类），"
          f"训练准确率 {report['accuracy']:.1%}")
    # 留一法：逐条样本看置信度（粗略泛化估计：用全量训练的模型看每条样本的置信度）
    confs = []
    for f in sample_files:
        feat = stroke_feature(_load_csv(f))
        label, prob = model.predict(feat, threshold=0.0)  # 阈值 0 看原始置信度
        proba = model.predict_proba(feat)
        confs.append(proba.max())
        print(f"  {f.name}: 预测={label} 置信度={proba.max():.3f}")
    print(f"  样本置信度 min={min(confs):.3f} median={float(np.median(confs)):.3f} "
          f"（触发阈值 {ccfg['prob_threshold']}）")

    # ---- 3. 分段器体检（模拟实时帧流）----
    print("\n== 3. 分段器体检（样本作为实时 INDEX 帧流 + OPEN_PALM 收笔）==")
    seg = _StrokeSegmenter(config)
    detector_model_path = CG_ROOT / "model.json"
    model.save(detector_model_path)
    detector = CustomGestureDetector(detector_model_path, config)
    print(f"  detector.available = {detector.available}")
    for f in sample_files[:3]:
        pts = _load_csv(f)
        seg2 = _StrokeSegmenter(config)
        out = None
        for i in range(len(pts)):
            hf = make_handframe(pts, None, i)
            r = seg2.feed(hf, Pose.INDEX)
            if r is not None:
                out = r
        # 收笔：换成 OPEN_PALM 持续 stroke_end_frames 帧
        for j in range(ccfg["stroke_end_frames"] + 2):
            hf = make_handframe(pts, None, len(pts) + j)
            r = seg2.feed(hf, Pose.OPEN_PALM)
            if r is not None:
                out = r
        print(f"  {f.name}: 分段器{'产出笔画 %d 点' % len(out) if out else '未产出笔画（！）'}")

    # 完整 detector 路径（含 MLP 分类与阈值）
    pts = _load_csv(sample_files[0])
    det2 = CustomGestureDetector(detector_model_path, config)
    event = None
    for i in range(len(pts)):
        event = det2.feed(make_handframe(pts, None, i), Pose.INDEX) or event
    for j in range(ccfg["stroke_end_frames"] + 2):
        event = det2.feed(make_handframe(pts, None, len(pts) + j), Pose.OPEN_PALM) or event
    print(f"  detector 端到端: {'触发事件 ' + str(event.data) if event else '无事件（！）'}")

    # ---- 4. 管线级体检（ARMED 态全链路）----
    print("\n== 4. 管线级体检（Pipeline, 模式=ARMED, 映射 画圈→last_slide）==")
    config2 = load_config()
    config2.setdefault("custom_gestures", {}).setdefault("mapping", {})["画圈"] = "last_slide"
    pipe = Pipeline(config2, with_controls=False)
    pipe.engine.mode = Mode.ARMED
    events, dispatched = [], []
    for i in range(len(pts)):
        pipe.process(make_handframe(pts, None, i), {}, events_out=events, dispatched_out=dispatched)
    for j in range(ccfg["stroke_end_frames"] + 2):
        pipe.process(make_handframe(pts, None, len(pts) + j), {},
                     events_out=events, dispatched_out=dispatched)
    custom_events = [e for e in events if e.type is GestureType.CUSTOM_GESTURE]
    print(f"  事件流: {[e.type.name for e in events]}")
    print(f"  CUSTOM_GESTURE 事件: {len(custom_events)}，最终分发: {len(dispatched)}")

    # ---- 5. 垂手/静止场景复现（用户最可能的实际操作）----
    print("\n== 5. 场景复现：画完后垂手（hf=None）或保持食指静止 ====")
    for scenario in ("hand_lost", "hold_still"):
        pipe2 = Pipeline(config2, with_controls=False)
        pipe2.engine.mode = Mode.ARMED
        events2 = []
        for i in range(len(pts)):
            pipe2.process(make_handframe(pts, None, i), {}, events_out=events2)
        for j in range(30):  # 1 秒（hf=None 走真实时钟，需按真实帧率 pacing）
            if scenario == "hand_lost":
                time.sleep(1 / 30)
                pipe2.process(None, {}, events_out=events2)
            else:
                last = [pts[-1]] * 2
                pipe2.process(make_handframe(last, None, 100 + j), {}, events_out=events2)
        fired = [e for e in events2 if e.type is GestureType.CUSTOM_GESTURE]
        print(f"  {scenario}: {'识别成功' if fired else '零反应（复现用户症状！）'}"
              f"，事件流={[e.type.name for e in events2]}")

    print("\n诊断完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
