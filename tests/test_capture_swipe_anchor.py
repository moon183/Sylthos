"""摄像头自愈与挥手起点回溯测试。"""
from __future__ import annotations

import numpy as np
from test_e2e import FULL_CFG
from test_gestures import make_hand

from src.capture import CameraCapture
from src.decision import GestureType
from src.gestures.swipe import SwipeDetector

FPS = 30
DT = 1.0 / FPS


def _make_capture_no_hw():
    """不触碰硬件构造 CameraCapture（只测健康计数逻辑）。"""
    cap = CameraCapture.__new__(CameraCapture)
    cap._black_threshold = 3.0
    cap._black_max = 5
    cap._black_count = 0
    cap.unhealthy = False
    cap._cap = _FakeCap()
    return cap


class _FakeCap:
    def __init__(self):
        self.reopened = False

    def release(self):
        self.reopened = True

    def isOpened(self):
        return True

    def set(self, *a):
        pass


def test_black_frames_trigger_reopen():
    cap = _make_capture_no_hw()
    black = np.zeros((64, 64, 3), dtype=np.uint8)
    for _ in range(4):
        cap._update_health(black)
    assert not cap._cap.reopened  # 未达阈值不重开
    cap._update_health(black)     # 第 5 帧达阈值
    assert cap._cap.reopened


def test_normal_frame_resets_black_count():
    cap = _make_capture_no_hw()
    bright = np.full((64, 64, 3), 200, dtype=np.uint8)
    black = np.zeros((64, 64, 3), dtype=np.uint8)
    for _ in range(4):
        cap._update_health(black)
    cap._update_health(bright)    # 正常帧清零计数
    for _ in range(4):
        cap._update_health(black)
    assert not cap._cap.reopened  # 重新计数未达阈值


def test_swipe_onset_anchor_includes_rampup():
    """起点回溯机制：onset 时动作起点锚定到前 3 帧的最早位置（而非 onset 前一帧）。"""
    det = SwipeDetector(FULL_CFG)
    t = 0.0
    # 5 帧静止在 x=0.6（hs 2.4）
    for _ in range(5):
        det.feed(make_hand((0.6, 0.5), scale=0.25, t=t))
        t += DT
    # 一帧快速挥动触发 onset
    det.feed(make_hand((0.66, 0.5), scale=0.25, t=t))
    assert det._state.name == "TRACKING"
    anchor_hs = det._stroke_start[1]
    prev_hs = 2.4  # onset 前一帧的 x（0.6/0.25）
    # 锚点应比"前一帧"更靠左（回溯到了更早的帧）
    assert anchor_hs <= prev_hs + 1e-6
    # 且锚点来自回看缓冲（等于静止位置 0.6/0.25 = 2.4）
    assert abs(anchor_hs - 2.4) < 0.2
