"""A3 备注提词链路真机验证工具（诊断用，与 tools/diagnose_custom_gesture.py 同类）：
COM 创建带备注的临时演示文稿 → 放映 → 用项目真实的 PptComController
轮询线程读取当前页备注 → 断言缓存内容正确 → 清理现场（不污染用户 PPT 实例）。
用法：PYTHONPATH=<项目根> python tools/verify_a3_notes.py
"""
import time

import pythoncom
import win32com.client

NOTE_TEXT = "A3验证：这是第一页的演讲者备注，应当被轮询线程读到。"

pythoncom.CoInitialize()
app = None
created_app = False
pres = None
try:
    try:
        app = win32com.client.GetActiveObject("PowerPoint.Application")
        print("检测到 PowerPoint 已在运行， attach 现有实例（结束后不退出它）")
    except Exception:
        app = win32com.client.Dispatch("PowerPoint.Application")
        created_app = True
        print("PowerPoint 未运行，已新建实例（结束后退出）")

    pres = app.Presentations.Add()
    slide = pres.Slides.Add(1, 12)  # ppLayoutBlank
    slide.NotesPage.Shapes.Placeholders(2).TextFrame.TextRange.Text = NOTE_TEXT
    pres.SlideShowSettings.Run()
    time.sleep(1.0)  # 等放映窗口就绪

    from src.control.ppt_com import PptComController

    ppt = PptComController()
    ppt.start_polling(250)
    time.sleep(1.2)  # 等至少两轮轮询写缓存
    pos = ppt.position_cached()
    notes = ppt.notes_cached()
    running = ppt.is_running_cached()
    ppt.stop_polling()

    print(f"position_cached() = {pos}")
    print(f"is_running_cached() = {running}")
    print(f"notes_cached() = {notes!r}")
    assert running, "放映状态应为 True"
    assert pos == (1, 1), f"页码应为 (1, 1)，实际 {pos}"
    assert notes == NOTE_TEXT, "备注内容不匹配"
    print("A3 链路验证通过：COM 轮询线程正确读到当前页备注（缓存读取，管线零阻塞）")
finally:
    try:
        if app is not None and app.SlideShowWindows.Count >= 1:
            app.SlideShowWindows(1).View.Exit()
    except Exception:
        pass
    try:
        if pres is not None:
            pres.Saved = True  # 免保存提示
            pres.Close()
    except Exception:
        pass
    if created_app:
        try:
            app.Quit()
        except Exception:
            pass
    pythoncom.CoUninitialize()
