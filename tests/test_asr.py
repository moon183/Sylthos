"""语音识别模块测试（SPEC 3.3 例外功能）：分段器 / WAV 编码 / 引擎工厂 /
在线客户端（mock HTTP）/ 字幕浮层 / GUI 页面 / 手势指令。

不依赖麦克风与真实网络（在线接口全部 mock urllib）。
"""
from __future__ import annotations

import base64
import copy
import json
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.asr.capture import MicSegmenter, encode_wav
from src.asr.base import create_engine

CFG = {
    "asr": {
        "enabled": True, "mode": "offline",
        "energy_threshold": 0.05, "silence_ms": 90,
        "offline": {"model_type": "sensevoice", "model_dir": "models/sensevoice"},
        "online": {"base_url": "http://example.invalid/asr", "api_key": "sk-test",
                   "model": "qwen-audio-turbo", "prompt": "转写", "segment_s": 25.0,
                   "timeout_s": 10},
        "subtitle": {"font_size": 28, "max_chars": 20},
    }
}


def _loud(n):
    """说话帧：能量起伏（真实语音高方差特征；恒定能量是噪音特征，
    会被噪音自适应判别为底噪——2026-09-13 噪音自适应 VAD 引入此约定）。"""
    _loud.i = getattr(_loud, "i", 0) + 1
    return np.full(n, 0.5 if _loud.i % 2 else 0.12, dtype=np.float32)


def _quiet(n):
    return np.zeros(n, dtype=np.float32)


# ---------- 分段器 ----------

def _feed(seg, frame, result):
    r = seg.feed(frame)
    return r if r is not None else result


def test_segmenter_pre_roll_keeps_speech_onset():
    """实测反馈：语音起始前的 150ms 预缓冲帧并入段首，句首不被削掉。"""
    seg = MicSegmenter(energy_threshold=0.05, silence_ms=90, frame_ms=30)
    for _ in range(5):  # 安静帧进入预缓冲
        assert seg.feed(_quiet(480)) is None
    result = None
    for _ in range(10):
        result = _feed(seg, _loud(480), result)
    for _ in range(3):
        result = _feed(seg, _quiet(480), result)
    assert result is not None
    assert len(result) > 480 * (10 + 5)  # 段首含 5 帧预缓冲


def test_subtitle_placeholder_when_empty(qapp):
    """实测反馈：无文字时字幕条也要画出底条和占位提示（否则等于没显示）。"""
    from src.overlay import SubtitleOverlay

    sub = SubtitleOverlay(CFG)
    sub.show()
    sub.repaint()  # 空状态 paintEvent 冒烟（画"正在聆听…"）
    sub.close()


def test_segmenter_emits_after_silence():
    seg = MicSegmenter(energy_threshold=0.05, silence_ms=90, frame_ms=30)
    result = None
    for _ in range(20):  # 600ms 说话
        result = _feed(seg, _loud(480), result)
    assert result is None  # 说话中不切段
    for _ in range(3):   # 90ms 静默
        result = _feed(seg, _quiet(480), result)
    assert result is not None and len(result) > 480 * 20


def test_segmenter_drops_short_segment():
    seg = MicSegmenter(energy_threshold=0.05, silence_ms=90, min_segment_s=0.5, frame_ms=30)
    result = None
    for _ in range(3):   # 只响 90ms（咳嗽）
        result = _feed(seg, _loud(480), result)
    for _ in range(4):
        result = _feed(seg, _quiet(480), result)
    assert result is None  # 过短丢弃


def test_segmenter_force_cut_long_segment():
    seg = MicSegmenter(energy_threshold=0.05, max_segment_s=1.0, frame_ms=30)
    result = None
    for _ in range(40):  # 持续说话 1.2s > 上限
        result = _feed(seg, _loud(480), result)
    assert result is not None


# ---------- WAV 编码 ----------

def test_encode_wav_header():
    data = encode_wav(_loud(1600))
    assert data[:4] == b"RIFF" and data[8:12] == b"WAVE"
    import io
    import wave

    with wave.open(io.BytesIO(data)) as wf:
        assert wf.getframerate() == 16000
        assert wf.getnchannels() == 1
        assert wf.getnframes() == 1600


# ---------- 引擎工厂与在线客户端 ----------

