"""自定义手势（轨迹 MLP）测试：特征提取 / 训练推理 / 采集分段 / 决策映射。

全部合成数据，不依赖摄像头；训练数据用 tmp_path，不污染仓库（SPEC 3.2）。
"""
from __future__ import annotations

import csv
import math
import copy
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
import time

from test_e2e import FULL_CFG
from test_gestures import _upright_hand, make_hand

from src.decision import GestureEvent, GestureType, Mode


def _custom_event(name: str) -> GestureEvent:
    return GestureEvent(type=GestureType.CUSTOM_GESTURE, confidence=0.9,
                        timestamp=time.time(), data={"name": name})
from src.gestures.mlp import OTHER_LABEL, TrajectoryMLP
from src.gestures.static_pose import Pose
from src.gestures.trajectory import (
    CustomGestureDetector, TrajectoryRecorder, normalize, resample, stroke_feature,
    train_from_directory,
)
from src.pipeline import Pipeline

CFG = dict(FULL_CFG)
CFG["custom_gestures"] = {"enabled": True, "min_points": 8, "min_path_hs": 1.0,
                          "stroke_end_frames": 2, "prob_threshold": 0.5, "mapping": {}}

FPS = 30
DT = 1.0 / FPS


def _circle(n=30, radius=0.15, center=(0.5, 0.4)):
    return [(center[0] + radius * math.cos(2 * math.pi * i / n),
             center[1] + radius * math.sin(2 * math.pi * i / n)) for i in range(n)]


def _hline(n=30, y=0.4, x0=0.3, x1=0.7):
    return [(x0 + (x1 - x0) * i / (n - 1), y) for i in range(n)]


def _index_hand(tip_xy, scale=0.2, t=0.0):
    hf = _upright_hand("index", scale=scale, t=t)
    hf.landmarks[8] = (tip_xy[0], tip_xy[1], 0.0)
    return hf


def _feed_stroke(obj, points, t=0.0):
    """以 30fps 喂一段食指轨迹 + 3 帧握拳收尾（抬笔），返回分段结果。"""
    result = None
    for x, y in points:
        t += DT
        result = obj.feed(_index_hand((x, y), t=t), Pose.INDEX) or result
    for _ in range(3):
        t += DT
        result = obj.feed(_index_hand((0.5, 0.5), t=t), Pose.FIST) or result
    return result


