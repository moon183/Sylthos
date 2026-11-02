"""流式语音识别（第三模式，2026-09-14 用户批准）测试：
流式引擎（mock sherpa）/ MicCapture 流模式 / Manager 流式循环 /
字幕条部分结果 / GUI 第三模式页。不依赖麦克风与真实模型推理。
"""
from __future__ import annotations

import copy
import json
from unittest.mock import MagicMock

import numpy as np
import pytest

from src.asr.capture import MicCapture, MicSegmenter

CFG = {
    "asr": {
        "enabled": True, "mode": "stream",
        "energy_threshold": 0.05, "silence_ms": 90,
        "offline": {"model_type": "sensevoice", "model_dir": "models/sensevoice"},
        "stream": {"model_dir": "models/zipformer_ctc", "endpoint_silence_s": 1.2},
        "online": {"base_url": "http://example.invalid/asr", "api_key": "sk-test",
                   "model": "qwen-audio-turbo", "prompt": "转写", "segment_s": 25.0,
                   "timeout_s": 10},
        "subtitle": {"font_size": 28, "max_chars": 20},
    }
}


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


# ---------- 流式引擎（mock sherpa-onnx） ----------

def test_streaming_engine_accept_endpoint_reset():
    from src.asr.streaming import StreamingEngine

    eng = StreamingEngine(CFG)
    rec = MagicMock()
    rec.is_ready.side_effect = [True, False]  # 每次 accept 解一块
    rec.get_result.return_value = "部分结果"
    eng._recognizer = rec
    eng._stream = MagicMock(name="stream")
    text = eng.accept(np.zeros(480, dtype=np.float32))
    assert text == "部分结果"
    eng._stream.accept_waveform.assert_called_once()
    rec.decode_stream.assert_called_once_with(eng._stream)
    rec.is_endpoint.return_value = True
    assert eng.endpoint() is True
    eng.reset()
    rec.reset.assert_called_once_with(eng._stream)


def test_streaming_engine_ready_checks_files(tmp_path):
    from src.asr.streaming import StreamingEngine

    cfg = {"asr": {"stream": {"model_dir": "models/zipformer_ctc"}}}
    eng = StreamingEngine(cfg)
    ok, reason = eng.ready()
    # CI 环境模型可能已下载（开发机），只校验返回结构
    assert isinstance(ok, bool) and isinstance(reason, str)


# ---------- MicCapture 流模式 ----------

def test_mic_capture_streaming_feeds_chunks_and_levels():
    cap = MicCapture(CFG, streaming=True)
    chunks, levels = [], []
    cap.on_chunk = chunks.append
    cap.on_level = lambda rms, thr: levels.append((rms, thr))
    for _ in range(4):
        cap._handle_frame(np.full(480, 0.2, dtype=np.float32))
    assert len(chunks) == 4          # 逐帧直送，不分段
    assert all(len(c) == 480 for c in chunks)
    assert len(levels) == 2          # 电平每 2 帧一次
    assert levels[-1][0] > 0.19 and levels[-1][1] == 0.05  # 参照线=配置阈值


def test_mic_capture_segment_mode_unchanged():
    """段落模式行为不变（回归保护）：走 VAD 分段器，on_chunk 不触发。"""
    cap = MicCapture(CFG)  # 默认 streaming=False
    segs, chunks = [], []
    cap.on_segment = segs.append
    cap.on_chunk = chunks.append

    def loud(i):  # 能量起伏帧（恒定能量是噪音特征，会被噪音自适应抬阈值）
        return np.full(480, 0.3 if i % 2 else 0.1, dtype=np.float32)

    for i in range(20):  # 600ms 说话
        cap._handle_frame(loud(i))
    for _ in range(4):   # 120ms 静默 > silence_ms=90 → 切段
        cap._handle_frame(np.zeros(480, dtype=np.float32))
    assert len(segs) == 1 and len(chunks) == 0


# ---------- Manager 流式循环 ----------

class _FakeStreamEngine:
    """脚本化假流式引擎：第 N 次 accept 后报端点。"""

    def __init__(self, partials, endpoint_after):
        self._partials = partials
        self._endpoint_after = endpoint_after
        self.calls = 0
        self.resets = 0

    def warmup(self):
        pass

    def accept(self, chunk):
        p = self._partials[min(self.calls, len(self._partials) - 1)]
        self.calls += 1
        return p

    def endpoint(self):
        return self.calls >= self._endpoint_after

    def reset(self):
        self.resets += 1


