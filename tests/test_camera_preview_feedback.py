"""实测回归：导航过程中旧帧同步缩放、画面圆角、空态提示中心稳定。"""
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtGui import QImage, QColor
from PySide6.QtWidgets import QApplication

from src.gui.fluent_window import PreviewPage, FluentMainWindow


@pytest.fixture
def page():
    app = QApplication.instance() or QApplication([])
    widget = PreviewPage({})
    widget.resize(1117, 672)
    widget.show()
    app.processEvents()
    yield widget
    widget.close()
    widget.deleteLater()
    app.processEvents()


def deliver(page):
    frame = QImage(1280, 720, QImage.Format.Format_RGB32)
    frame.fill(QColor("#ef8030"))
    FluentMainWindow._on_frame(SimpleNamespace(preview_page=page), frame)


@pytest.mark.parametrize("start,end", [(1.0, 0.0), (0.0, 1.0)])
def test_frame_resizes_without_new_camera_frame_and_keeps_round_corners(page, start, end):
    page.apply_blend(start)
    deliver(page)
    for step in range(11):
        page.apply_blend(start + (end-start)*step/10)
        QApplication.processEvents()
        image = page.preview.grab().toImage()
        # 内容到达两侧，不能仍停在启动时大小；四角必须被裁剪。
        color = QColor("#ef8030")
        assert image.pixelColor(image.width()-3, image.height()//2) == color
        assert image.pixelColor(2, image.height()//2) == color
        for x, y in [(0, 0), (image.width()-1, 0),
                     (0, image.height()-1), (image.width()-1, image.height()-1)]:
            assert image.pixelColor(x, y) != color


@pytest.mark.parametrize("height", [672, 673])
def test_placeholder_has_no_vertical_one_pixel_bounce(page, height):
    page.resize(1117, height)
    positions = []
    for step in list(range(31)) + list(reversed(range(31))):
        page.apply_blend(step/30)
        QApplication.processEvents()
        positions.append(page.placeholder.mapTo(page, QPoint(0, 0)).y())
    assert len(set(positions)) == 1


def test_non_widescreen_frame_is_centered_and_not_stretched(page):
    frame = QImage(640, 480, QImage.Format.Format_RGB32)
    frame.fill(QColor("#ef8030"))
    FluentMainWindow._on_frame(SimpleNamespace(preview_page=page), frame)
    image = page.preview.grab().toImage()
    assert image.pixelColor(10, image.height()//2) == QColor("#111111")
    assert image.pixelColor(image.width()-11, image.height()//2) == QColor("#111111")
    assert image.pixelColor(image.width()//2, image.height()//2) == QColor("#ef8030")
