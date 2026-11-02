"""用户反馈回归：真实名称、无设备、插拔重排与正确后端。"""
import copy
import json
from unittest.mock import Mock

import cv2
import pytest
from PySide6.QtWidgets import QApplication
from qfluentwidgets import BodyLabel

from src.config import load_config
from src.camera_devices import CameraDevice
import src.camera_devices as devices
import src.gui.camera_selector as selector
import src.gui.fluent_window as window


@pytest.fixture
def page(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(window, 'CONFIG_PATH', tmp_path / 'config.json')
    monkeypatch.setattr(selector, 'list_cameras', lambda backend: [
        CameraDevice(0, '内置相机', 'builtin', backend),
        CameraDevice(3, 'USB Camera', 'usb', backend)])
    config = copy.deepcopy(load_config())
    config['camera'].update(index=0, backend='MSMF')
    config['camera'].pop('device_path', None)
    widget = window.SettingsPage(config)
    yield widget, tmp_path / 'config.json'
    widget.close()
    widget.deleteLater()
    app.processEvents()


def test_named_camera_selection_without_annotation(page):
    widget, path = page
    combo = widget.camera_combo
    assert combo.currentText() == '内置相机'
    assert [combo.itemText(i) for i in range(combo.count())] == ['内置相机', 'USB Camera']
    assert [w.text() for w in widget._setting_cards['camera.index'].findChildren(BodyLabel)] == ['摄像头']
    assert not path.exists()
    original = dict(widget._config['camera'])
    widget.on_saved = Mock()
    combo.setCurrentIndex(1)
    saved = json.loads(path.read_text(encoding='utf-8'))
    assert saved['camera'] == {**original, 'index': 3, 'backend': 'MSMF', 'device_path': 'usb'}
    widget.on_saved.assert_not_called()
    combo.refresh_devices()
    assert combo.currentText() == 'USB Camera'


def test_unplug_replug_and_no_devices_do_not_overwrite_config(page, monkeypatch):
    widget, path = page
    combo = widget.camera_combo
    combo.setCurrentIndex(1)
    saved = path.read_bytes()
    monkeypatch.setattr(selector, 'list_cameras', lambda backend: [])
    combo.refresh_devices()
    assert combo.currentText() == '无'
    assert combo.count() == 1
    assert path.read_bytes() == saved
    monkeypatch.setattr(selector, 'list_cameras', lambda backend: [
        CameraDevice(5, 'USB Camera', 'usb', backend)])
    combo.refresh_devices()
    assert combo.currentText() == 'USB Camera'
    assert path.read_bytes() == saved


def test_missing_selection_and_duplicate_names(page, monkeypatch):
    widget, path = page
    widget._config['camera']['device_path'] = 'absent'
    monkeypatch.setattr(selector, 'list_cameras', lambda backend: [
        CameraDevice(0, 'USB Camera', 'a', backend), CameraDevice(1, 'USB Camera', 'b', backend)])
    widget.camera_combo.refresh_devices()
    assert widget.camera_combo.currentIndex() == -1
    assert widget.camera_combo.itemText(0) != widget.camera_combo.itemText(1)
    assert not path.exists()
    widget.camera_combo.setCurrentIndex(1)
    assert widget._config['camera']['device_path'] == 'b'


def test_enumeration_failure_is_safe(page, monkeypatch):
    monkeypatch.setattr(selector, 'list_cameras', Mock(side_effect=RuntimeError('unavailable')))
    page[0].camera_combo.refresh_devices()
    assert page[0].camera_combo.currentText() == '无'
    assert not page[1].exists()


@pytest.mark.parametrize('backend,api', [('DSHOW', cv2.CAP_DSHOW), ('MSMF', cv2.CAP_MSMF)])
def test_enumeration_retains_backend_index(monkeypatch, backend, api):
    enum = Mock(return_value=[CameraDevice(4, 'camera', 'path', backend)])
    monkeypatch.setattr(devices, 'enumerate_cameras', enum)
    assert devices.list_cameras(backend) == [CameraDevice(4, 'camera', 'path', backend)]
    enum.assert_called_once_with(api)


def test_any_backend_fallback_does_not_use_encoded_indices(monkeypatch):
    enum = Mock(side_effect=[[], [CameraDevice(2, 'camera', 'p', 'DSHOW')]])
    monkeypatch.setattr(devices, 'enumerate_cameras', enum)
    assert devices.list_cameras('ANY') == [CameraDevice(2, 'camera', 'p', 'DSHOW')]
    assert [c.args[0] for c in enum.call_args_list] == [cv2.CAP_MSMF, cv2.CAP_DSHOW]


def test_capture_resolves_reordered_device_and_rejects_missing(monkeypatch):
    from src.capture import CameraCapture
    monkeypatch.setattr(devices, 'list_cameras', lambda backend: [CameraDevice(5, 'camera', 'USB', backend)])
    capture = Mock()
    monkeypatch.setattr(cv2, 'VideoCapture', capture)
    CameraCapture(0, 1280, 720, backend='MSMF', device_path='usb')
    assert capture.call_args.args == (5, cv2.CAP_MSMF)
    capture.reset_mock()
    with pytest.raises(RuntimeError, match='已断开'):
        CameraCapture(0, 1280, 720, backend='MSMF', device_path='missing')
    capture.assert_not_called()
    assert devices.resolve_camera_index(7, 'MSMF', '') == 7