def test_factory_modes():
    offline = create_engine(CFG)
    assert type(offline).__name__ == "OfflineEngine"
    cfg = copy.deepcopy(CFG)
    cfg["asr"]["mode"] = "online"
    online = create_engine(cfg)
    assert type(online).__name__ == "DashScopeEngine"


def test_online_ready_requires_key():
    from src.asr.online import DashScopeEngine

    cfg = copy.deepcopy(CFG)
    cfg["asr"]["online"]["api_key"] = ""
    ok, _ = DashScopeEngine(cfg).ready()
    assert not ok
    ok, _ = DashScopeEngine(CFG).ready()
    assert ok


def test_online_payload_and_response():
    from src.asr.online import DashScopeEngine

    engine = DashScopeEngine(CFG)
    payload = json.loads(engine.build_payload(encode_wav(_loud(1600))).decode("utf-8"))
    assert payload["model"] == "qwen-audio-turbo"
    audio = payload["input"]["messages"][0]["content"][0]["audio"]
    assert audio.startswith("data:;base64,")
    base64.b64decode(audio.split(",", 1)[1])  # base64 合法
    assert payload["input"]["messages"][0]["content"][1]["text"] == "转写"

    fake_resp = json.dumps({"output": {"choices": [{"message": {
        "content": [{"text": "欢迎使用阿里云"}]}}]}}).encode("utf-8")
    assert engine.parse_response(fake_resp) == "欢迎使用阿里云"


def test_online_transcribe_mocked_http():
    from src.asr.online import DashScopeEngine

    engine = DashScopeEngine(CFG)
    fake = MagicMock()
    fake.read.return_value = json.dumps({"output": {"choices": [{"message": {
        "content": [{"text": "你好"}]}}]}}).encode("utf-8")
    fake.__enter__ = lambda s: s
    fake.__exit__ = MagicMock(return_value=False)
    with patch("urllib.request.urlopen", return_value=fake) as m:
        text = engine.transcribe(_loud(1600))
    assert text == "你好"
    req = m.call_args.args[0]
    assert req.headers["Authorization"] == "Bearer sk-test"


# ---------- 热词矫正 ----------

def test_hotword_corrector_replaces_near_match():
    from src.asr.hotwords import HotwordCorrector

    c = HotwordCorrector(["手势识别", "答辩委员会"])
    assert c.correct("今天介绍守势识别系统") == "今天介绍手势识别系统"
    assert "答辩委员会" in c.correct("感谢答辩委元会的聆听")
    assert c.correct("完全无关的一句话") == "完全无关的一句话"


def test_hotword_corrector_empty_and_long_first():
    from src.asr.hotwords import HotwordCorrector

    assert HotwordCorrector([]).correct("任意文本") == "任意文本"
    # 长词优先：先匹配长词，不被短词抢先
    c = HotwordCorrector(["识别", "手势识别系统"])
    assert c.correct("这是手势识別系统") == "这是手势识别系统"


def test_parse_hotword_and_script(tmp_path):
    from src.asr.hotwords import parse_hotword_file, parse_script_file

    words = tmp_path / "words.txt"
    words.write_text("手势识别\n\n激光笔\n超长词条" + "长" * 30 + "\n", encoding="utf-8")
    assert parse_hotword_file(words) == ["手势识别", "激光笔"]  # 空行与超长词条过滤
    script = tmp_path / "script.txt"
    script.write_text("各位老师好，今天介绍基于手势识别的演示系统。它支持实时字幕！",
                      encoding="utf-8")
    terms = parse_script_file(script)
    assert "各位老师好" in terms and "它支持实时字幕" in terms


def test_offline_engine_default_sensevoice():
    from src.asr.offline import OfflineEngine

    engine = OfflineEngine(CFG)
    assert engine.model_type == "sensevoice"
    assert "sensevoice" in str(engine.model_dir)


# ---------- 字幕浮层 ----------

@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_subtitle_overlay(qapp):
    from src.overlay import SubtitleOverlay

    sub = SubtitleOverlay(CFG)
    sub.show()
    sub.add_line("第一句话")
    sub.add_line("第二句话")
    sub.add_line("第三句话")
    assert [zh for zh, _ in sub._entries] == ["第二句话", "第三句话"]  # 只留最近两句
    sub.add_line("x" * 100)
    assert len(sub._entries[-1][0]) <= 21  # max_chars 截断（20 + 省略号）
    sub.repaint()
    sub.clear()
    assert sub._entries == []
    sub.close()


