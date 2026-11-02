"""BPF（Body Pre Focusing）单元测试：裁剪数学、坐标还原、触发逻辑。

姿态/手部检测均用 mock，不依赖真实模型推理。
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np

from src.tracking import HandTracker, compute_crop_square, remap_to_frame

CFG = {"tracking": {"max_num_hands": 1, "model_complexity": 0,
                    "min_detection_confidence": 0.7, "min_tracking_confidence": 0.6,
                    "bpf": True, "bpf_trigger_misses": 3, "bpf_visibility": 0.5}}

FRAME_W, FRAME_H = 1280, 720


# ---------- 纯函数 ----------

def test_crop_centered():
    x0, y0, side = compute_crop_square(640, 360, 300, FRAME_W, FRAME_H)
    assert (x0, y0, side) == (490, 210, 300)


def test_crop_clamped_at_edges():
    x0, y0, side = compute_crop_square(10, 10, 300, FRAME_W, FRAME_H)
    assert (x0, y0, side) == (0, 0, 300)  # 越界平移回画面内
    x0, y0, side = compute_crop_square(1270, 710, 300, FRAME_W, FRAME_H)
    assert x0 + side <= FRAME_W and y0 + side <= FRAME_H


def test_crop_side_capped_by_frame():
    _, _, side = compute_crop_square(640, 360, 9999, FRAME_W, FRAME_H)
    assert side == FRAME_H


def test_remap_roundtrip():
    crop = (400, 200, 300)
    x, y = remap_to_frame(0.5, 0.5, crop, FRAME_W, FRAME_H)
    assert abs(x - (400 + 150) / FRAME_W) < 1e-9
    assert abs(y - (200 + 150) / FRAME_H) < 1e-9


# ---------- 触发逻辑（mock 模型）----------

def _no_hands_result():
    return SimpleNamespace(multi_hand_landmarks=None, multi_handedness=None)


def _one_hand_result():
    points = [SimpleNamespace(x=0.5, y=0.5, z=0.0)] * 21
    # 腕点与中指根拉开距离，避免退化检测被丢弃
    points[0] = SimpleNamespace(x=0.5, y=0.7, z=0.0)
    points[9] = SimpleNamespace(x=0.5, y=0.4, z=0.0)
    lm = SimpleNamespace(landmark=points)
    handedness = SimpleNamespace(classification=[SimpleNamespace(label="Right")])
    return SimpleNamespace(multi_hand_landmarks=[lm], multi_handedness=[handedness])


def _pose_result():
    lms = [SimpleNamespace(x=0.5, y=0.5, z=0.0, visibility=0.9)] * 33
    lms[11] = SimpleNamespace(x=0.4, y=0.3, z=0.0, visibility=0.9)  # 左肩
    lms[12] = SimpleNamespace(x=0.6, y=0.3, z=0.0, visibility=0.9)  # 右肩
    lms[15] = SimpleNamespace(x=0.3, y=0.5, z=0.0, visibility=0.9)  # 左腕
    lms[16] = SimpleNamespace(x=0.7, y=0.5, z=0.0, visibility=0.9)  # 右腕
    return SimpleNamespace(pose_landmarks=SimpleNamespace(landmark=lms))


def _tracker_with_mocks():
    tr = HandTracker.__new__(HandTracker)
    tr._bpf = True
    tr._bpf_trigger = 3
    tr._bpf_visibility = 0.5
    tr._track_misses_max = 3
    tr._acquire_every = 1  # 测试里每帧都允许姿态检测
    tr._backoff_after = 40  # 连续失手退避点（S6 新增配置键）
    tr._max_every = 16      # 无手退避后的检测间隔（S6 新增配置键）
    tr._pose_width = 256   # 姿态检测输入宽度（S5 新增配置键）
    tr._detect_width = 960  # 整帧直检降采样（S6 新增配置键）
    tr._face_gate = False   # 人脸门控默认关（A7 新增配置键，测试不启用）
    tr._face_check_every = 6
    tr._face_det = None
    tr._face_present = True
    tr._face_last_ts = 0.0
    tr._miss = 0
    tr._track_region = None
    tr._track_miss = 0
    tr._frame_count = 0
    tr._last_center = None
    tr._last_velocity = (0.0, 0.0)
    tr._crop_factor = 3.5
    tr._hands = MagicMock()
    tr._pose = MagicMock()
    return tr


def test_bpf_not_triggered_below_miss_threshold():
    tr = _tracker_with_mocks()
    tr._hands.process.return_value = _no_hands_result()
    frame = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)
    for _ in range(2):  # 失手 2 次 < 阈值 3
        assert tr.process_all(frame) == []
    tr._pose.process.assert_not_called()


def test_bpf_triggers_and_remaps():
    tr = _tracker_with_mocks()
    tr._pose.process.return_value = _pose_result()
    # 整帧检测不到，裁剪块里检测到
    tr._hands.process.side_effect = [  # 3 次整帧失手（第 3 次触发 ACQUIRE）+ 2 次手腕裁剪命中
        _no_hands_result(), _no_hands_result(), _no_hands_result(),
        _one_hand_result(), _one_hand_result(),
    ]
    frame = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)
    for _ in range(2):
        assert tr.process_all(frame) == []
    hands = tr.process_all(frame)  # 第 3 次失手触发 ACQUIRE
    assert len(hands) >= 1
    hf = hands[0]
    assert hf.source == "bpf"
    # 关键点应被还原到整帧坐标系（而非 0-1 的裁剪块坐标）
    wx, wy, _ = hf.landmarks[0]
    # 左腕裁剪中心约 (0.3*1280, 0.5*720)=(384,360)，块内腕点 (0.5,0.7) → 整帧应在左腕附近
    assert 0.2 < wx < 0.5 and 0.4 < wy < 0.8


def test_track_mode_keeps_lock_without_pose():
    """TRACK 模式：锁定后不再跑姿态模型，直接围绕手部小区域检测。"""
    tr = _tracker_with_mocks()
    tr._pose.process.return_value = _pose_result()
    tr._hands.process.side_effect = [
        _no_hands_result(), _no_hands_result(), _no_hands_result(),  # 3 次整帧失手
        _one_hand_result(), _one_hand_result(),  # ACQUIRE 两腕裁剪命中
    ] + [_one_hand_result()] * 20  # TRACK 阶段持续命中
    frame = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)
    tr.process_all(frame)
    tr.process_all(frame)
    hands = tr.process_all(frame)  # ACQUIRE 命中，进入 TRACK
    assert hands and tr._track_region is not None
    pose_calls = tr._pose.process.call_count
    for _ in range(5):  # 后续帧不再跑姿态模型
        assert tr.process_all(frame)
    assert tr._pose.process.call_count == pose_calls


def test_track_loss_returns_to_acquire():
    """TRACK 连续丢失后退出跟踪，重新走 ACQUIRE。"""
    tr = _tracker_with_mocks()
    tr._pose.process.return_value = _pose_result()
    tr._hands.process.side_effect = [
        _no_hands_result(), _no_hands_result(), _no_hands_result(),  # 3 次整帧失手
        _one_hand_result(), _one_hand_result(),  # ACQUIRE 命中
    ] + [_no_hands_result()] * 20               # 之后全丢
    frame = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)
    tr.process_all(frame)
    tr.process_all(frame)
    assert tr.process_all(frame)  # 进入 TRACK
    for _ in range(3):  # track_misses_max=3，连续丢失退出 TRACK
        tr.process_all(frame)
    assert tr._track_region is None


def test_direct_hit_skips_bpf():
    tr = _tracker_with_mocks()
    tr._hands.process.return_value = _one_hand_result()
    frame = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)
    hands = tr.process_all(frame)
    assert len(hands) == 1
    assert hands[0].source == "direct"
    tr._pose.process.assert_not_called()
    assert tr._miss == 0


def test_velocity_prediction_moves_crop_ahead():
    """速度外推：手持续右移时，TRACK 裁剪框中心应预测到手的移动方向前方。"""
    tr = _tracker_with_mocks()
    tr._crop_factor = 3.5
    centers = []

    def make_moving_hand(x_norm):
        points = [SimpleNamespace(x=x_norm, y=0.5, z=0.0)] * 21
        points[0] = SimpleNamespace(x=x_norm, y=0.6, z=0.0)
        points[9] = SimpleNamespace(x=x_norm, y=0.4, z=0.0)
        lm = SimpleNamespace(landmark=points)
        handedness = SimpleNamespace(classification=[SimpleNamespace(label="Right")])
        return SimpleNamespace(multi_hand_landmarks=[lm], multi_handedness=[handedness])

    # 直接驱动内部方法：两帧命中，掌心从 0.3 → 0.5（右移 0.2*1280=256px/帧）
    tr._update_track_region(
        tr._to_handframes(make_moving_hand(0.3))[0], (FRAME_H, FRAME_W, 3))
    tr._update_track_region(
        tr._to_handframes(make_moving_hand(0.5))[0], (FRAME_H, FRAME_W, 3))
    cx, cy, side = tr._track_region
    # 速度经 0.5 平滑：0.5*256 + 0.5*0 = 128 px/帧
    px = cx + tr._last_velocity[0]
    assert px > cx  # 预测方向与运动方向一致
    assert abs(tr._last_velocity[0] - 128) < 1  # 平滑后的速度估计正确


def test_detect_full_downscales_input():
    """S6 卡顿治理：整帧直检按 detect_width 降采样（MediaPipe 耗时随像素数线性）；
    关键点为归一化坐标，降采样不改变下游语义。0 = 原始行为。"""
    import numpy as np

    tr = _tracker_with_mocks()
    result = SimpleNamespace(multi_hand_landmarks=None, multi_handedness=None)
    tr._hands.process.return_value = result
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    tr._detect_full(frame)
    img = tr._hands.process.call_args.args[0]
    assert img.shape[1] == 960 and img.shape[0] == 540  # 720p → 960×540
    tr._detect_width = 0
    tr._detect_full(frame)
    img2 = tr._hands.process.call_args.args[0]
    assert img2.shape[1] == 1280  # 关闭降采样 = 原始分辨率


def test_acquire_backs_off_when_idle_long():
    """S6 卡顿治理：长时间画面无手时，BlazePose 定位从 acquire_every 降频到
    max_every——退避点前积极找手，退避点后低频待命（省 CPU、削静态尖峰）。"""
    import numpy as np

    tr = _tracker_with_mocks()
    tr._bpf_trigger = 3
    tr._acquire_every = 2
    tr._backoff_after = 6
    tr._max_every = 5
    tr._hands.process.return_value = SimpleNamespace(
        multi_hand_landmarks=None, multi_handedness=None)
    tr._pose.process.return_value = SimpleNamespace(pose_landmarks=None)
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    for _ in range(5):  # miss 0→5（≥trigger 后 every=2）
        tr.process_all(frame)
    early_calls = tr._pose.process.call_count
    assert early_calls >= 1  # 退避点前：每 2 帧跑一次
    tr._pose.process.reset_mock()
    for _ in range(10):  # miss 5→15（>backoff_after=6 → every=5）
        tr.process_all(frame)
    late_calls = tr._pose.process.call_count
    assert 1 <= late_calls <= 3  # 退避点后：每 5 帧才跑一次
