from PySide6.QtWidgets import QApplication
from src.coaching import PracticeStore
from src.gui.coaching_page import CoachingPage

class Materials:
    def materials(self):
        return [dict(material_version_id='a'*32, name='演讲', version_no=1)]
    def load_material(self, version):
        return dict(slides=[dict(page=1)])
class Rehearsals:
    def reports(self):
        return [dict(id='b'*32, started_at=2, duration_s=30, page_stay={1:30}, presentation_context=dict(material_version_id='a'*32, target_duration_s=40)), dict(id='c'*32, started_at=1, duration_s=50, page_stay={1:50}, presentation_context=dict(material_version_id='a'*32, target_duration_s=40))]

def test_create_complete_compare_refresh(tmp_path):
    app = QApplication.instance() or QApplication([])
    store = PracticeStore(tmp_path)
    page = CoachingPage(Materials(), Rehearsals(), store)
    page.task_text.setPlainText('练习开场')
    page.task_page.setValue(1)
    page.target_seconds.setValue(35)
    page.add_task()
    assert store.list_tasks()[0]['page'] == 1
    assert '30.0' in page.tasks.item(0).text()
    page.tasks.setCurrentRow(0)
    page.complete_task()
    assert store.list_tasks()[0]['status'] == 'done'
    page.before_combo.setCurrentIndex(1)
    page.after_combo.setCurrentIndex(0)
    page.compare()
    assert page.comparison['duration_delta_s'] == -20
    page.refresh()
    assert page.material_combo.count() == 1
    page.deleteLater()
    app.processEvents()

def test_task_displays_latest_page_plan_target(tmp_path):
    class WithPlan(Materials):
        def load_plan(self, identity):
            return dict(material_version_id='a'*32, slide_plans=[dict(page=1, budget_s=42)])
    class Planned(Rehearsals):
        def reports(self):
            reports = super().reports()
            reports[0]['presentation_context']['plan_id'] = 'd'*32
            return reports
    app = QApplication.instance() or QApplication([])
    store = PracticeStore(tmp_path)
    store.add({'material_version_id':'a'*32}, '开场', 1, 35)
    page = CoachingPage(WithPlan(), Planned(), store)
    assert '42' in page.tasks.item(0).text()
    page.deleteLater()
    app.processEvents()

def test_fluent_cards_without_nested_page_scroll(tmp_path):
    from PySide6.QtWidgets import QScrollArea
    from qfluentwidgets import ComboBox, PlainTextEdit, PushButton, TitleLabel
    from src.gui.theme_style import CardWidget
    app = QApplication.instance() or QApplication([])
    page = CoachingPage(Materials(), Rehearsals(), PracticeStore(tmp_path))
    assert isinstance(page.material_combo, ComboBox)
    assert isinstance(page.task_text, PlainTextEdit)
    assert len(page.findChildren(CardWidget)) >= 2
    assert page.findChildren(TitleLabel)
    assert not page.findChildren(QScrollArea)
    assert page.findChildren(PushButton)
    page.deleteLater()
    app.processEvents()

def test_manual_task_rejects_page_outside_material(tmp_path):
    class SingleSlide(Materials):
        def load_material(self, version):
            return dict(slides=[dict(page=1)])
    app = QApplication.instance() or QApplication([])
    store=PracticeStore(tmp_path)
    page=CoachingPage(SingleSlide(), Rehearsals(), store)
    page.task_text.setPlainText('practice')
    page.task_page.setValue(999)
    page.add_task()
    assert store.list_tasks()==[]
    assert page.status.text()
    page.deleteLater()
    app.processEvents()

def test_task_spins_text_has_visible_width(tmp_path):
    app = QApplication.instance() or QApplication([])
    page=CoachingPage(Materials(), Rehearsals(), PracticeStore(tmp_path))
    page.resize(1100,900)
    page.show()
    page.task_page.setValue(999)
    page.target_seconds.setValue(123.45)
    app.processEvents()
    try:
        for spin in (page.task_page,page.target_seconds):
            text=spin.lineEdit()
            margins=text.textMargins()
            assert text.width() >= text.fontMetrics().horizontalAdvance(text.text())+margins.left()+margins.right()
    finally:
        page.close()
        page.deleteLater()
        app.processEvents()