# ---------- 手势指令 ----------

def test_subtitle_toggle_command():
    from test_e2e import FULL_CFG

    cfg = copy.deepcopy(FULL_CFG)
    cfg["custom_gestures"] = {"mapping": {"s": "subtitle_toggle"}}
    from src.pipeline import Pipeline
    from src.decision import GestureEvent, GestureType, Mode
    import time

    pipeline = Pipeline(cfg, with_controls=True, screen_size=(1920, 1080))
    pipeline.engine.mode = Mode.ARMED
    sub_ui = MagicMock()
    controls = {"ppt": MagicMock(is_running=lambda: True), "keyboard": MagicMock(),
                "subtitle_ui": sub_ui}
    event = GestureEvent(type=GestureType.CUSTOM_GESTURE, confidence=0.9,
                         timestamp=time.time(), data={"name": "s"})
    assert pipeline.engine.feed(event, controls) is True
    sub_ui.assert_called_once_with("toggle", None)


def test_command_choices_include_subtitle():
    from src.gui.custom_gesture_page import COMMAND_CHOICES
    from src.pipeline import Pipeline

    assert {c for c, _ in COMMAND_CHOICES} == set(Pipeline._CUSTOM_COMMANDS)


# ---------- GUI 页面 ----------

def test_asr_page_constructs(qapp, tmp_path, monkeypatch):
    import src.gui.asr_page as ap

    monkeypatch.setattr(ap, "CONFIG_PATH", tmp_path / "config.json")  # 不写真实配置
    from src.asr.manager import ASRManager
    from src.gui.asr_page import ASRPage

    page = ASRPage(CFG, ASRManager(CFG))
    page.show()
    assert page.enable_switch.isChecked() is True
    assert page.offline_card.isVisible()
    page.mode_combo.setCurrentIndex(2)  # 切在线（0=离线 1=流式 2=在线）
    assert page.online_card.isVisible() and not page.offline_card.isVisible()
    saved = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert saved["asr"]["mode"] == "online"  # 改动持久化到配置
    page.close()


def test_asr_page_mode_combo_short_text(qapp, tmp_path, monkeypatch):
    """2026-09-17 用户要求：窄卡内模式下拉框按钮只显示短名（离线/流式/在线识别），
    下拉项仍保留完整说明文案；页面标题去「（实时字幕）」、热词卡去「（识别后矫正）」。"""
    import src.gui.asr_page as ap

    monkeypatch.setattr(ap, "CONFIG_PATH", tmp_path / "config.json")
    from qfluentwidgets import StrongBodyLabel, TitleLabel
    from src.asr.manager import ASRManager
    from src.gui.asr_page import ASRPage

    page = ASRPage(CFG, ASRManager(CFG))
    # 下拉项完整文案不变
    assert page.mode_combo.itemText(0) == "离线识别（SenseVoice，整句出字）"
    assert page.mode_combo.itemText(1) == "流式识别（离线 Zipformer，边说边出字）"
    assert page.mode_combo.itemText(2) == "在线识别（阿里百炼 API，可翻译）"
    # 按钮只显示短名，且随切换更新
    for index, short in ((0, "离线识别"), (1, "流式识别"), (2, "在线识别")):
        page.mode_combo.setCurrentIndex(index)
        assert page.mode_combo.text() == short
    titles = [l.text() for l in page.findChildren(TitleLabel)]
    assert "语音识别" in titles and "语音识别（实时字幕）" not in titles
    cards = [l.text() for l in page.findChildren(StrongBodyLabel)]
    assert "热词增强" in cards and "热词增强（识别后矫正）" not in cards
    page.close()


# ---------- 噪音自适应 VAD（2026-09-13 用户批准） ----------

def _frames(energy, n, sr=16000):
    amp = energy  # RMS≈amp 的常量帧（直流不影响 RMS 计算）
    return [np.full(int(sr * 0.03), amp, dtype=np.float32) for _ in range(n)]


def test_noise_adaptive_quiet_env_threshold_unchanged():
    """安静环境（底噪≈0）：阈值保持配置值，行为与原实现一致。"""
    seg = MicSegmenter(energy_threshold=0.01, noise_adaptive=True)
    for f in _frames(0.001, 50):  # 安静环境底噪
        seg.feed(f)
    assert seg.current_threshold == 0.01


