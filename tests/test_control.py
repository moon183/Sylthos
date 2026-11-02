"""控制层单元测试：COM 与键盘模拟均用 mock 隔离真实 PowerPoint/系统输入。"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.control.keyboard import KeyboardController
from src.control.ppt_com import PptComController


def _make_ppt_with_view(position=3, total=10):
    ppt = PptComController.__new__(PptComController)
    ppt._app = MagicMock()
    view = ppt._app.SlideShowWindows(1).View
    view.CurrentShowPosition = position
    ppt._app.ActivePresentation.Slides.Count = total
    ppt._app.SlideShowWindows.Count = 1
    return ppt, view


def test_com_next_slide():
    ppt, view = _make_ppt_with_view(position=3, total=10)
    assert ppt.next_slide() is True
    view.Next.assert_called_once()


def test_com_next_slide_at_last_page_blocked():
    ppt, view = _make_ppt_with_view(position=10, total=10)
    assert ppt.next_slide() is True  # 边界拦截视为"已处理"（不翻页也不走键盘兜底）
    view.Next.assert_not_called()


def test_com_prev_slide_at_first_page_blocked():
    ppt, view = _make_ppt_with_view(position=1, total=10)
    assert ppt.prev_slide() is True
    view.Previous.assert_not_called()


def test_com_no_slideshow_returns_false():
    ppt = PptComController.__new__(PptComController)
    ppt._app = MagicMock()
    ppt._app.SlideShowWindows.Count = 0
    assert ppt.next_slide() is False
    assert ppt.is_running() is False
    assert ppt.get_position() is None


def test_keyboard_blocked_when_foreground_not_ppt():
    with patch("src.control.keyboard.foreground_is_powerpoint", return_value=False), \
         patch("src.control.keyboard.pyautogui") as mock_gui:
        kb = KeyboardController(check_foreground=True)
        assert kb.next_slide() is False
        mock_gui.press.assert_not_called()


def test_keyboard_sends_when_foreground_is_ppt():
    with patch("src.control.keyboard.foreground_is_powerpoint", return_value=True), \
         patch("src.control.keyboard.pyautogui") as mock_gui:
        kb = KeyboardController(check_foreground=True)
        assert kb.next_slide() is True
        mock_gui.press.assert_called_once_with("space")


def test_keyboard_laser_shortcut():
    with patch("src.control.keyboard.foreground_is_powerpoint", return_value=True), \
         patch("src.control.keyboard.pyautogui") as mock_gui:
        kb = KeyboardController()
        assert kb.laser_on() is True
        mock_gui.hotkey.assert_called_once_with("ctrl", "l")


def test_zoom_scroll_wraps_ctrl():
    with patch("src.control.keyboard.foreground_is_powerpoint", return_value=True), \
         patch("src.control.keyboard.pyautogui") as mock_gui:
        kb = KeyboardController()
        assert kb.zoom_scroll(2) is True
        mock_gui.keyDown.assert_called_once_with("ctrl")
        mock_gui.scroll.assert_called_once_with(2)
        mock_gui.keyUp.assert_called_once_with("ctrl")


def test_ppt_poll_cache_roundtrip(monkeypatch):
    """COM 后台轮询缓存（S8，2026-09-13 帧耗时看门狗定位的真凶修复）：
    轮询线程刷新缓存，position_cached/is_running_cached 读缓存不阻塞。"""
    import time
    from unittest.mock import MagicMock

    import src.control.ppt_com as pcm

    fake_app = MagicMock()
    fake_app.SlideShowWindows.Count = 1
    fake_app.SlideShowWindows(1).View.CurrentShowPosition = 3
    fake_app.ActivePresentation.Slides.Count = 9
    monkeypatch.setattr(pcm.win32com.client, "Dispatch", lambda name: fake_app)

    ctrl = pcm.PptComController()
    assert ctrl.position_cached() is None  # 轮询前无缓存
    ctrl.start_polling(interval_ms=50)
    try:
        deadline = time.time() + 2.0
        while ctrl.position_cached() is None and time.time() < deadline:
            time.sleep(0.02)
        assert ctrl.position_cached() == (3, 9)
        assert ctrl.is_running_cached() is True
    finally:
        ctrl.stop_polling()
    assert ctrl._poll_thread is None  # 线程已正确回收


def test_ppt_poll_notes_cached(monkeypatch):
    """A3 备注提词：轮询线程顺带读当前页备注（缓存读取不阻塞）。"""
    import time
    from unittest.mock import MagicMock

    import src.control.ppt_com as pcm

    fake_app = MagicMock()
    fake_app.SlideShowWindows.Count = 1
    fake_app.SlideShowWindows(1).View.CurrentShowPosition = 2
    fake_app.ActivePresentation.Slides.Count = 9
    (fake_app.ActivePresentation.Slides(2).NotesPage.Shapes
     .Placeholders(2).TextFrame.TextRange.Text) = "  记得讲 handScale 归一化  "
    monkeypatch.setattr(pcm.win32com.client, "Dispatch", lambda name: fake_app)

    ctrl = pcm.PptComController()
    ctrl.start_polling(interval_ms=50)
    try:
        deadline = time.time() + 2.0
        while not ctrl.notes_cached() and time.time() < deadline:
            time.sleep(0.02)
        assert ctrl.notes_cached() == "记得讲 handScale 归一化"
    finally:
        ctrl.stop_polling()


# ---------- 一键演示（2026-09-14 用户要求） ----------

def test_launch_and_start_show_with_path(monkeypatch, tmp_path):
    """一键演示：打开指定文稿并开始放映。"""
    import src.control.ppt_com as pcm

    ppt = tmp_path / "demo.pptx"
    ppt.write_bytes(b"fake")
    fake_app = MagicMock()
    pres = fake_app.Presentations.Open.return_value
    pres.Name = "demo"
    monkeypatch.setattr(pcm.win32com.client, "Dispatch", lambda name: fake_app)
    ok, msg = pcm.launch_and_start_show(str(ppt))
    assert ok and "demo" in msg
    pres.SlideShowSettings.Run.assert_called_once()


def test_launch_and_start_show_fallback_active(monkeypatch):
    """不传路径时复用当前打开的演示文稿。"""
    import src.control.ppt_com as pcm

    fake_app = MagicMock()
    fake_app.ActivePresentation.Name = "已打开的文稿"
    monkeypatch.setattr(pcm.win32com.client, "Dispatch", lambda name: fake_app)
    ok, msg = pcm.launch_and_start_show(None)
    assert ok and "已打开的文稿" in msg
    fake_app.ActivePresentation.SlideShowSettings.Run.assert_called_once()


def test_launch_and_start_show_no_presentation(monkeypatch):
    """没有打开的文稿且未给路径：明确失败提示。"""
    from unittest.mock import PropertyMock

    import src.control.ppt_com as pcm

    fake_app = MagicMock()
    type(fake_app).ActivePresentation = PropertyMock(
        side_effect=Exception("无打开的文稿"))
    monkeypatch.setattr(pcm.win32com.client, "Dispatch", lambda name: fake_app)
    ok, msg = pcm.launch_and_start_show(None)
    assert not ok and "没有打开的演示文稿" in msg


def test_launch_and_start_show_missing_file(tmp_path, monkeypatch):
    import src.control.ppt_com as pcm

    def unavailable_office(_):
        raise OSError('Office COM 不可用')

    monkeypatch.setattr(pcm.win32com.client, 'Dispatch', unavailable_office)

    ok, msg = pcm.launch_and_start_show(str(tmp_path / '不存在的文件.pptx'))
    assert not ok and "不存在" in msg