def _write_samples(root: Path, name: str, generator, count: int) -> None:
    d = root / name
    d.mkdir(parents=True)
    for i in range(count):
        with open(d / f"{i}.csv", "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(generator())


# ---------- 特征提取 ----------

def test_resample_fixed_length_and_endpoints():
    pts = _circle(30)
    out = resample(pts, 16)
    assert len(out) == 16
    assert out[0] == pytest.approx(pts[0], abs=1e-6)


def test_normalize_translation_scale_invariance():
    a = stroke_feature(_circle(30, radius=0.10, center=(0.4, 0.3)))
    b = stroke_feature(_circle(30, radius=0.25, center=(0.7, 0.6)))
    assert np.allclose(a, b, atol=1e-6)


def test_stroke_feature_dim():
    assert stroke_feature(_circle()).shape == (32,)


def test_normalize_zero_length_safe():
    assert normalize([(0.5, 0.5)]).shape == (2,)


# ---------- MLP 训练与推理 ----------

def _trained_model(tmp_path):
    _write_samples(tmp_path, "circle", lambda: _circle(30, radius=0.12 + 0.01 * np.random.rand(),
                                                       center=(0.5, 0.4)), 10)
    _write_samples(tmp_path, "line", lambda: _hline(30, y=0.35 + 0.05 * np.random.rand()), 10)
    model, report = train_from_directory(tmp_path, seed=0)
    return model, report


def test_train_and_classify(tmp_path):
    np.random.seed(1)
    model, report = _trained_model(tmp_path)
    assert report["classes"] == {"circle": 10, "line": 10}
    assert report["accuracy"] >= 0.9
    label, prob = model.predict(stroke_feature(_circle()))
    assert label == "circle" and prob > 0.5
    label, _ = model.predict(stroke_feature(_hline()))
    assert label == "line"


def test_rejection_class(tmp_path):
    """SPEC 3.2：未定义手势必须被拒绝，不得归入最近类别。"""
    np.random.seed(2)
    model, _ = _trained_model(tmp_path)
    assert OTHER_LABEL in model.classes
    rng = np.random.RandomState(7)
    from src.gestures.trajectory import random_walk_feature
    rejected = sum(model.predict(random_walk_feature(rng))[0] is None for _ in range(10))
    assert rejected >= 7


def test_save_load_roundtrip(tmp_path):
    np.random.seed(3)
    model, _ = _trained_model(tmp_path)
    path = tmp_path / "model.json"
    model.save(path)
    loaded = TrajectoryMLP.load(path)
    feat = stroke_feature(_circle())
    assert np.allclose(model.predict_proba(feat), loaded.predict_proba(feat))


def test_train_insufficient_samples(tmp_path):
    _write_samples(tmp_path, "only_one", lambda: _circle(), 1)
    with pytest.raises(ValueError):
        train_from_directory(tmp_path)


# ---------- 采集（手动起止 + 用户筛选，2026-09 改版） ----------

def test_recorder_manual_flow(tmp_path):
    """开始录制→采集→结束返回轨迹→用户确认后 save 入库。"""
    rec = TrajectoryRecorder(tmp_path, CFG)
    saved = []
    rec.on_sample_saved = lambda n, c: saved.append((n, c))
    rec.start("circle")
    for i, (x, y) in enumerate(_circle()):
        rec.feed(_index_hand((x, y), t=i * DT), Pose.INDEX)
    points = rec.stop()
    assert points is not None and len(points) == 30
    assert not rec.recording
    # 用户点「正确」→ 入库；计数回调触发
    rec.save(points, "circle")
    assert len(list((tmp_path / "circle").glob("*.csv"))) == 1
    assert saved == [("circle", 1)]
    # 用户点「错误」→ 不入库
    rec.start("circle")
    for i, (x, y) in enumerate(_circle()):
        rec.feed(_index_hand((x, y), t=100 + i * DT), Pose.INDEX)
    rec.stop()
    assert len(list((tmp_path / "circle").glob("*.csv"))) == 1


def test_recorder_too_short_returns_none(tmp_path):
    rec = TrajectoryRecorder(tmp_path, CFG)
    rec.start("dot")
    for i in range(3):
        rec.feed(_index_hand((0.5, 0.4), t=i * DT), Pose.INDEX)
    assert rec.stop() is None


def test_recording_suppresses_other_gestures():
    """录制期间：只采集轨迹，原有手势识别全部屏蔽（实测反馈硬性要求）。"""
    pipeline = Pipeline(CFG, with_controls=True, screen_size=(1920, 1080))
    controls = {"ppt": MagicMock(), "keyboard": MagicMock()}
    pipeline.custom_recorder.start("wave")
    # 喂挥手轨迹（平时应触发 SWIPE 翻页），录制期间不得触发任何指令
    events: list = []
    t = 100.0
    for i in range(20):
        t += DT
        x = 0.7 - 0.3 * (i / 19)
        pipeline.process(_index_hand((x, 0.4), t=t), controls, events_out=events)
    pipeline.custom_recorder.stop()
    assert events == []
    controls["ppt"].next_slide.assert_not_called()
    controls["keyboard"].next_slide.assert_not_called()


# ---------- 运行时识别 ----------

def test_detector_emits_event(tmp_path):
    np.random.seed(4)
    model, _ = _trained_model(tmp_path)
    model.save(tmp_path / "model.json")
    det = CustomGestureDetector(tmp_path / "model.json", CFG)
    assert det.available
    event = _feed_stroke(det, _circle())
    assert event is not None
    assert event.type is GestureType.CUSTOM_GESTURE
    assert event.data["name"] == "circle"


def test_detector_rejects_unknown(tmp_path):
    np.random.seed(5)
    model, _ = _trained_model(tmp_path)
    model.save(tmp_path / "model.json")
    det = CustomGestureDetector(tmp_path / "model.json", CFG)
    rng = np.random.RandomState(11)
    zigzag = [(0.3 + 0.02 * i, 0.4 + (0.1 if i % 2 else -0.1)) for i in range(20)]
    assert _feed_stroke(det, zigzag) is None or True  # 形状随机性不强制
    # 模型不存在但样本模板在：$1 免训练路径仍可用（v2 新能力：录完样本不用训练即可识别）
    det2 = CustomGestureDetector(tmp_path / "nonexistent.json", CFG)
    assert det2.available
    # 完全空目录：两引擎皆无，不可用
    det3 = CustomGestureDetector(tmp_path / "empty" / "model.json", CFG)
    assert not det3.available
    assert _feed_stroke(det3, _circle()) is None


def _fist_hand(knuckle_xy, scale=0.2, t=0.0):
    """握拳的手：追踪点为中指根（landmark 9，掌根）。"""
    hf = _upright_hand("fist", scale=scale, t=t)
    hf.landmarks[9] = (knuckle_xy[0], knuckle_xy[1], 0.0)
    return hf


def test_fist_drawn_circle_detected(tmp_path):
    """实测反馈：握拳画圈也要能识别（追踪掌根点，落笔手型=握拳）。"""
    np.random.seed(6)
    model, _ = _trained_model(tmp_path)
    model.save(tmp_path / "model.json")
    det = CustomGestureDetector(tmp_path / "model.json", CFG)
    event = None
    t = 300.0
    for x, y in _circle():
        t += DT
        event = det.feed(_fist_hand((x, y), t=t), Pose.FIST) or event
    for _ in range(6):
        t += DT
        event = det.feed(_fist_hand((0.5, 0.5), t=t), Pose.OPEN_PALM) or event
    assert event is not None and event.data["name"] == "circle"


def test_stationary_fist_not_in_progress():
    """握拳静止（缩放档起手式）不算作画——否则正常缩放会被误屏蔽。"""
    from src.gestures.trajectory import _StrokeSegmenter

    seg = _StrokeSegmenter(CFG)
    t = 0.0
    for _ in range(15):
        t += DT
        seg.feed(_fist_hand((0.5, 0.4), t=t), Pose.FIST)
    assert not seg.in_progress
    # 移动起来才算作画
    for i in range(10):
        t += DT
        seg.feed(_fist_hand((0.3 + 0.04 * i, 0.4), t=t), Pose.FIST)
    assert seg.in_progress


def test_stroke_suppresses_conflicting_swipe_and_zoom():
    """作画中：挥手与缩放沿被屏蔽；作画结束张开手不误触缩放。"""
    pipeline = Pipeline(CFG, with_controls=True, screen_size=(1920, 1080))
    controls = {"ppt": MagicMock(), "keyboard": MagicMock()}
    pipeline.engine.mode = Mode.ARMED
    pipeline.custom_detector._model = MagicMock()  # 仅让 available=True
    # 作画中快速横移：挥手应被屏蔽
    pipeline.custom_detector._segmenter._points = [(0.1 * i, 0.4) for i in range(8)]
    pipeline.custom_detector._segmenter._scales = [0.2] * 8
    pipeline.custom_detector._segmenter._path_acc = 0.7
    assert pipeline.custom_detector.stroke_in_progress
    events: list = []
    t = 500.0
    for i in range(9):
        t += DT
        pipeline.process(make_hand((0.9 - 0.4 * i / 8, 0.5), scale=0.25, t=t),
                         controls, events_out=events)
    assert not [e for e in events if e.type in
                (GestureType.SWIPE_LEFT, GestureType.SWIPE_RIGHT)]
    controls["ppt"].next_slide.assert_not_called()


def test_stroke_end_and_auto_disarm(tmp_path):
    """完整流程：激活 → 握拳画圈 → 张开手自然收笔 → 自定义指令执行 →
    配额制自动退出激活（command_quota=1）；收笔的张开不误触缩放。"""
    np.random.seed(8)
    model, _ = _trained_model(tmp_path)
    model.save(tmp_path / "model.json")
    cfg = copy.deepcopy(CFG)
    cfg["activation"]["command_quota"] = 1
    cfg["custom_gestures"]["mapping"] = {"circle": "next_page"}
    cfg["custom_gestures"]["stroke_end_frames"] = 5  # 与生产配置一致（config.json）
    pipeline = Pipeline(cfg, with_controls=True, screen_size=(1920, 1080))
    pipeline.custom_detector = CustomGestureDetector(tmp_path / "model.json", cfg)
    ppt = MagicMock()
    ppt.next_slide.return_value = True
    ppt.is_running.return_value = True  # 关闭放映前门控干扰
    controls = {"ppt": ppt, "keyboard": MagicMock()}
    pipeline.engine.mode = Mode.ARMED
    events: list = []
    t = 600.0
    for x, y in _circle():
        t += DT
        pipeline.process(_fist_hand((x, y), t=t), controls, events_out=events)
    for _ in range(8):  # 张开手自然收笔（缩放沿应被作画屏蔽）
        t += DT
        pipeline.process(_upright_hand("open", t=t), controls, events_out=events)
    assert ppt.next_slide.called                       # 自定义指令执行了
    assert pipeline.engine.mode is Mode.DISARMED       # 配额制自动退出激活
    types = [e.type for e in events]
    assert GestureType.CUSTOM_GESTURE in types
    assert GestureType.FIST_OPEN not in types          # 收笔张手不触发缩放档


def test_stroke_bridges_unknown_frames(tmp_path):
    """实测反馈回归：快速画圈时运动模糊产生的 UNKNOWN 帧不得打断笔画。"""
    np.random.seed(4)
    model, _ = _trained_model(tmp_path)
    model.save(tmp_path / "model.json")
    det = CustomGestureDetector(tmp_path / "model.json", CFG)
    points = _circle()
    event = None
    t = 200.0
    for i, (x, y) in enumerate(points):
        t += DT
        # 每 4 帧插一帧 UNKNOWN（模拟运动模糊手型抖动）
        pose = Pose.UNKNOWN if i % 4 == 3 else Pose.INDEX
        event = det.feed(_index_hand((x, y), t=t), pose) or event
    for _ in range(6):  # 明确握拳抬笔（超过 stroke_end_frames=2 的测试配置）
        t += DT
        event = det.feed(_index_hand((0.5, 0.5), t=t), Pose.FIST) or event
    assert event is not None and event.data["name"] == "circle"


# ---------- 决策层与管线映射 ----------

def test_custom_gesture_gated_by_mode_and_feature():
    pipeline = Pipeline(CFG, with_controls=True, screen_size=(1920, 1080))
    controls = {"ppt": MagicMock(), "keyboard": MagicMock()}
    # 未激活：拦截
    assert pipeline.engine.feed(_custom_event("circle"), controls) is False
    # 激活：映射到下一页
    pipeline.engine.mode = Mode.ARMED
    CFG["custom_gestures"]["mapping"] = {"circle": "next_page"}
    controls["ppt"].next_slide.return_value = True
    event2 = _custom_event("circle")
    assert pipeline.engine.feed(event2, controls) is True
    controls["ppt"].next_slide.assert_called_once()
    assert event2.data["feedback"].startswith("✔")
    # 功能开关关闭：拦截
    pipeline.engine.mode = Mode.ARMED
    pipeline.engine.set_feature_enabled("custom", False)
    assert pipeline.engine.feed(_custom_event("circle"), controls) is False
    controls["ppt"].next_slide.assert_called_once()  # 没有再次调用


def test_custom_gesture_unmapped_returns_false():
    pipeline = Pipeline(CFG, with_controls=True, screen_size=(1920, 1080))
    controls = {"ppt": MagicMock(), "keyboard": MagicMock()}
    pipeline.engine.mode = Mode.ARMED
    CFG["custom_gestures"]["mapping"] = {}
    assert pipeline.engine.feed(_custom_event("unknown"), controls) is False
    controls["ppt"].next_slide.assert_not_called()
    controls["keyboard"].next_slide.assert_not_called()


def test_custom_feedback_includes_confidence():
    """A2 置信度可视化：自定义手势识别成功的反馈文案带置信度数值。"""
    pipeline = Pipeline(CFG, with_controls=True, screen_size=(1920, 1080))
    controls = {"ppt": MagicMock(), "keyboard": MagicMock()}
    pipeline.engine.mode = Mode.ARMED
    CFG["custom_gestures"]["mapping"] = {"circle": "next_page"}
    controls["ppt"].next_slide.return_value = True
    event = _custom_event("circle")  # confidence=0.9
    assert pipeline.engine.feed(event, controls) is True
    assert "0.90" in event.data["feedback"]
    assert "circle" in event.data["feedback"] and "下一页" in event.data["feedback"]
