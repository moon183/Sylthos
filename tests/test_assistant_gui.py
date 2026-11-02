"""API UI and late-response protection, with a synthetic in-memory client."""
from copy import deepcopy
from threading import Event

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLineEdit
import pytest

from test_assistant_service import FakeClient, material, report


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def finish(widget, app):
    widget.close()
    widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


def wait(panel, app):
    for _ in range(200):
        app.processEvents()
        if not panel.busy:
            return
        QTest.qWait(10)
    pytest.fail('AI task did not finish')


def configure(path):
    from src.assistant_api import ApiSettings, save_api_settings
    save_api_settings(ApiSettings(enabled=True, api_key='test-only-key'), path)


def test_config_dialog_has_editable_api_fields_and_masked_key(tmp_path, app):
    from src.gui.assistant_panel import ApiSettingsDialog
    from src.assistant_api import load_api_settings
    path = tmp_path / 'api.json'
    dialog = ApiSettingsDialog(settings_path=path)
    assert dialog.key_edit.echoMode() == QLineEdit.EchoMode.Password
    assert dialog.key_edit.text() == '' and not dialog.enabled_check.isChecked()
    dialog.enabled_check.setChecked(True)
    dialog.url_edit.setText('https://example.com/v1')
    dialog.model_edit.setText('custom-model')
    dialog.key_edit.setText('test-only-key')
    assert dialog.save_settings()
    saved = load_api_settings(path)
    assert saved.enabled and saved.model == 'custom-model' and saved.api_key == 'test-only-key'
    finish(dialog, app)


def test_settings_dialog_preserves_key_when_numeric_config_is_invalid(tmp_path, app):
    import json
    from src.gui.assistant_panel import ApiSettingsDialog
    from src.assistant_api import load_api_settings
    path = tmp_path/'api.json'
    path.write_text(json.dumps({'enabled':True, 'api_key':'private-test-key', 'max_tokens':10000000000}), encoding='utf8')
    dialog = ApiSettingsDialog(settings_path=path)
    assert dialog.key_edit.text() == 'private-test-key'
    assert 'max_tokens' in dialog.status_label.text()
    assert dialog.tokens_edit.text() == '10000000000'
    assert 'private-test-key' not in dialog.status_label.text()
    dialog.tokens_edit.setText('65536')
    assert dialog.save_settings()
    assert load_api_settings(path).api_key == 'private-test-key'
    assert load_api_settings(path).max_tokens == 65536
    finish(dialog, app)


def test_settings_dialog_can_leave_output_budget_to_model(tmp_path, app):
    from src.gui.assistant_panel import ApiSettingsDialog
    from src.assistant_api import load_api_settings
    path = tmp_path/'api.json'
    dialog = ApiSettingsDialog(settings_path=path)
    dialog.tokens_edit.clear()
    assert dialog.save_settings()
    assert load_api_settings(path).max_tokens is None
    finish(dialog, app)


def test_disabled_settings_do_not_start_worker(tmp_path, app):
    from src.gui.assistant_panel import AssistantPanel
    called = []
    panel = AssistantPanel('AI', '生成', lambda: lambda *a, **k: called.append(1), str,
                           settings_path=tmp_path/'api.json')
    panel.start_action()
    assert not panel.busy and not called and '开启' in panel.status_label.text()
    finish(panel, app)


def test_generated_plan_preview_adoption_reload_and_manual_save_preserves_ai(tmp_path, app):
    from src.gui.presentation_page import PresentationPage
    from src.presentation_store import PresentationStore
    from test_presentation_store import draft
    store = PresentationStore(tmp_path/'library')
    saved = store.save_material(draft())
    page = PresentationPage(store=store)
    configure(tmp_path/'api.json')
    page.ai_panel.settings_path = tmp_path/'api.json'
    page.ai_panel.client_factory = lambda _: FakeClient()
    page.ai_panel.start_action()
    wait(page.ai_panel, app)
    assert '讲述建议' in page.ai_panel.output.toPlainText()
    assert store.plans() == []
    assert page.ai_panel.adopt_result()
    plan = store.plans()[0]
    assert plan['material_version_id'] == saved['material_version_id']
    assert plan['slide_plans'][0]['script'] == '讲述建议'
    assert page.save_plan()
    assert store.plans()[0]['slide_plans'][0]['script'] == '讲述建议'
    finish(page, app)


