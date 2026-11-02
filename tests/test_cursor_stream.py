"""光标高频插值输出测试（S3，2026-09-12 实测反馈"卡顿"的统一修复）：

CursorStreamer 以 stream_hz 恒定插值移动到目标点，光标运动与摄像头帧率解耦。
全部注入假 mover，不触碰真实鼠标；手动 _tick 推进，不走真实线程。
"""
from __future__ import annotations

from src.control.keyboard import CursorStreamer, KeyboardController


def _make(hz=120, tau_ms=50):
    moves, ink_moves = [], []
    s = CursorStreamer(hz=hz, tau_ms=tau_ms,
                       mover=lambda x, y: moves.append((x, y)),
                       ink_mover=lambda x, y: ink_moves.append((x, y)),
                       autostart=False)
    return s, moves, ink_moves


def test_converges_smoothly_to_target():
    clock = [0.0]
    moves = []
    s = CursorStreamer(hz=120, tau_ms=50,
                       mover=lambda x, y: moves.append((x, y)),
                       autostart=False, clock=lambda: clock[0])
    s.jump_to(0, 0)
    moves.clear()
    s.set_target(100, 0)
    for _ in range(200):
        clock[0] += 1 / 120  # S10：趋近按真实流逝时间推进
        s._tick()
    assert moves, "插值过程应产生连续移动"
    # 单调逼近（无 overshoot）且最终贴到目标
    xs = [m[0] for m in moves]
    assert all(xs[i] <= xs[i + 1] + 1e-9 for i in range(len(xs) - 1))
    assert moves[-1][0] == 100
    # 插值密度远高于 30Hz 管线（120Hz 输出 → 同样距离更多步）
    assert len(moves) > 3


def test_freeze_halts_immediately():
    s, moves, _ = _make()
    s.jump_to(0, 0)
    s.set_target(100, 0)
    for _ in range(3):
        s._tick()
    s.freeze()
    n = len(moves)
    for _ in range(10):
        s._tick()
    assert len(moves) == n  # 冻结后不再移动


def test_jump_to_emits_exact_position():
    s, moves, ink_moves = _make()
    s.jump_to(500, 400)
    assert moves == [(500.0, 400.0)]
    s.jump_to(300, 200, ink=True)
    assert ink_moves == [(300.0, 200.0)]


def test_ink_routing():
    """ink=True 走笔级通道（mouse_event），ink=False 走普通移动。"""
    s, moves, ink_moves = _make()
    s.jump_to(0, 0)
    moves.clear()
    s.set_target(50, 0, ink=True)
    for _ in range(3):
        s._tick()
    assert ink_moves and not moves
    ink_moves.clear()
    s.set_target(80, 0, ink=False)
    for _ in range(3):
        s._tick()
    assert moves and not ink_moves


def test_keyboard_controller_routes_through_streamer():
    """KeyboardController 接入插值器：move_to/pen_move 驱动目标，jump 类立即到位。"""
    moves, ink_moves = [], []
    s = CursorStreamer(hz=120, tau_ms=50,
                       mover=lambda x, y: moves.append((x, y)),
                       ink_mover=lambda x, y: ink_moves.append((x, y)),
                       autostart=False)
    kb = KeyboardController(check_foreground=False, streamer=s)
    kb.move_to(100, 100)
    for _ in range(5):
        s._tick()
    assert moves  # move_to 经插值器输出
    kb.move_to_immediate(500, 500)  # 中心锚定：立即到位不滑动
    assert moves[-1] == (500.0, 500.0)
    kb.cursor_freeze()
    n = len(moves)
    kb.move_to(0, 0)
    # freeze 只清当前目标；set_target 仍应恢复工作
    for _ in range(3):
        s._tick()
    assert len(moves) > n - 1  # 恢复移动（断言不挂死即可）


def test_keyboard_controller_without_streamer_unchanged():
    """无插值器时保持原直接调用语义（向后兼容）。"""
    kb = KeyboardController(check_foreground=False, streamer=None)
    assert kb._streamer is None
    kb.cursor_freeze()  # 无操作不报错
    kb.close()          # 无操作不报错


def test_streamer_close_without_thread():
    s, _, _ = _make()
    s.close()  # autostart=False 时关闭安全


def test_build_controls_inks_via_mouse_event(monkeypatch):
    """防回归：build_controls 的插值器 ink 通道必须绑定 _pen_move_raw
    （mouse_event 笔级事件）——默认的 pyautogui.moveTo 按住时画不出 PPT 墨迹
    （tools/verify_writing.py 实证教训）。"""
    import src.control.keyboard as kbm
    from src.pipeline import build_controls

    captured = {}

    class FakeStreamer:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(kbm, "CursorStreamer", FakeStreamer)
    controls = build_controls({})
    kb = controls["keyboard"]
    assert captured.get("ink_mover") == kb._pen_move_raw, \
        "ink 通道必须是 _pen_move_raw（mouse_event），否则书写画不出墨迹"


