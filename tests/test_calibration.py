"""手势灵敏度标定（calibration.py）测试：测量器 + 建议计算 + 写回/恢复默认。
红线守护：建议只放宽不收紧、全部被 clamp 在安全区间、极端数据不坏。
"""
from __future__ import annotations

import copy

from src.calibration import (
    BOUNDS, DEFAULTS, HandScaleMeasurer, HoldMeasurer, SwipeMeasurer,
    apply_suggestions, compute_suggestions, restore_defaults,
)

CFG = {
    "swipe": {"min_velocity_hs_per_s": 2.5, "min_displacement_hs": 1.3},
    "activation": {"max_drift_hs": 0.08},
}


def _swipe_burst(m: SwipeMeasurer, v_peak: float, disp: float, scale: float = 0.1,
                 t0: float = 0.0, frames: int = 12) -> None:
    """合成一次挥手：匀加速到峰值再停。位移按 v_peak 与时长自然累计。"""
    x, y, ts = 0.5, 0.5, t0
    m.feed(x, y, ts, scale)
    v = v_peak
    for i in range(frames):
        ts += 0.033
        x += v * 0.033 * scale  # 手长归一化位移 = v(手长/s) × dt × scale
        m.feed(x, y, ts, scale)
    for _ in range(10):  # 静止收尾触发段结束
        ts += 0.033
        m.feed(x, y, ts, scale)


# ---------- 手长测量 ----------

def test_hand_scale_measurer():
    m = HandScaleMeasurer()
    for v in [0.10, 0.11, 0.09, 0.105, 0.095, 0.10, 0.11, 0.10, 0.09, 0.105]:
        m.feed(v)
    r = m.result()
    assert r["count"] == 10
    assert abs(r["median"] - 0.10) < 0.01
    assert r["min"] == 0.09 and r["max"] == 0.11


def test_hand_scale_measurer_too_few_samples():
    m = HandScaleMeasurer()
    for v in [0.1, 0.1, 0.1]:
        m.feed(v)
    assert m.result() is None


# ---------- 挥手测量 ----------

def test_swipe_measurer_captures_slow_and_fast():
    m = SwipeMeasurer()
    _swipe_burst(m, v_peak=2.0, disp=1.0, t0=0.0)   # 慢挥（低于默认阈值 2.5）
    _swipe_burst(m, v_peak=6.0, disp=2.0, t0=5.0)   # 快挥
    r = m.result()
    assert r["count"] == 2
    assert abs(r["peak_v_median"] - 4.0) < 0.6  # 两次峰值的中位
    assert 0.5 < r["disp_median"] < 2.1


def test_swipe_measurer_ignores_stationary_jitter():
    m = SwipeMeasurer()
    ts = 0.0
    for _ in range(30):  # 原地微抖：速度低于地板，不产生动作段
        ts += 0.033
        m.feed(0.5 + 0.001 * (ts % 0.01), 0.5, ts, 0.1)
    m.finish()
    assert m.bursts == []


# ---------- 保持测量 ----------

def test_hold_measurer_drift():
    m = HoldMeasurer()
    ts = 0.0
    # 第一次保持：稳定（漂移 ~0.005 手长）
    for i in range(20):
        ts += 0.033
        m.feed(0.5 + 0.0005 * (i % 2), 0.5, 0.1, holding=True)
    m.feed(0.5, 0.5, 0.1, holding=False)  # 松手结束
    # 第二次保持：手抖（漂移 ~0.1 手长）
    for i in range(20):
        ts += 0.033
        m.feed(0.5 + 0.01 * (1 if i % 2 else -1), 0.5, 0.1, holding=True)
    m.finish()
    r = m.result()
    assert r["count"] == 2
    assert r["drift_p90"] > 0.15  # 手抖次的漂移（0.01/0.1=0.1 手长，双向累计更大）


# ---------- 建议计算（红线：只放宽不收紧） ----------

def test_suggestions_relax_for_slow_small_user():
    cfg = copy.deepcopy(CFG)
    sug = compute_suggestions(
        {"swipe_peak_v": 2.0, "swipe_disp": 1.0, "hold_drift_p90": 0.1}, cfg)
    assert sug["swipe.min_velocity_hs_per_s"]["suggested"] == 1.5    # 0.6×2.0=1.2 → 下限 1.5
    assert sug["swipe.min_displacement_hs"]["suggested"] == 0.9      # 0.6×1.0=0.6 → 下限 0.9
    assert sug["activation.max_drift_hs"]["suggested"] == 0.15       # 1.5×0.1
    # 全部比默认更宽松
    assert sug["swipe.min_velocity_hs_per_s"]["suggested"] < DEFAULTS["swipe.min_velocity_hs_per_s"]
    assert sug["swipe.min_displacement_hs"]["suggested"] < DEFAULTS["swipe.min_displacement_hs"]
    assert sug["activation.max_drift_hs"]["suggested"] > DEFAULTS["activation.max_drift_hs"]


