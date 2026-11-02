"""自定义手势 v2 回归测试（2026-09-12 实测反馈：训练成功、已绑定指令，
但激活后做动作零反应——诊断工具 tools/diagnose_custom_gesture.py 定位的三个根因）。

锁死三个修复：
1. 收笔多路化：画完后手丢失超时 / 静止减速也要能收笔（原来只有"换明确手型×N帧"一条路，
   自然垂手/保持不动 = 笔画永不结束 = 识别从未发生）；
2. 作画优先权：食指作画（有点数且有移动量）期间挂起导航保持检测器——
   原来画圈超过 1.5s 会被「食指保持唤导航」抢占并切走模式，识别器随之停喂；
3. 拒绝反馈：轨迹被捕获但置信度不足时必须给用户可见原因（原来是静默吞掉）。

全部合成数据，不依赖摄像头。
"""
from __future__ import annotations

import copy
import csv
import math
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np

from test_e2e import FULL_CFG
from test_gestures import _upright_hand

from src.decision import GestureType, Mode
from src.gestures.static_pose import Pose
from src.gestures.trajectory import CustomGestureDetector, train_from_directory
from src.pipeline import Pipeline

CFG = dict(FULL_CFG)
CFG["custom_gestures"] = {"enabled": True, "min_points": 8, "min_path_hs": 1.0,
                          "stroke_end_frames": 2, "prob_threshold": 0.5, "mapping": {},
                          "end_still_ms": 400, "lost_end_ms": 450,
                          "end_velocity_hs_per_s": 0.5}

FPS = 30
DT = 1.0 / FPS


def _circle(n=90, radius=0.10, center=(0.5, 0.30)):
    """默认 90 点 ≈ 3 秒（故意超过导航唤起的 1.5s 保持时长，复现抢占场景）。

    注意合成手的几何一致性：_upright_hand 的食指 MCP/PIP 固定在 y≈0.55/0.44，
    指尖必须始终位于 PIP 上方（伸直语义），否则指节向量反转会被分类器判成
    握拳（真实手的指节会跟随移动，这里只能抬高圆心来等效）。
    """
    return [(center[0] + radius * math.cos(2 * math.pi * i / n),
             center[1] + radius * math.sin(2 * math.pi * i / n)) for i in range(n)]


def _index_hand(tip_xy, scale=0.2, t=0.0):
    hf = _upright_hand("index", scale=scale, t=t)  # 腕点固定不动（最利于导航计时的情况）
    hf.landmarks[8] = (tip_xy[0], tip_xy[1], 0.0)
    return hf


def _fist_hand(knuckle_xy, scale=0.2, t=0.0):
    hf = _upright_hand("fist", scale=scale, t=t)
    hf.landmarks[9] = (knuckle_xy[0], knuckle_xy[1], 0.0)
    return hf


