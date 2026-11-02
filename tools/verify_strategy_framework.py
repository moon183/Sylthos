"""Synthetic pipeline and UI artifact verification; no real network or personal data."""
from __future__ import annotations
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from src.strategy_framework import build_case, run_strategy, units
from src.strategy_evaluation import export_bundle, read_json, write_new, evaluate_batch, format_evaluation_md


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args()
    report=dict(id='d'*32,started_at=100,duration_s=95,status='completed',page_gaps=0,
        page_stay={1:95},presentation_context=dict(material_id='a'*32,material_version_id='b'*32,plan_id='c'*32),
        page_timeline=[dict(page=1,started_at=100,ended_at=195)],
        transcripts=[dict(id='s1',text='这是合成演示：通过手势识别控制翻页。',started_at=102,ended_at=110)])
    material=dict(material_id='a'*32,material_version_id='b'*32,name='合成策略演示（非真人数据）',version_no=1,
                  slides=[dict(page=1,title='合成演示',body='通过手势识别控制翻页。',notes='',supplement='',hidden=False)])
    plan=dict(id='c'*32,material_id='a'*32,material_version_id='b'*32,
              slide_plans=[dict(page=1,budget_s=60,key_points=['通过手势识别控制翻页'])])
    case=build_case(report,material,plan,origin='synthetic')
    export_bundle(args.out,case)
    annotation=read_json(args.out/'annotation.json')
    annotation.update(participant_code='SYNTHETIC-P01',reviewer='synthetic predefined labels',dataset_split='test',status='final')
    for row in annotation['labels']:
        row.update(verdict='issue' if row['unit_id']=='pacing:1' else 'clear' if row['unit_id']=='coverage:1:1' else 'unknown',
                   rationale='合成固定用例，不是真人标注或真实模型成绩。')
    write_new(args.out/'synthetic-labels.json',annotation)
    def complete(messages,**kwargs):
        checks=json.loads(messages[1]['content'])['checks']
        rows=[]
        for u in checks:
            if u['kind']=='pacing':
                rows.append(dict(unit_id=u['id'],verdict='issue',reason='合成预设超时。',citations=[dict(source='page:1',quote='')]))
            elif u['kind']=='coverage':
                rows.append(dict(unit_id=u['id'],verdict='clear',reason='合成预设重点证据。',citations=[dict(source='segment:s1',quote='通过手势识别控制翻页')]))
            else:
                rows.append(dict(unit_id=u['id'],verdict='unknown',reason='合成用例证据不足。',citations=[]))
        return dict(assessments=rows)
    client=SimpleNamespace(complete=complete,settings=SimpleNamespace(model='synthetic-stub'))
    items=[]
    for mode in ('local','baseline','skill','framework'):
        result=run_strategy(case,mode,client if mode!='local' else None)
        write_new(args.out/(mode+'.json'),result)
        items.append((case,annotation,result))
    evaluation=evaluate_batch(items)
    write_new(args.out/'synthetic-evaluation.json',evaluation)
    (args.out/'synthetic-evaluation.md').write_text(format_evaluation_md(evaluation),encoding='utf-8')
    from PySide6.QtWidgets import QApplication, QWidget
    from PySide6.QtGui import QFontDatabase
    from qfluentwidgets import setTheme, Theme
    from src.gui.coaching_page import CoachingPage
    from src.coaching import PracticeStore
    app=QApplication.instance() or QApplication([])
    font_id=QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc')
    family=QFontDatabase.applicationFontFamilies(font_id)[0] if font_id>=0 else None
    materials=SimpleNamespace(materials=lambda:[material],load_material=lambda _:deepcopy(material),load_plan=lambda _:deepcopy(plan),errors=[])
    history=SimpleNamespace(reports=lambda:[deepcopy(report)],errors=[])
    widget=CoachingPage(materials,history,PracticeStore(args.out/'tasks'))
    widget._selected_strategy_case=lambda:deepcopy(case)
    if family:
        for child in [widget,*widget.findChildren(QWidget)]:
            font=child.font();font.setFamily(family);child.setFont(font)
    widget.run_local_strategy()
    widget.resize(1100,1900)
    widget.show()
    for name,theme in [('light',Theme.LIGHT),('dark',Theme.DARK)]:
        setTheme(theme,save=False)
        app.processEvents()
        assert widget.strategy_card.grab().save(str(args.out/f'strategy-{name}.png'))
    widget.close()
    widget.deleteLater()
    app.processEvents()
    print(json.dumps(dict(origin='synthetic',out=str(args.out),cases=1,modes=4,network_calls=0),ensure_ascii=False))


if __name__=='__main__':
    main()