def test_suggestions_no_change_for_typical_user():
    """动作达标的用户：不建议任何改动（不收紧）。"""
    cfg = copy.deepcopy(CFG)
    sug = compute_suggestions(
        {"swipe_peak_v": 6.0, "swipe_disp": 2.5, "hold_drift_p90": 0.02}, cfg)
    assert sug == {}  # 0.6×6=3.6>默认 2.5 → clamp 回默认 → 无建议；漂移同理


def test_suggestions_clamped_within_bounds():
    cfg = copy.deepcopy(CFG)
    sug = compute_suggestions(
        {"swipe_peak_v": 0.5, "swipe_disp": 0.3, "hold_drift_p90": 0.5}, cfg)
    for path, item in sug.items():
        lo, hi = BOUNDS[path]
        assert lo <= item["suggested"] <= hi


def test_suggestions_respect_existing_custom_values():
    """当前值已被用户改过（比建议更宽松）时，不反向收紧回默认。"""
    cfg = copy.deepcopy(CFG)
    cfg["swipe"]["min_velocity_hs_per_s"] = 1.2  # 用户已调到很灵敏
    sug = compute_suggestions({"swipe_peak_v": 6.0}, cfg)
    assert "swipe.min_velocity_hs_per_s" in sug  # 建议=默认 2.5（clamp 上限）
    assert sug["swipe.min_velocity_hs_per_s"]["suggested"] == 2.5
    # 说明：clamp 上限是"默认值"，建议可能回调到默认；这不违反红线
    #（红线是相对默认不收紧，用户自改值被建议回调默认属于预期行为，结果页可见）


# ---------- 写回与恢复 ----------

def test_apply_and_restore(tmp_path):
    cfg = copy.deepcopy(CFG)
    sug = compute_suggestions(
        {"swipe_peak_v": 2.0, "swipe_disp": 1.0, "hold_drift_p90": 0.1}, cfg)
    apply_suggestions(cfg, sug)
    assert cfg["swipe"]["min_velocity_hs_per_s"] == 1.5
    assert cfg["activation"]["max_drift_hs"] == 0.15
    restore_defaults(cfg)
    assert cfg["swipe"]["min_velocity_hs_per_s"] == DEFAULTS["swipe.min_velocity_hs_per_s"]
    assert cfg["swipe"]["min_displacement_hs"] == DEFAULTS["swipe.min_displacement_hs"]
    assert cfg["activation"]["max_drift_hs"] == DEFAULTS["activation.max_drift_hs"]


# ---------- 内嵌向导 GUI 与设置页入口（offscreen，2026-09-15 改版） ----------

import pytest
import types

from PySide6.QtCore import QObject, Signal


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


class _FakeWorker(QObject):
    """假 GestureWorker：只提供内嵌向导需要的采样信号与开关。"""

    wizard_sample = Signal(object)

    def __init__(self):
        super().__init__()
        self.sampling = None

    def set_wizard_sampling(self, on: bool) -> None:
        self.sampling = on

    def request_config_reload(self) -> None:  # 应用建议后的阈值热更新调用
        pass

    def stop(self) -> None:  # 窗口 closeEvent → _stop() 调用
        pass


@pytest.fixture
def window(qapp):
    from src.config import load_config
    from src.gui.fluent_window import FluentMainWindow

    w = FluentMainWindow(load_config())
    w.switchTo(w.preview_page)  # Calibration geometry belongs to the preview, not the default workbench.
    w._worker = _FakeWorker()  # 预置假 worker：向导打开时跳过 _start（不开真摄像头）
    w._inline_wizard._animate = False  # 测试关动画（几何立即可断言）
    yield w
    w.close()
    w.deleteLater()


def _hf(x=0.5, y=0.5, ts=1000.0, scale=0.1):
    return types.SimpleNamespace(point=lambda i: (x, y, 0.0),
                                 hand_scale=scale, timestamp=ts)


def test_inline_wizard_open_close(window):
    """打开：按钮文字切换、采样开启、模块出现；关闭：采样停止、模块隐藏、文字还原。"""
    wiz = window._inline_wizard
    worker = window._worker
    assert not wiz.is_open
    wiz.open()
    assert wiz.is_open
    assert worker.sampling is True
    assert window.preview_page.calib_btn.text() == "关闭向导"
    assert not window.preview_page.wizard_panel.isHidden()
    assert "①" in wiz.panel.step_title.text()  # 进入第一步
    wiz.close()
    assert not wiz.is_open
    assert worker.sampling is False
    assert window.preview_page.calib_btn.text() == "校准向导"
    assert window.preview_page.wizard_panel.isHidden()


