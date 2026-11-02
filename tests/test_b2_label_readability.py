"""主题切换后保留校准说明层级，并保证自定义色号可读。"""
import pytest

from PySide6.QtCore import QEvent
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import CaptionLabel, Theme, qconfig, setTheme, setThemeColor

from src.gui.theme_page import PaletteDialog
from src.gui.theme_style import contrast
from src.gui.wizard_inline import WizardPanel


@pytest.fixture
def app():
    app = QApplication.instance() or QApplication([])
    mode = qconfig.get(qconfig.themeMode)
    color = qconfig.get(qconfig.themeColor)
    yield app
    setTheme(mode, save=False)
    setThemeColor(color, save=False)
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_wizard_labels_survive_theme_and_accent_changes(app):
    panel = WizardPanel()
    panel.show_step(0, "测量中", 30)
    panel.show()
    try:
        for mode, accent in [(Theme.LIGHT, '#009faa'),
                             (Theme.DARK, '#795548'),
                             (Theme.LIGHT, '#abd397')]:
            setTheme(mode, save=False)
            setThemeColor(QColor(accent), save=False)
            app.processEvents()
            for label in [panel.step_desc, *panel.findChildren(CaptionLabel)]:
                assert label.palette().color(QPalette.ColorRole.WindowText).name() == '#8a8a8a'
            for label in [panel.step_desc, panel.step_prog, panel.center_label]:
                assert label.font().pixelSize() == 12
            assert panel.step_prog.font().bold()
    finally:
        panel.close()
        panel.deleteLater()


@pytest.mark.parametrize('background', ['#ffff00', '#00ff00', '#0000ff', '#ff0000', '#000000', '#ffffff'])
def test_palette_hex_text_contrasts_with_selected_color(app, background):
    parent = QWidget()
    dialog = PaletteDialog(QColor(background), parent)
    try:
        dialog._preview.ensurePolished()
        foreground = dialog._preview.palette().color(QPalette.ColorRole.WindowText)
        assert contrast(dialog.color(), foreground) >= 4.5
        assert dialog._preview.text() == dialog.color().name().upper()
    finally:
        parent.deleteLater()