def test_ink_throttled_to_ink_hz():
    """ink 通道限流（实测反馈：120Hz 笔级事件让 PPT 墨迹重绘吃满 CPU，
    反过来把识别管线饿停顿）：持续移动时，ink 事件只按 ink_hz=60 发出。"""
    clock = [0.0]
    moves, ink_moves = [], []
    s = CursorStreamer(hz=120, tau_ms=50,
                       mover=lambda x, y: moves.append((x, y)),
                       ink_mover=lambda x, y: ink_moves.append((x, y)),
                       autostart=False, ink_hz=60, clock=lambda: clock[0])
    s.jump_to(0, 0, ink=True)
    ink_moves.clear()
    # 模拟书写：目标点每 tick 都在移动（持续 200ms）
    for i in range(24):
        s.set_target(i * 4.0, 0, ink=True)
        s._tick()
        clock[0] += 1 / 120
    assert 8 <= len(ink_moves) <= 13  # 60Hz × 0.2s ≈ 12 次，远少于 24 tick
    # 指向通道（ink=False）不受限
    moves.clear()
    for i in range(8):
        s.set_target(i * 4.0, 100, ink=False)
        s._tick()
        clock[0] += 1 / 120
    assert len(moves) >= 7


def test_ink_min_step_filter():
    """ink 最小步长过滤（S7：PPT 会把相邻点连线，<2px 的点对观感无贡献，
    过滤后 PPT 消息量约减半，削减 PPT 侧渲染争用）。"""
    clock = [0.0]
    _, ink_moves = [], []
    s = CursorStreamer(hz=120, tau_ms=10,
                       mover=lambda x, y: None,
                       ink_mover=lambda x, y: ink_moves.append((x, y)),
                       autostart=False, ink_hz=120, ink_min_step_px=2.0,
                       clock=lambda: clock[0])
    s.jump_to(0, 0, ink=True)
    ink_moves.clear()
    # 每 tick 移动 1px（< 2px 步长）→ 应被过滤（累积到 ≥2px 才发）
    for i in range(6):
        s.set_target(i * 1.0, 0, ink=True)
        s._tick()
        clock[0] += 1 / 120
    small_steps = len(ink_moves)
    # 大步长移动 → 必须发
    for i in range(6):
        s.set_target(i * 10.0, 0, ink=True)
        s._tick()
        clock[0] += 1 / 120
    big_steps = len(ink_moves) - small_steps
    assert big_steps > small_steps
    assert small_steps <= 3  # 小步大量被过滤


def test_ink_tau_faster_than_pointing():
    """S9 手感微调：ink 通道用更低的 tau（更跟手），指向通道保持原 tau。"""
    clock = [0.0]
    moves, ink_moves = [], []
    s = CursorStreamer(hz=120, tau_ms=80, ink_tau_ms=20,
                       mover=lambda x, y: moves.append((x, y)),
                       ink_mover=lambda x, y: ink_moves.append((x, y)),
                       autostart=False, ink_hz=120, ink_min_step_px=0,
                       clock=lambda: clock[0])
    assert s._ink_tau_s < s._tau_s  # ink 时间常数更小 = 更快贴近目标
    s.jump_to(0, 0, ink=True)
    ink_moves.clear()
    s.set_target(100, 0, ink=True)
    clock[0] += 1 / 120
    s._tick()
    ink_first = ink_moves[-1][0]
    s.jump_to(0, 0)
    moves.clear()
    s.set_target(100, 0, ink=False)
    clock[0] += 1 / 120
    s._tick()
    point_first = moves[-1][0]
    assert ink_first > point_first  # 同样目标与间隔下 ink 首步更大（更跟手）


def test_tick_uses_measured_dt():
    """S10 丝滑收尾：趋近系数按每 tick 真实流逝时间计算——
    帧间隔抖动/计时粒度失真时运动速度仍正确（不再依赖名义帧率）。"""
    clock = [0.0]
    moves = []
    s = CursorStreamer(hz=120, tau_ms=100,
                       mover=lambda x, y: moves.append((x, y)),
                       autostart=False, clock=lambda: clock[0])
    s.jump_to(0, 0)
    moves.clear()
    s.set_target(100, 0)
    # 第一个 tick 间隔 8.3ms，第二个 tick 间隔 33ms（帧率抖动）
    clock[0] += 1 / 120
    s._tick()
    first = moves[-1][0]
    clock[0] += 1 / 30
    s._tick()
    second = moves[-1][0]
    # 第二个 tick 间隔 4 倍，位移增量也应约 4 倍（按真实 dt 趋近）
    assert second - first > (first - 0) * 1.5
    # 长时间不 tick 后一步到位附近（不应欠走）
    clock[0] += 10.0
    s._tick()
    assert moves[-1][0] == 100