def test_cancellation_drops_late_result_and_releases_ui(tmp_path, app):
    from src.gui.assistant_panel import AssistantPanel
    configure(tmp_path/'api.json')
    entered, release = Event(), Event()
    def prepare():
        def run(client, **kwargs):
            entered.set()
            release.wait(3)
            return {'old':'result'}
        return run
    panel = AssistantPanel('AI', '生成', prepare, str, settings_path=tmp_path/'api.json')
    panel.client_factory = lambda _: FakeClient()
    panel.start_action()
    assert entered.wait(1)
    panel.cancel()
    release.set()
    QTest.qWait(100)
    app.processEvents()
    assert not panel.busy and panel.result is None
    assert 'old' not in panel.output.toPlainText()
    finish(panel, app)


def test_change_material_invalidates_preview(tmp_path, app):
    from src.gui.presentation_page import PresentationPage
    from src.presentation_store import PresentationStore
    from test_presentation_store import draft
    store = PresentationStore(tmp_path/'library')
    first = store.save_material(draft())
    page = PresentationPage(store=store)
    configure(tmp_path/'api.json')
    page.ai_panel.settings_path = tmp_path/'api.json'
    page.ai_panel.client_factory = lambda _: FakeClient()
    page.ai_panel.start_action()
    wait(page.ai_panel, app)
    changed = draft()
    changed['source_sha256'] = 'b'*64
    second = store.save_material(changed)
    page._set_material(second)
    assert page.ai_panel.result is None
    assert not page.ai_panel.adopt_result() and store.plans() == []
    finish(page, app)


def test_rehearsal_analysis_uses_selected_report_and_export(tmp_path, app):
    from src.gui.rehearsal_page import RehearsalPage
    page = RehearsalPage(history_dir=tmp_path/'history')
    configure(tmp_path/'api.json')
    page.ai_panel.settings_path = tmp_path/'api.json'
    page.ai_panel.output_dir = tmp_path/'exports'
    page.ai_panel.client_factory = lambda _: FakeClient([{'summary':'精简第1页。', 'suggestions':[
        dict(page=1, advice='缩短背景说明。', evidence_ids=['page_1'])]}])
    source = report()
    source.update(started_at=1000, ended_at=1200, updated_at=1200, reason='', command_labels={}, events=[])
    page._show_report(source)
    page.ai_panel.start_action()
    wait(page.ai_panel, app)
    assert '100' in page.ai_panel.output.toPlainText()
    exported = page.ai_panel.export_result()
    assert exported.exists() and '缩短背景说明' in exported.read_text(encoding='utf8')
    assert 'test-only-key' not in exported.read_text(encoding='utf8')
    page._clear_report()
    assert page.ai_panel.result is None
    finish(page, app)


def test_waiting_feedback_tracks_elapsed_and_stops_on_cancel(tmp_path, app, monkeypatch):
    from src.gui.assistant_panel import AssistantPanel
    import src.gui.assistant_panel as ui
    configure(tmp_path/'api.json')
    clock = [100.0]
    monkeypatch.setattr(ui.time, 'monotonic', lambda: clock[0])
    entered, release = Event(), Event()
    def prepare():
        def action(client, **kwargs):
            entered.set()
            release.wait(3)
            return {'ok': True}
        return action
    panel = AssistantPanel('AI', '生成', prepare, str, settings_path=tmp_path/'api.json')
    panel.client_factory = lambda _: FakeClient()
    try:
        panel.start_action()
        assert entered.wait(1)
        clock[0] = 165.0
        panel._update_waiting()
        assert '65' in panel.wait_label.text()
        panel._progress(panel._token, '正在生成第2批')
        assert '第2批' in panel.status_label.text()
        assert '65' in panel.wait_label.text()
        assert panel.wait_timer.isActive()
        panel.cancel()
        assert not panel.wait_timer.isActive()
        assert panel.wait_label.isHidden()
        old = panel.status_label.text()
        panel._update_waiting()
        assert panel.status_label.text() == old
    finally:
        release.set()
        QTest.qWait(50)
        finish(panel, app)


def test_waiting_timer_stops_when_request_finishes(tmp_path, app):
    from src.gui.assistant_panel import AssistantPanel
    configure(tmp_path/'api.json')
    panel = AssistantPanel('AI', '生成', lambda: lambda *a, **k: {'ok':True}, str,
                           settings_path=tmp_path/'api.json')
    panel.client_factory = lambda _: FakeClient()
    panel.start_action()
    wait(panel, app)
    assert not panel.wait_timer.isActive()
    assert panel.wait_label.isHidden()
    finish(panel, app)
