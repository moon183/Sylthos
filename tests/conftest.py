"""pytest 全局配置：Qt 无头模式，避免每次运行时手动设环境变量。"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


import pytest


@pytest.fixture(scope="session", autouse=True)
def qt_application_session():
    """Keep one QApplication alive across modules and clean widgets before exit."""
    from PySide6.QtCore import QCoreApplication, QEvent, QThreadPool
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
    QThreadPool.globalInstance().waitForDone(5000)
    for widget in app.topLevelWidgets():
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.fixture(autouse=True)
def isolated_floating_positions(monkeypatch, tmp_path):
    """窗口测试不得读取或改写用户实际保存的浮层位置。"""
    from PySide6.QtCore import QSettings
    import src.gui.floating_panel as panels

    monkeypatch.setattr(panels, "QSettings", lambda *_: QSettings(
        str(tmp_path / "floating.ini"), QSettings.Format.IniFormat))
    yield
    # Deliver deleteLater() before the next test changes the global theme.
    # Otherwise hidden windows retain theme subscribers across test cases.
    from PySide6.QtCore import QCoreApplication, QEvent
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
