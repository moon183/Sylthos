"""Render the new pages using only the hermetic acceptance evidence."""
import argparse
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import sys
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PySide6.QtWidgets import QApplication, QWidget, QScrollArea
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import QCoreApplication, QEvent
from qfluentwidgets import setTheme, Theme
from src.presentation_store import PresentationStore
from src.rehearsal_store import RehearsalStore
from src.coaching import PracticeStore
from src.assistant_dialogue import DialogueStore
from src.gui.coaching_page import CoachingPage
from src.gui.dialogue_page import AssistantDialoguePage
from src.gui.rehearsal_page import RehearsalPage
from src.gui.presentation_page import PresentationPage


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('evidence',type=Path)
    args=parser.parse_args()
    evidence=args.evidence.resolve()
    if not evidence.is_relative_to((ROOT/'build'/'complete_acceptance').resolve()):
        raise ValueError('Only synthetic complete_acceptance evidence is allowed.')
    app=QApplication([])
    font_id=QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc')
    family=QFontDatabase.applicationFontFamilies(font_id)[0] if font_id>=0 else None
    library=PresentationStore(evidence/'library')
    history=RehearsalStore(evidence/'rehearsals')
    tasks=PracticeStore(evidence/'tasks')
    output=evidence/'gui';output.mkdir(exist_ok=True)
    for theme in (Theme.LIGHT,Theme.DARK):
        setTheme(theme,save=False)
        with patch('src.gui.dialogue_page.DialogueStore', lambda root: DialogueStore(evidence/'dialogues')):
            pages=[('coaching',CoachingPage(library,history,tasks)),
                   ('dialogue',AssistantDialoguePage(library,history)),
                   ('timeline',RehearsalPage(history_dir=evidence/'rehearsals',presentation_store=library,
                                            settings_path=evidence/'never-online.json')),
                   ('plan',PresentationPage(store=library))]
        pages[0][1].compare()
        pages[1][1].store=DialogueStore(evidence/'dialogues')
        pages[1][1].refresh_history()
        if pages[1][1].history_combo.count()>1:
            pages[1][1].history_combo.setCurrentIndex(1)
        reports=history.reports()
        report=next(r for r in reports if r.get('transcripts'))
        pages[2][1]._show_report(report)
        for name,page in pages:
            if family:
                for widget in [page,*page.findChildren(QWidget)]:
                    font=widget.font();font.setFamily(family);widget.setFont(font)
            area=QScrollArea();area.setWidgetResizable(True);area.setWidget(page)
            area.resize(1080,760);area.show();app.processEvents()
            assert area.grab().save(str(output/f'{name}-{theme.value.lower()}.png'))
            if name=='dialogue':
                area.ensureWidgetVisible(page.panel)
                app.processEvents()
                assert area.grab().save(str(output/f'dialogue-output-{theme.value.lower()}.png'))
                page.panel.cancel(quiet=True)
            if name=='coaching':
                area.ensureWidgetVisible(page.tasks)
                app.processEvents()
                assert area.grab().save(str(output/f'coaching-tasks-{theme.value.lower()}.png'))
            if name=='plan':
                area.ensureWidgetVisible(page.plan_editor)
                app.processEvents()
                assert area.grab().save(str(output/f'plan-budget-{theme.value.lower()}.png'))
                page.ai_panel.cancel(quiet=True)
            if name=='timeline':
                page.ai_panel.cancel(quiet=True);page.content_panel.cancel(quiet=True)
            area.close();area.deleteLater()
            QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
            app.processEvents()
    print('Rendered synthetic light/dark GUI pages:',output)
    return 0


if __name__=='__main__': raise SystemExit(main())
