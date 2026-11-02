"""决策层状态机测试：模式互斥规则（PLAN 步骤 12，PRD 5.1）。"""
from __future__ import annotations

from src.decision import (
    CommandRegistry, DecisionEngine, GestureEvent, GestureType, Mode,
)


def _engine():
    calls: list[GestureType] = []
    registry = CommandRegistry()
    for g in GestureType:
        if g is not GestureType.NONE:
            registry.register(g, lambda e, c, calls=calls: calls.append(e.type))
    return DecisionEngine(config={}, registry=registry), calls


def _feed(engine, g: GestureType):
    return engine.feed(GestureEvent.now(g), controls={})


def test_swipe_suspended_in_laser_mode():
    engine, calls = _engine()
    _feed(engine, GestureType.ACTIVATE)          # -> ARMED
    _feed(engine, GestureType.LASER_TOGGLE)      # -> LASER
    assert engine.mode is Mode.LASER
    assert _feed(engine, GestureType.SWIPE_LEFT) is False   # 挥手挂起
    assert GestureType.SWIPE_LEFT not in calls


def test_zoom_mode_enter_and_exit():
    engine, calls = _engine()
    _feed(engine, GestureType.ACTIVATE)
    _feed(engine, GestureType.FIST_OPEN)         # -> ZOOM
    assert engine.mode is Mode.ZOOM
    assert _feed(engine, GestureType.SWIPE_RIGHT) is False  # 挥手挂起
    # v2.1：张开→握拳在缩放模式内允许分发（✌️ 切方向后的缩小档），不退出模式
    assert _feed(engine, GestureType.OPEN_FIST) is True
    assert engine.mode is Mode.ZOOM
    _feed(engine, GestureType.OK_EXIT)           # -> ARMED（OK 手势统一退出）
    assert engine.mode is Mode.ARMED
    assert GestureType.OK_EXIT in calls


def test_activate_exits_any_mode():
    engine, _ = _engine()
    _feed(engine, GestureType.ACTIVATE)
    _feed(engine, GestureType.LASER_TOGGLE)
    # v2：激活手势在模式内无效（防止缩放平移时误退出），须用 OK 手势退出模式
    assert _feed(engine, GestureType.ACTIVATE) is False
    assert engine.mode is Mode.LASER
    _feed(engine, GestureType.OK_EXIT)
    assert engine.mode is Mode.ARMED
    _feed(engine, GestureType.ACTIVATE)          # ARMED -> DISARMED
    assert engine.mode is Mode.DISARMED
    assert _feed(engine, GestureType.INDEX_TAP) is False    # 未激活全挂起


def test_laser_toggle_cycles_tools_and_ok_exits():
    """v2：✌️ 在激光笔模式内循环工具（不退出），OK 手势退出。"""
    engine, calls = _engine()
    _feed(engine, GestureType.ACTIVATE)
    _feed(engine, GestureType.LASER_TOGGLE)      # -> LASER
    _feed(engine, GestureType.LASER_TOGGLE)      # 模式内循环，不退出
    _feed(engine, GestureType.LASER_TOGGLE)
    assert engine.mode is Mode.LASER
    _feed(engine, GestureType.OK_EXIT)           # -> ARMED
    assert engine.mode is Mode.ARMED
    assert calls.count(GestureType.LASER_TOGGLE) == 3


def test_feature_gating_blocks_disabled_feature():
    engine, calls = _engine()
    engine.set_feature_enabled("flip", False)
    _feed(engine, GestureType.ACTIVATE)
    assert _feed(engine, GestureType.SWIPE_LEFT) is False   # 翻页功能已关
    assert GestureType.SWIPE_LEFT not in calls
    engine.set_feature_enabled("flip", True)
    assert _feed(engine, GestureType.SWIPE_LEFT) is True    # 重新开启后恢复
    # ACTIVATE 无开关，始终可用
    engine.set_feature_enabled("flip", False)
    assert _feed(engine, GestureType.ACTIVATE) is True