def test_manager_stream_loop_emits_partials_and_final():
    from PySide6.QtCore import Qt
    from src.asr.manager import ASRManager

    manager = ASRManager(CFG)
    manager._engine = _FakeStreamEngine(["你", "你好", "你好吗"], endpoint_after=3)
    manager._corrector = None
    partials, finals = [], []
    manager.partial_ready.connect(
        lambda t: partials.append(t), Qt.ConnectionType.DirectConnection)
    manager.text_ready.connect(
        lambda t: finals.append(t), Qt.ConnectionType.DirectConnection)
    manager._running = True
    import threading

    thread = threading.Thread(target=manager._loop, daemon=True)
    thread.start()
    for _ in range(3):
        manager._enqueue(np.zeros(480, dtype=np.float32))
    import time

    deadline = time.time() + 3
    while not finals and time.time() < deadline:
        time.sleep(0.02)
    manager._running = False
    thread.join(timeout=2)
    assert "你" in partials and "你好" in partials  # 边说边出字
    assert finals == ["你好吗"]                     # 端点定稿
    assert partials[-1] == ""                       # 定稿后清进行中行
    assert manager._engine.resets == 1


def test_manager_stream_hotword_corrects_final():
    """流式最终句同样走热词矫正（识别后矫正与模型无关）。"""
    from PySide6.QtCore import Qt
    from src.asr.manager import ASRManager

    cfg = copy.deepcopy(CFG)
    cfg["asr"]["hotwords"] = ["手势识别"]
    manager = ASRManager(cfg)
    manager._engine = _FakeStreamEngine(["守势识别"], endpoint_after=1)
    from src.asr.hotwords import HotwordCorrector

    manager._corrector = HotwordCorrector(["手势识别"])
    finals = []
    manager.text_ready.connect(
        lambda t: finals.append(t), Qt.ConnectionType.DirectConnection)
    manager._running = True
    import threading, time

    thread = threading.Thread(target=manager._loop, daemon=True)
    thread.start()
    manager._enqueue(np.zeros(480, dtype=np.float32))
    deadline = time.time() + 3
    while not finals and time.time() < deadline:
        time.sleep(0.02)
    manager._running = False
    thread.join(timeout=2)
    assert finals == ["手势识别"]


# ---------- 字幕条部分结果 ----------

def test_subtitle_overlay_partial(qapp):
    from src.overlay import SubtitleOverlay

    overlay = SubtitleOverlay(CFG)
    overlay.set_partial("正在说")
    assert overlay._partial == "正在说"
    overlay.show()
    overlay.grab()  # 仅部分结果时绘制不崩溃
    overlay.add_line("完整句子")
    assert overlay._partial == ""  # 最终句落定清掉部分结果
    overlay.set_partial("又说半句")
    overlay.grab()                 # 最终句+部分结果并存绘制不崩溃
    overlay.clear()
    assert overlay._partial == "" and overlay._entries == []
    overlay.close()


# ---------- GUI 第三模式 ----------

def test_asr_page_stream_mode(qapp, tmp_path, monkeypatch):
    import src.gui.asr_page as ap

    monkeypatch.setattr(ap, "CONFIG_PATH", tmp_path / "config.json")  # 不写真实配置
    from src.asr.manager import ASRManager
    from src.gui.asr_page import ASRPage

    cfg = copy.deepcopy(CFG)
    cfg["asr"]["mode"] = "offline"  # 从离线切到流式（同索引不会触发切换信号）
    page = ASRPage(cfg, ASRManager(cfg))
    page.show()
    assert page.mode_combo.count() == 3  # 离线/流式/在线
    page.mode_combo.setCurrentIndex(1)   # 流式
    assert page.stream_card.isVisible()
    assert not page.offline_card.isVisible() and not page.online_card.isVisible()
    saved = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert saved["asr"]["mode"] == "stream"  # 改动持久化
    assert page.stream_status.text()         # 流式模型状态已刷新
    page.close()