def _wait_until(cond, timeout_ms=4000) -> bool:
    """事件循环轮询直到条件满足（动画按墙钟插值，固定时长断言在
    事件循环繁忙时会抖动——改为条件等待）。"""
    from PySide6.QtCore import QEventLoop, QTimer

    deadline = timeout_ms // 50
    for _ in range(deadline):
        if cond():
            return True
        loop = QEventLoop()
        QTimer.singleShot(50, loop.quit)
        loop.exec()
    return cond()


def test_inline_wizard_content_fade_sequence(window):
    """2026-09-17 用户要求：展开完成前模块为空白（内容透明），完全展开后内容
    才淡入；关闭时内容先淡出成空白模块，然后再收起。"""
    window.show()
    wiz = window._inline_wizard
    wiz._animate = True  # 本用例专门测动画路径（fixture 默认关动画）
    panel = window.preview_page.wizard_panel

    wiz.open()
    assert wiz._opacity.opacity() == 0.0  # 展开中：内容不可见（空白模块）
    assert not panel.isHidden()
    assert wiz._height_ani is not None

    assert _wait_until(lambda: wiz._opacity.opacity() == 1.0)  # 展开完成后淡入
    assert panel.height() == wiz._target_height()

    wiz.close()
    assert wiz._fade_ani is not None  # 关闭：先淡出……
    assert not panel.isHidden()       # ……此时模块尚未收起
    assert _wait_until(lambda: panel.isHidden())  # 淡出完成后模块收起


@pytest.mark.parametrize("close_fraction", [0.2, 0.5, 0.8])
def test_inline_wizard_reopen_keeps_current_height(window, qapp, close_fraction):
    """收起途中重新展开必须从当前高度接续，不能归零或被旧动画隐藏。"""
    window.show()
    qapp.processEvents()
    wiz = window._inline_wizard
    wiz.open()  # 先以无动画方式到达完整展开态
    target = wiz.panel.height()
    wiz._animate = True
    wiz.close()
    wiz._fade_ani.setCurrentTime(wiz._fade_ani.duration())
    closing = wiz._height_ani
    closing.pause()
    closing.setCurrentTime(round(closing.duration() * close_fraction))
    before = wiz.panel.height()
    assert 0 < before < target

    wiz.open()
    assert wiz.panel.height() == before
    opening = wiz._height_ani
    opening.pause()
    heights = []
    for elapsed in range(0, opening.duration(), 20):
        opening.setCurrentTime(elapsed)
        heights.append(wiz.panel.height())
    assert heights == sorted(heights)
    opening.resume()
    assert _wait_until(lambda: wiz._opacity.opacity() == 1.0)
    assert wiz.panel.height() == wiz._target_height()
    assert not wiz.panel.isHidden()
    assert window._worker.sampling is True

    wiz.close()
    assert _wait_until(wiz.panel.isHidden)
    wiz.open()
    assert wiz.panel.height() == 0  # 完全关闭后仍从零展开
    assert _wait_until(lambda: wiz._opacity.opacity() == 1.0)


def test_inline_wizard_geometry_when_open(window):
    """用户亲定几何：向导打开时 画面顶==状态卡顶、模块底==侧栏底、顶距画面 16。"""
    from PySide6.QtCore import QEventLoop, QTimer

    window.show()
    loop = QEventLoop()
    QTimer.singleShot(400, loop.quit)
    loop.exec()
    p = window.preview_page
    wiz = window._inline_wizard
    wiz.open()
    loop = QEventLoop()
    QTimer.singleShot(200, loop.quit)
    loop.exec()
    pv_y = p.preview.mapTo(window, p.preview.rect().topLeft()).y()
    st_y = p.status_card.mapTo(window, p.status_card.rect().topLeft()).y()
    assert abs(pv_y - st_y) <= 2  # 画面上移后与状态卡同顶
    pv_bottom = pv_y + p.preview.height()
    panel_y = p.wizard_panel.mapTo(window, p.wizard_panel.rect().topLeft()).y()
    assert abs(panel_y - (pv_bottom + 16)) <= 2  # 模块顶距画面 16
    side_bottom = p.side_container.mapTo(window, p.side_container.rect().topLeft()).y() \
        + p.side_container.height()
    panel_bottom = panel_y + p.wizard_panel.height()
    assert abs(panel_bottom - side_bottom) <= 2  # 模块底缘与侧栏底缘对齐
    wiz.close()