def test_noise_adaptive_noisy_env_raises_threshold():
    """嘈杂环境（底噪 0.008 > 默认阈值附近）：阈值自动抬高到 margin×底噪，
    不再把环境噪音当说话切段；关闭自适应则阈值不变。"""
    seg = MicSegmenter(energy_threshold=0.005, noise_adaptive=True, noise_margin=3.0)
    for f in _frames(0.01, 100):  # 底噪 0.01（高于配置阈值 0.005）
        seg.feed(f)
    assert seg.current_threshold >= 0.029  # 3×0.01 附近
    seg_off = MicSegmenter(energy_threshold=0.005, noise_adaptive=False)
    for f in _frames(0.01, 100):
        seg_off.feed(f)
    assert seg_off.current_threshold == 0.005


def test_noise_adaptive_speech_still_segmented():
    """噪音环境下语音仍可正常分段（阈值自适应不干扰识别与延迟）。"""
    seg = MicSegmenter(energy_threshold=0.005, silence_ms=150,
                       noise_adaptive=True, noise_margin=3.0, min_segment_s=0.5)
    for f in _frames(0.01, 30):  # 底噪（恒定能量 = 噪音特征）
        assert seg.feed(f) is None  # 启动期 ~3 帧泄漏被最短段长过滤（生产语义）
    out = None
    for i in range(20):  # 说话（能量起伏 = 语音特征，且远超底噪）
        r = seg.feed(_frames(0.15 if i % 2 else 0.04, 1)[0])
        out = r if r is not None else out
    for f in _frames(0.005, 10):  # 静默 300ms > silence_ms=150 → 切段
        r = seg.feed(f)
        out = r if r is not None else out
    assert out is not None and len(out) > 0


def test_noise_floor_recovers_after_calibration_burst():
    """启动瞬间有人说话（底噪被抬高）：地板快速回落，阈值很快恢复正常。"""
    seg = MicSegmenter(energy_threshold=0.01, noise_adaptive=True, noise_margin=3.0)
    for f in _frames(0.1, 5):  # 启动期说话（首帧地板被抬高）
        seg.feed(f)
    for f in _frames(0.001, 60):  # 之后安静 2 秒
        seg.feed(f)
    assert seg.current_threshold < 0.02  # 阈值回落接近配置值


# ---------- 实时翻译（A4 用户批准） ----------

def test_translate_prompt_used_when_enabled():
    """翻译开启：在线引擎改用「转写+翻译双行」提示词；关闭时保持原提示词。"""
    from src.asr.online import DashScopeEngine, TRANSLATE_PROMPT

    cfg = {"asr": {"translate": True, "online": {"api_key": "k"}}}
    eng = DashScopeEngine(cfg)
    payload = eng.build_payload(b"wav")
    assert "翻译成英文" in payload.decode("utf-8")
    cfg2 = {"asr": {"translate": False, "online": {"api_key": "k"}}}
    eng2 = DashScopeEngine(cfg2)
    payload2 = eng2.build_payload(b"wav")
    assert "翻译成英文" not in payload2.decode("utf-8")


def test_correct_zh_line_only():
    """热词矫正只作用于中文行（翻译模式下英文行不参与矫正）。"""
    from src.asr.manager import _correct_zh_line
    from src.asr.hotwords import HotwordCorrector

    corrector = HotwordCorrector(["手势识别"])
    out = _correct_zh_line("守势识别很重要\nGesture recognition matters", corrector)
    assert out.split("\n")[0] == "手势识别很重要"
    assert out.split("\n")[1] == "Gesture recognition matters"  # 英文行原样


def test_subtitle_overlay_translation_layout(qapp):
    """A4 字幕条：中文+英文成对显示、高度自适应、UI 重做后可绘制。"""
    from src.overlay import SubtitleOverlay

    overlay = SubtitleOverlay({"asr": {"subtitle": {"font_size": 24, "max_chars": 60}}})
    assert overlay.height() == 64  # 无翻译时矮
    overlay.add_line("第一句话")
    overlay.add_line("第二句话\nThe second sentence")
    assert overlay._entries[-1] == ("第二句话", "The second sentence")
    assert overlay.height() > 64  # 按实际字体和行数加高
    overlay.show()
    overlay.grab()  # 强制绘制无崩溃
    overlay.clear()
    assert overlay.height() == 64
    overlay.close()