def _write_samples(root: Path, name: str, generator, count: int) -> None:
    d = root / name
    d.mkdir(parents=True)
    for i in range(count):
        with open(d / f"{i}.csv", "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(generator())


def _trained_model(tmp_path):
    np.random.seed(42)
    _write_samples(tmp_path, "circle",
                   lambda: _circle(90, radius=0.10 + 0.03 * np.random.rand()), 10)
    model, _report = train_from_directory(tmp_path, seed=0)
    model.save(tmp_path / "model.json")
    return model


# ---------- 根因 1：收笔多路化 ----------

def test_stroke_finalizes_on_hand_lost(tmp_path):
    """画完垂手（手出画/丢帧超过 lost_end_ms）→ 强制收笔并识别。
    修复前：丢帧被无限桥接，笔画永不结束，零反应。"""
    _trained_model(tmp_path)
    det = CustomGestureDetector(tmp_path / "model.json", CFG)
    event = None
    t = 0.0
    for x, y in _circle(30):  # 1 秒画完
        t += DT
        event = det.feed(_index_hand((x, y), t=t), Pose.INDEX) or event
    assert event is None  # 画完尚未收笔
    for _ in range(16):  # 手丢失 533ms > lost_end_ms=450
        t += DT
        event = det.feed(None, Pose.UNKNOWN, now=t) or event
    assert event is not None and event.data["name"] == "circle"


def test_short_loss_gap_still_bridges(tmp_path):
    """回归保护：运动模糊的短暂丢帧（< lost_end_ms）仍桥接，不得误收笔。"""
    _trained_model(tmp_path)
    det = CustomGestureDetector(tmp_path / "model.json", CFG)
    event = None
    t = 0.0
    points = _circle(30)
    for i, (x, y) in enumerate(points):
        t += DT
        event = det.feed(_index_hand((x, y), t=t), Pose.INDEX) or event
        if i == 10:  # 中途丢 4 帧（133ms）→ 应桥接而非收笔
            for _ in range(4):
                t += DT
                assert det.feed(None, Pose.UNKNOWN, now=t) is None
    for _ in range(4):  # 明确握拳收笔（stroke_end_frames=2）
        t += DT
        event = det.feed(_fist_hand((0.5, 0.5), t=t), Pose.OPEN_PALM) or event
    assert event is not None and event.data["name"] == "circle"


def test_stroke_finalizes_on_stillness(tmp_path):
    """画完保持食指不动（速度 < 阈值持续 end_still_ms）→ 收笔识别。
    修复前：手型没变 = 永不收笔，零反应。"""
    _trained_model(tmp_path)
    det = CustomGestureDetector(tmp_path / "model.json", CFG)
    event = None
    t = 0.0
    last = None
    for x, y in _circle(30):
        t += DT
        last = (x, y)
        event = det.feed(_index_hand(last, t=t), Pose.INDEX) or event
    for _ in range(15):  # 静止 500ms > end_still_ms=400
        t += DT
        event = det.feed(_index_hand(last, t=t), Pose.INDEX) or event
    assert event is not None and event.data["name"] == "circle"


# ---------- 根因 2：作画优先权（导航不得抢占） ----------

def test_slow_drawing_not_hijacked_by_nav(tmp_path):
    """食指慢速画圈 3 秒（超过 nav.hold_ms=1500）：不得触发 NAV_TOGGLE，
    不得切走模式，笔画正常收笔并执行自定义指令。"""
    _trained_model(tmp_path)
    cfg = copy.deepcopy(CFG)
    cfg["custom_gestures"]["mapping"] = {"circle": "next_page"}
    pipeline = Pipeline(cfg, with_controls=True, screen_size=(1920, 1080))
    pipeline.custom_detector = CustomGestureDetector(tmp_path / "model.json", cfg)
    ppt = MagicMock()
    ppt.next_slide.return_value = True
    ppt.is_running_cached.return_value = True
    controls = {"ppt": ppt, "keyboard": MagicMock()}
    pipeline.engine.mode = Mode.ARMED
    events: list = []
    t = 100.0
    for x, y in _circle(90):  # 3 秒慢画（修复前：1.5s 时 NAV_TOGGLE 抢占）
        t += DT
        pipeline.process(_index_hand((x, y), t=t), controls, events_out=events)
    for _ in range(6):  # 握拳以外的明确手型收笔（张开）
        t += DT
        pipeline.process(_upright_hand("open", t=t), controls, events_out=events)
    types = [e.type for e in events]
    assert GestureType.NAV_TOGGLE not in types, "作画期间导航保持检测器必须挂起"
    assert GestureType.CUSTOM_GESTURE in types
    assert ppt.next_slide.called


def test_nav_hold_still_still_works():
    """回归保护：食指静止保持 1.5s+ 仍正常唤起导航（静止不动 ≠ 作画，不得屏蔽）。"""
    pipeline = Pipeline(CFG, with_controls=True, screen_size=(1920, 1080))
    pipeline.custom_detector._model = MagicMock()  # available=True 即可，无需真模型
    kb = MagicMock()
    controls = {"ppt": MagicMock(), "keyboard": kb}
    ppt = controls["ppt"]
    ppt.is_running_cached.return_value = True
    pipeline.engine.mode = Mode.ARMED
    events: list = []
    t = 200.0
    for _ in range(60):  # 2 秒静止保持
        t += DT
        pipeline.process(_index_hand((0.5, 0.4), t=t), controls, events_out=events)
    assert GestureType.NAV_TOGGLE in [e.type for e in events]


# ---------- 根因 3：拒绝反馈 ----------

def test_rejected_stroke_gives_feedback(tmp_path):
    """轨迹被捕获但置信度不足/命中拒绝类 → feedback_fn 收到「未识别+原因」，
    不耗配额、不弹成功 Toast（原来静默吞掉，用户不知道发生了什么）。"""
    _trained_model(tmp_path)
    cfg = copy.deepcopy(CFG)
    cfg["custom_gestures"]["mapping"] = {"circle": "next_page"}
    pipeline = Pipeline(cfg, with_controls=True, screen_size=(1920, 1080))
    pipeline.custom_detector = CustomGestureDetector(tmp_path / "model.json", cfg)
    ppt = MagicMock()
    ppt.is_running_cached.return_value = True
    fb = MagicMock()
    controls = {"ppt": ppt, "keyboard": MagicMock(), "feedback_fn": fb}
    pipeline.engine.mode = Mode.ARMED
    t = 300.0
    # 画一条之字形随机轨迹（与 circle 不像）
    zigzag = [(0.3 + 0.02 * i, 0.4 + (0.12 if i % 2 else -0.12)) for i in range(25)]
    for x, y in zigzag:
        t += DT
        pipeline.process(_index_hand((x, y), t=t), controls)
    for _ in range(6):  # 收笔
        t += DT
        pipeline.process(_upright_hand("open", t=t), controls)
    msgs = " ".join(str(c.args[0]) for c in fb.call_args_list if c.args)
    assert "未识别" in msgs or "拒绝" in msgs or "不像" in msgs, f"缺少拒绝反馈，实际：{msgs!r}"
    assert not ppt.next_slide.called  # 拒绝不执行指令
    assert pipeline.engine.mode is Mode.ARMED  # 拒绝不耗配额


# ---------- 双引擎仲裁（$1 模板匹配 + MLP，RESEARCH_ROUND3 第三节） ----------

def test_templates_only_recognition_without_training(tmp_path):
    """$1 免训练路径：只有样本、从未训练（无 model.json）也能识别——
    录完样本即时生效（调研：$1 单模板即 97% 准确率）。"""
    np.random.seed(43)
    _write_samples(tmp_path, "circle",
                   lambda: _circle(90, radius=0.10 + 0.03 * np.random.rand()), 6)
    det = CustomGestureDetector(tmp_path / "model.json", CFG)  # model.json 不存在
    assert det.available  # $1 模板库在场即可用
    event = None
    t = 0.0
    for x, y in _circle(30):
        t += DT
        event = det.feed(_index_hand((x, y), t=t), Pose.INDEX) or event
    for _ in range(4):
        t += DT
        event = det.feed(_fist_hand((0.5, 0.5), t=t), Pose.OPEN_PALM) or event
    assert event is not None and event.data["name"] == "circle"


def test_dual_engine_disagreement_rejects(tmp_path):
    """仲裁铁律：双引擎结论不一致 = 拒绝（误触防线），拒绝明细含两引擎数据。"""
    _trained_model(tmp_path)
    det = CustomGestureDetector(tmp_path / "model.json", CFG)
    # 人为制造分歧：$1 引擎认为最像另一个手势
    det._dollar.recognize = lambda points: {"label": "打勾", "score": 0.90,
                                            "second_label": "circle", "second_score": 0.50,
                                            "margin": 0.40}
    event = None
    t = 0.0
    for x, y in _circle(30):
        t += DT
        event = det.feed(_index_hand((x, y), t=t), Pose.INDEX) or event
    for _ in range(4):
        t += DT
        event = det.feed(_fist_hand((0.5, 0.5), t=t), Pose.OPEN_PALM) or event
    assert event is None  # 双引擎不一致 → 拒绝
    rej = det.pop_rejection()
    assert rej is not None
    assert rej["mlp_label"] == "circle" and rej["dollar_label"] == "打勾"
    assert rej["mlp_prob"] > 0 and rej["dollar_score"] > 0
