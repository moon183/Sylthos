"""Render and run all three application Skills using synthetic fixtures, no network."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    from src.presentation_store import PresentationStore
    from src.assistant_api import ApiSettings
    from src.assistant_service import generate_plan
    from src.material_review import review_material
    from src.assistant_dialogue import DialogueSession,DialogueStore
    store=PresentationStore(args.out/'library')
    material=store.save_material(dict(source_name='合成Skill演示.pptx',source_sha256='a'*64,
        slides=[dict(page=1,slide_id='256',title='合成实现方案',body='已实现手势翻页。训练集准确率98%。',notes='尚未开展陌生人实验。',supplement='',hidden=False,warnings=[]),
                dict(page=2,slide_id='257',title='合成验证计划',body='计划开展独立测试，验证不同使用者的效果。',notes='',supplement='',hidden=False,warnings=['图片需人工核对'])]))
    def complete(messages,**kwargs):
        payload=json.loads(messages[-1]['content'])
        if 'scenario' in payload:
            return dict(overview='先说明实现，再说明已有验证的边界。',slide_plans=[dict(page=s['page'],budget_weight=1,key_points=['说明实现和验证边界'],script='以下是合成建议：解释已实现的功能，并明确尚未开展的测试。',transition='接下来说明验证方案。',questions=['如何设计独立测试？'],issues=['核对指标定义'],source_refs=[dict(page=s['page'],field='body',quote=s['body'])]) for s in payload['slides']])
        return dict(summary='合成展示：建议补充指标与数据划分说明。',checked_pages=payload['checked_pages'],findings=[dict(kind='source',priority='medium',reason='当前文字给出训练集结果，尚需核对独立测试口径。',action='明确区分训练集与独立测试，不把已有数字用于陌生人效果。',citations=[dict(page=1,field='body',quote='训练集准确率98%。')])])
    def complete_turn(messages,**kwargs):
        payload=json.loads(messages[1]['content']);state=payload['defense_state']
        first=state['first_question'];summary=payload['summarize']
        assessment='not_assessed' if first else 'partial'
        dimension=state['current_dimension'] if first or summary else state['transition_table'][assessment]
        question='' if summary else '你们如何实现手势翻页？' if first else '独立测试会如何划分样本？'
        result=dict(text='合成答辩建议：区分已完成的实现与尚待验证的效果。',citations=[dict(page=1,quote='已实现手势翻页。')],weak_questions=['独立测试设计'],answer_quote='' if first else payload['input'],
                    defense_feedback=dict(assessment=assessment,reason='当前回答说明已有边界，仍可补充独立测试方案。',question=question,dimension=dimension))
        return dict(role='assistant',content=json.dumps(result,ensure_ascii=False))
    client=SimpleNamespace(complete=complete,complete_turn=complete_turn,settings=ApiSettings(enabled=True,api_key='SYNTHETIC_ONLY',model='synthetic-stub'))
    plan=generate_plan(client,material,'答辩老师',120,'实现与验证',scenario='innovation')
    saved=store.save_plan(material['material_version_id'],'答辩老师',120,'实现与验证',plan['slide_plans'],overview=plan['overview'],generation=plan['generation'],skill=plan['skill'])
    review=review_material(client,material)
    session=DialogueSession(material,defense_profile='adaptive')
    session.run(client,'开始提问','defense')
    session.run(client,'我们尚未开展独立测试，准备按测试者划分数据。','defense')
    DialogueStore(args.out/'dialogues').save(session.record())
    for name,result in [('planning',saved),('material-review',review),('defense',session.record())]:
        (args.out/(name+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    from PySide6.QtWidgets import QApplication,QWidget
    from PySide6.QtGui import QFontDatabase
    from qfluentwidgets import setTheme,Theme
    from src.gui.presentation_page import PresentationPage
    from src.gui import dialogue_page as dialogue_module
    dialogue_module.PROJECT_ROOT=args.out.resolve()
    AssistantDialoguePage=dialogue_module.AssistantDialoguePage
    app=QApplication.instance() or QApplication([])
    font_id=QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc')
    family=QFontDatabase.applicationFontFamilies(font_id)[0] if font_id>=0 else None
    page=PresentationPage(store)
    page.review_panel.show_result(review)
    dialogue=AssistantDialoguePage(store,SimpleNamespace(reports=lambda:[]))
    dialogue.store=DialogueStore(args.out/'dialogues')
    dialogue.mode_combo.setCurrentIndex(1)
    dialogue.panel.show_result(dict(session=session,record=session.record(),result=session.turns[-1]['result'],context=session.context))
    for panel in (page.ai_panel,page.review_panel,dialogue.panel):
        panel.setFixedHeight(420)
        panel.status_label.setText('合成Skill演示：未调用真实接口，结果只用于验证界面。')
    for widget in (page,dialogue):
        if family:
            for child in [widget,*widget.findChildren(QWidget)]:
                font=child.font();font.setFamily(family);child.setFont(font)
        widget.resize(1100,2600);widget.show()
    for theme in (Theme.LIGHT,Theme.DARK):
        setTheme(theme,save=False);app.processEvents()
        for name,widget in [('planning-profile',page.scenario_combo.parentWidget()),('planning-result',page.ai_panel),('material-review',page.review_panel),('defense',dialogue.panel)]:
            assert widget.grab().save(str(args.out/(name+'-'+theme.value.lower()+'.png')))
    for widget in (page,dialogue):widget.close();widget.deleteLater()
    app.processEvents()
    (args.out/'verification.json').write_text(json.dumps(dict(origin='synthetic',skills=3,network_calls=0,real_model_verified=False),indent=2),encoding='utf-8')
    print(json.dumps(dict(origin='synthetic',skills=3,network_calls=0,out=str(args.out)),ensure_ascii=False))


if __name__=='__main__':main()