def test_subtitle_overlay_draggable(qapp):
    """实测反馈回归：字幕条鼠标可拖动；拖动后高度自适应不得把位置重置回底部。"""
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtCore import Qt
    from src.overlay import SubtitleOverlay

    overlay = SubtitleOverlay({"asr": {"subtitle": {"font_size": 24, "max_chars": 60}}})
    overlay.show()
    assert not overlay.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    start = overlay.pos()
    press = QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPoint(10, 10),
                        overlay.mapToGlobal(QPoint(10, 10)), Qt.MouseButton.LeftButton,
                        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    overlay.mousePressEvent(press)
    move = QMouseEvent(QMouseEvent.Type.MouseMove, QPoint(110, -90),
                       overlay.mapToGlobal(QPoint(110, -90)), Qt.MouseButton.LeftButton,
                       Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    overlay.mouseMoveEvent(move)
    overlay.mouseReleaseEvent(move)
    assert overlay.pos() != start  # 拖动生效
    assert overlay._user_moved
    pos_after_drag = overlay.pos()
    overlay.add_line("中文行\nEnglish line")  # 高度 64→100 时锚定底边，不跳回默认位
    assert overlay.height() > 64
    assert overlay.x() == pos_after_drag.x()
    assert overlay.y() + overlay.height() == pos_after_drag.y() + 64
    overlay.close()


def test_subtitle_overlay_english_line_hardened(qapp):
    """英文行加固：多行/多余空白压成一行，超长截断防溢出。"""
    from src.overlay import SubtitleOverlay

    overlay = SubtitleOverlay({"asr": {"subtitle": {"font_size": 24, "max_chars": 60}}})
    overlay.add_line("中文\nEnglish  line\nwith extra row")
    zh, en = overlay._entries[-1]
    assert en == "English line with extra row"
    overlay.add_line("中文\n" + "e" * 200)
    assert len(overlay._entries[-1][1]) <= 121  # max_chars*2 + 省略号
    overlay.close()


# ---------- 输入电平表（实测反馈：识别无反应时无法定位麦克风/阈值/模型） ----------

def test_segmenter_level_callback_throttled():
    """分段器每 2 帧回调一次电平（~15Hz），携带当前生效阈值。"""
    seg = MicSegmenter(energy_threshold=0.05, silence_ms=90, frame_ms=30)
    seen = []
    seg.on_level = lambda rms, thr: seen.append((rms, thr))
    for _ in range(6):
        seg.feed(_loud(480))
    assert len(seen) == 3
    rms, thr = seen[-1]
    assert rms > 0 and thr == seg.current_threshold


def test_segmenter_no_level_callback_by_default():
    """未接电平回调时分段行为零变化（默认 None 不影响原逻辑）。"""
    seg = MicSegmenter(energy_threshold=0.05, silence_ms=90, frame_ms=30)
    assert seg.on_level is None
    for _ in range(20):
        assert seg.feed(_loud(480)) is None


def test_level_meter(qapp):
    """电平表：动画趋近目标、峰值驻留、归零后自动停表、sqrt 归一化映射。"""
    from src.gui.asr_page import LevelMeter

    m = LevelMeter()
    m.set_level(0.05, 0.01)
    assert m._target == 0.05 and m._threshold == 0.01
    m.show()
    for _ in range(40):  # 快攻趋近
        m._tick()
    assert abs(m._level - 0.05) < 0.01
    assert m._peak >= m._level - 1e-6
    m.grab()  # 有电平时绘制不崩溃
    m.reset()
    for _ in range(300):  # 慢放归零 → 自动停表
        m._tick()
    assert m._level == 0.0 and not m._timer.isActive()
    m.grab()  # 归零后绘制不崩溃
    assert LevelMeter._norm(0) == 0 and LevelMeter._norm(LevelMeter.RANGE) == 1.0
    assert 0.3 < LevelMeter._norm(0.01) < 0.4
    m.close()


def test_asr_page_has_level_meter(qapp, tmp_path, monkeypatch):
    """语音识别页含电平表且接入 manager 电平信号。"""
    import src.gui.asr_page as ap

    monkeypatch.setattr(ap, "CONFIG_PATH", tmp_path / "config.json")
    from src.asr.manager import ASRManager
    from src.gui.asr_page import ASRPage, LevelMeter

    manager = ASRManager(CFG)
    page = ASRPage(CFG, manager)
    assert isinstance(page.level_meter, LevelMeter)
    manager.level_changed.emit(0.04, 0.02)  # 信号 → 电平表目标值
    assert page.level_meter._target == 0.04 and page.level_meter._threshold == 0.02
    page._on_status("识别中（离线 SenseVoice）")  # 未启动时无设备名，不崩溃
    page._on_status("已停止")  # 停止 → 电平表归零动画启动
    assert page.level_meter._target == 0.0
    page.close()


def test_asr_page_top_row_golden_ratio(qapp, tmp_path, monkeypatch):
    """用户亲定（2026-09-15 v2）：顶行 左四模块区 : 右字幕预览 = 1 : 1.618；
    四模块 2+1+1 排布：启用/模式横排一行，模型槽与电平卡各自整宽在下。"""
    import src.gui.asr_page as ap

    monkeypatch.setattr(ap, "CONFIG_PATH", tmp_path / "config.json")
    from PySide6.QtCore import QEventLoop, QTimer
    from qfluentwidgets import BodyLabel
    from src.asr.manager import ASRManager
    from src.gui.asr_page import ASRPage

    page = ASRPage(CFG, ASRManager(CFG))
    page.show()
    page.resize(1100, 700)
    loop = QEventLoop()
    QTimer.singleShot(400, loop.quit)
    loop.exec()
    left_unit = page.model_slot.parentWidget()
    # 第一行：启用卡在左、模式卡在右，同一水平线
    ey = page.enable_card.mapTo(page, page.enable_card.rect().topLeft()).y()
    my = page.mode_card.mapTo(page, page.mode_card.rect().topLeft()).y()
    ex = page.enable_card.mapTo(page, page.enable_card.rect().topLeft()).x()
    mx = page.mode_card.mapTo(page, page.mode_card.rect().topLeft()).x()
    assert ey == my and ex < mx
    # 模型槽与电平卡与左区同宽（整宽），且在第二/三行
    for card in (page.model_slot, page.level_card):
        assert card.width() == left_unit.width()
    sy = page.model_slot.mapTo(page, page.model_slot.rect().topLeft()).y()
    ly = page.level_card.mapTo(page, page.level_card.rect().topLeft()).y()
    assert ey < sy < ly
    # 黄金比例（与自定义手势页同断言口径）
    ratio = page.preview_card.width() / left_unit.width()
    assert abs(ratio - 1.618) < 0.05
    # 启用卡内容：开关 + 开始识别 + 状态
    assert page.recog_btn.text() == "开始识别"
    assert page.status_label.text()
    # 电平卡：电平表 + 三行小字注释
    texts = [l.text() for l in page.level_card.findChildren(BodyLabel)]
    assert any("未采集" in t for t in texts) and any("琥珀色" in t for t in texts) \
        and any("energy_threshold" in t for t in texts)
    page.close()


def test_overlay_paint_events_direct_call_fresh(qapp):
    """实测 bug 回归（2026-09-14 用户首启报错）：paintEvent 必须能直接调用。

    背景：PySide6 经事件循环调用 paintEvent 时会吞掉 Python 异常（只打印
    "Error calling Python override"），此前的 show()/repaint() 测试因此漏掉了
    SubtitleOverlay._partial 未初始化的 AttributeError。直接调用 paintEvent(None)
    异常会正常抛出——这里对所有自绘浮层做同守护，覆盖"属性未初始化"这类 bug。
    """
    from src.overlay import (
        CountdownOverlay, LaserOverlay, NotesOverlay, PointerRingOverlay,
        SpotlightOverlay, SubtitleOverlay,
    )
    from src.gui.asr_page import LevelMeter
    from src.gui.status_overlay import ThumbLabel

    widgets = [
        SubtitleOverlay(CFG),                      # 字幕条（本次 bug 主体）
        NotesOverlay(),                            # 备注大字卡
        CountdownOverlay(5),                       # 倒计时
        SpotlightOverlay(radius=150),              # 聚光灯
        PointerRingOverlay(radius=60),             # 指针聚光环
        LaserOverlay({"laser": {"dot_radius": 8, "trail_ms": 1000}}),  # 自绘激光
        LevelMeter(),                              # 输入电平表
        ThumbLabel(""),                            # 悬浮窗缩略图（站位引导）
    ]
    for w in widgets:
        w.paintEvent(None)  # 全新状态（无任何数据）直接绘制，异常即失败
        w.close()
        w.deleteLater()