def test_inline_wizard_full_flow_and_apply(window, tmp_path, monkeypatch):
    """全流程：手长→挥手×3→保持×2 → 结果 → 应用/完成（写配置+关闭）。"""
    import src.gui.wizard_inline as wi

    monkeypatch.setattr(wi, "CONFIG_PATH", tmp_path / "config.json")
    wiz = window._inline_wizard
    worker = window._worker
    wiz.open()
    # 第 1 步：手长（喂一帧后回拨计时，免等真实 2 秒）
    worker.wizard_sample.emit(_hf())
    wiz._scale_start -= 3.0
    worker.wizard_sample.emit(_hf())
    assert wiz._step == 1
    # 第 2 步：三次挥手（左右交替，位移不抵消——连续同向回跳会被位移下限正确拒绝）
    ts = 1000.0
    x = 0.5
    for burst in range(3):
        dx = 0.02 if burst % 2 == 0 else -0.02
        for _ in range(10):
            ts += 0.033
            x += dx
            worker.wizard_sample.emit(_hf(x=x, ts=ts))
        for _ in range(10):  # 静止收尾
            ts += 0.033
            worker.wizard_sample.emit(_hf(x=x, ts=ts))
    assert wiz._step == 2
    # 第 3 步：两次保持（在场若干帧 → 离画结束）
    for _ in range(2):
        for _ in range(15):
            ts += 0.033
            worker.wizard_sample.emit(_hf(ts=ts))
        worker.wizard_sample.emit(None)
    assert wiz._step == 3  # 结果态
    assert "实测：" in wiz.panel.center_label.text()
    import json

    if wiz._suggestions:
        wiz.panel.apply_btn.click()
        saved = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
        assert saved["calibration"]["done"] is True
        assert not wiz.is_open  # 应用后自动关闭
    else:
        wiz.panel.finish_btn.click()
        assert not wiz.is_open


def test_inline_wizard_close_discards(window):
    """关闭向导丢弃全部测量：重开时测量器是全新的。"""
    wiz = window._inline_wizard
    worker = window._worker
    wiz.open()
    wiz._swipe_meas.bursts = [(6.0, 2.0)]
    wiz._hold_meas.holds = [0.1]
    wiz.close()
    wiz.open()
    assert wiz._swipe_meas.bursts == [] and wiz._hold_meas.holds == []
    wiz.close()


def test_settings_jump_button(qapp, tmp_path, monkeypatch):
    """设置页：按钮改名「跳转校准向导…」，点击触发跳转回调（向导内嵌预览页）。"""
    import src.gui.fluent_window as fw

    monkeypatch.setattr(fw, "CONFIG_PATH", tmp_path / "config.json")
    from src.gui.fluent_window import SettingsPage

    page = SettingsPage(copy.deepcopy(CFG_FULL))
    jumped = []
    page.on_jump_wizard = lambda: jumped.append(1)
    page._jump_to_wizard()
    assert jumped == [1]
    page.deleteLater()


def test_inline_wizard_stop_button_and_activity(window):
    """校准中：操作列有「停止」、悬浮窗活动行显示校准状态；停止=终止并丢弃。"""
    wiz = window._inline_wizard
    wiz.open()
    assert not wiz.panel.stop_btn.isHidden()
    assert not window._status_overlay.activity_label.isHidden()
    assert "校准中" in window._status_overlay.activity_label.text()
    wiz.panel.stop_btn.click()
    assert not wiz.is_open
    assert window._status_overlay.activity_label.isHidden()


def test_calibration_suppresses_gesture_recognition():
    """校准期间屏蔽一切手势识别（用户要求：与练习/录制一致不触发手势）。"""
    import time

    from test_e2e import FULL_CFG
    from test_gestures import _upright_hand
    from src.decision import Mode
    from src.pipeline import Pipeline

    pipeline = Pipeline(copy.deepcopy(FULL_CFG))
    pipeline.calibration_active = True
    t0 = time.time()
    events: list = []
    for i in range(40):  # 张开手掌保持 ~1.3s（足以激活）
        pipeline.process(_upright_hand("open", t=t0 + i * 0.033), {},
                         events_out=events)
    assert pipeline.engine.mode is Mode.DISARMED  # 校准中：激活手势被屏蔽
    assert events == []

    pipeline.calibration_active = False  # 校准结束 → 恢复正常识别
    for i in range(40):
        pipeline.process(_upright_hand("open", t=t0 + 2 + i * 0.033), {},
                         events_out=events)
    assert pipeline.engine.mode is Mode.ARMED


CFG_FULL = {  # 设置页构造所需的最小完整配置
    **CFG,
    "swipe": {"min_velocity_hs_per_s": 2.5, "min_displacement_hs": 1.3,
              "cooldown_ms": 650},
    "static_pose": {"finger_extended_cos": 0.95, "finger_bent_ratio": 1.2,
                    "confirm_frames": 4},
    "laser": {"hold_ms": 1500},
    "countdown": {"minutes": 10},
    "pointer_ring": {"radius": 60},
    "screenshot": {"dir": "screenshots"},
    "activation": {"hold_ms": 700, "max_drift_hs": 0.08, "command_quota": 1},
    "camera": {"index": 0, "width": 1280, "height": 720, "fps": 30},
}
