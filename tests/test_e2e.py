"""端到端集成测试：合成关键点序列 → 完整管线（Pipeline）→ mock 控制层。

验证"激活 → 翻页 → 激光笔唤起/退出"全链路的指令顺序与模式转换，
覆盖 SPEC 4.2 核心接口的集成行为（不依赖摄像头/PowerPoint/Qt）。
"""
from __future__ import annotations

from unittest.mock import MagicMock

from test_gestures import _upright_hand, make_hand

from src.decision import Mode
from src.pipeline import Pipeline

FULL_CFG = {
    "camera": {"index": 0, "width": 1280, "height": 720, "fps": 30},
    "tracking": {"max_num_hands": 1, "model_complexity": 0,
                 "min_detection_confidence": 0.7, "min_tracking_confidence": 0.6},
    "static_pose": {"finger_extended_cos": 0.95, "finger_bent_ratio": 1.2, "confirm_frames": 2},
    "activation": {"hold_ms": 700, "max_drift_hs": 0.08},
    "swipe": {"window_ms": 260, "min_velocity_hs_per_s": 2.5, "min_displacement_hs": 1.3,
              "gap_bridge_ms": 160, "teleport_hs": 1.6, "cooldown_ms": 650,
              "reverse_cooldown_ms": 1300, "rearm_velocity_hs_per_s": 1.8},
    "laser": {"hold_ms": 1000, "region_x_min": 0.15, "region_x_max": 0.85,
              "region_y_min": 0.15, "region_y_max": 0.85,
              "one_euro_min_cutoff": 1.0, "one_euro_beta": 0.5, "track_loss_grace_ms": 280,
              "dot_radius": 8, "trail_ms": 1000},
    "zoom": {"backend": "native", "step_scroll_units": 1,
             "hysteresis_low": 0.7, "hysteresis_high": 1.4, "slide_speed_hs_per_s": 2.0},
    "tap": {"max_duration_ms": 300, "min_dip_hs": 0.25, "max_lateral_hs": 0.15},
    "blackout": {"cover_scale": 0.45, "hold_ms": 400},
    "pinch": {"pinch_hs": 0.25, "confirm_frames": 3},
    "nav": {"hold_ms": 1500},
    "spotlight": {"hold_ms": 1000, "radius": 150},
    "twohand": {"enabled": False, "delta_hs": 0.6, "cooldown_ms": 800},
    "features": {"flip": True, "zoom": True, "laser": True, "tap": True,
                 "blackout": True, "nav": True, "spotlight": True},
    "magnifier": {"window_size": 480, "factor": 2.0, "refresh_ms": 32, "idle_ms": 1000},
}

FPS = 30
DT = 1.0 / FPS


def _feed_seconds(pipeline, controls, hand_factory, seconds, t):
    """以 30fps 连续喂 seconds 秒的同构帧，返回结束时间戳。"""
    for _ in range(int(seconds * FPS)):
        t += DT
        pipeline.process(hand_factory(t), controls)
    return t


def test_full_chain_activate_swipe_laser():
    pipeline = Pipeline(FULL_CFG, with_controls=True, screen_size=(1920, 1080))
    ppt = MagicMock()
    ppt.next_slide.return_value = True
    ppt.prev_slide.return_value = True
    kb = MagicMock()
    kb.zoom_scroll.return_value = True
    controls = {"ppt": ppt, "keyboard": kb}

    t = 0.0
    # 1) 未激活挥手：不应翻页
    for i in range(8):  # 快速左挥
        t += DT
        x = 0.7 - 0.5 * i / 7
        pipeline.process(make_hand((x, 0.5), scale=0.25, t=t), controls)
    for _ in range(5):  # 静止结算（完成式判定）
        t += DT
        pipeline.process(make_hand((0.2, 0.5), scale=0.25, t=t), controls)
    ppt.next_slide.assert_not_called()

    # 2) 张开手掌保持 → 激活（挥手宽限期内保持无效，先握拳等待宽限期结束）
    t = _feed_seconds(pipeline, controls, lambda ts: _upright_hand("fist", t=ts), 0.8, t)
    t = _feed_seconds(pipeline, controls, lambda ts: _upright_hand("open", t=ts), 1.0, t)
    assert pipeline.engine.mode is Mode.ARMED

    # 3) 激活后挥手 → 翻页（从当前手位连续挥动，x 无跳变——模拟真实动作）
    t = _feed_seconds(pipeline, controls, lambda ts: _upright_hand("open", t=ts), 0.8, t)
    for i in range(9):  # 快速左挥（下一页）
        t += DT
        x = 0.5 - 0.45 * i / 8
        pipeline.process(make_hand((x, 0.5), scale=0.25, t=t), controls)
    ppt.next_slide.assert_called_once()

    # 4) ✌️ 保持 1 秒 → 唤起激光笔（先握拳等待冷却/宽限期结束 + re-arm；
    #    注意不能张开手掌等待——那会被正确识别为退出激活）
    t = _feed_seconds(pipeline, controls, lambda ts: _upright_hand("fist", t=ts), 1.5, t)
    t = _feed_seconds(pipeline, controls, lambda ts: _upright_hand("victory", t=ts), 1.2, t)
    assert pipeline.engine.mode is Mode.LASER
    kb.laser_on.assert_called_once()

    # 5) 激光笔模式下挥手 → 不翻页；指尖移动 → 移动鼠标
    ppt.next_slide.reset_mock()
    for i in range(9):
        t += DT
        pipeline.process(make_hand((0.7 - 0.5 * i / 8, 0.5), scale=0.25, t=t), controls)
    ppt.next_slide.assert_not_called()
    assert kb.move_to.called

    # 6) 先握拳（松开 ✌️ 让检测器复位 + 等待宽限期结束），再做 OK 手势 → 退出激光笔恢复箭头
    t = _feed_seconds(pipeline, controls, lambda ts: _upright_hand("fist", t=ts), 0.7, t)
    t = _feed_seconds(pipeline, controls, lambda ts: _upright_hand("ok", t=ts), 0.6, t)
    assert pipeline.engine.mode is Mode.ARMED
    kb.arrow_on.assert_called_once()


def test_zoom_chain():
    pipeline = Pipeline(FULL_CFG, with_controls=True, screen_size=(1920, 1080))
    ppt = MagicMock()
    kb = MagicMock()
    kb.zoom_scroll.return_value = True
    controls = {"ppt": ppt, "keyboard": kb}

    t = 0.0
    t = _feed_seconds(pipeline, controls, lambda ts: _upright_hand("open", t=ts), 1.0, t)
    assert pipeline.engine.mode is Mode.ARMED
    # 握拳（稳定）→ 张开：FIST_OPEN → 进入缩放模式 + 放大
    t = _feed_seconds(pipeline, controls, lambda ts: _upright_hand("fist", t=ts), 0.3, t)
    t = _feed_seconds(pipeline, controls, lambda ts: _upright_hand("open", t=ts), 0.3, t)
    assert pipeline.engine.mode is Mode.ZOOM
    kb.zoom_scroll.assert_called_with(1)
    # v2：OK 手势退出缩放并恢复原始大小
    t = _feed_seconds(pipeline, controls, lambda ts: _upright_hand("ok", t=ts), 0.6, t)
    assert pipeline.engine.mode is Mode.ARMED
    assert kb.zoom_scroll.call_count == 2  # 一次放大 + 一次恢复
