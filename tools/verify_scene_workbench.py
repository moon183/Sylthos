"""Synthetic scenario workflow and whole-window visual QA. Never uses a real API/device."""
import argparse
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    from src.gui import presentation_page,rehearsal_page,dialogue_page,coaching_page,fluent_window,theme_page,asr_page,floating_panel
    for module in (presentation_page,rehearsal_page,dialogue_page,coaching_page,fluent_window):module.PROJECT_ROOT=out
    for module in (fluent_window,theme_page,asr_page):module.CONFIG_PATH=out/'config.json'
    from PySide6.QtCore import QSettings
    floating_panel.QSettings=lambda *_:QSettings(str(out/'positions.ini'),QSettings.Format.IniFormat)
    from src.presentation_store import PresentationStore
    from src.rehearsal_store import RehearsalStore
    from src.rehearsal import RehearsalRecorder
    from src.assistant_service import generate_plan
    from src.assistant_api import ApiSettings
    from src.material_review import review_material
    from src.config import load_config
    from tools.build_exe import sanitize_config
    store=PresentationStore(out/'logs'/'presentations')
    material=store.save_material(dict(source_name='合成场景演示.pptx',source_sha256='a'*64,
        slides=[dict(page=1,slide_id='256',title='从感知到应用',body='采集传感器数据，经网关传至应用端。',notes='目前只完成原型链路，稳定性仍需验证。',supplement='',hidden=False,warnings=[]),
                dict(page=2,slide_id='257',title='验证与边界',body='计划开展断网、延迟和长时间运行测试。',notes='',supplement='',hidden=False,warnings=['图表需人工核对'])]))
    def complete(messages,**kwargs):
        payload=json.loads(messages[-1]['content'])
        if 'scenario' in payload:
            return dict(overview='围绕数据闭环解释实现，再说明验证边界。',slide_plans=[dict(page=s['page'],budget_weight=1,key_points=['讲清数据链路与验证依据'],script='合成讲稿：先解释采集、通信与应用，再明确当前完成范围及待验证项。',transition='接下来说明系统如何验证。',questions=['断网时系统如何处理？'],issues=['补充测试条件'],source_refs=[dict(page=s['page'],field='body',quote=s['body'])]) for s in payload['slides']])
        return dict(summary='合成检查建议：明确区分原型完成与稳定性验证。',checked_pages=payload['checked_pages'],findings=[dict(kind='source',priority='medium',reason='当前文字说明了计划，但尚需核对验证记录。',action='补充断网、时延与运行测试的实际条件及结果。',citations=[dict(page=2,field='body',quote='计划开展断网、延迟和长时间运行测试。')])])
    client=SimpleNamespace(complete=complete,settings=ApiSettings(enabled=True,api_key='SYNTHETIC_ONLY',model='synthetic-stub'))
    generated=generate_plan(client,material,'技术评委',120,'链路与证据',scene='iot_design')
    plan=store.save_plan(material['material_version_id'],'技术评委',120,'链路与证据',generated['slide_plans'],overview=generated['overview'],generation=generated['generation'],skill=generated['skill'],scene=generated['scene'])
    context=next(c for c in store.contexts() if c['plan_id']==plan['id'])
    history=RehearsalStore(out/'logs'/'rehearsals');rec=RehearsalRecorder(history)
    with patch('src.rehearsal.time.time',return_value=100):rec.start(presentation_context=context)
    rec.on_page(1,100)
    with patch('src.rehearsal.time.time',return_value=120):rec.on_transcript(dict(id='synthetic1',text='采集传感器数据，经网关传至应用端。',started_at=102,ended_at=110))
    rec.on_page(2,195)
    with patch('src.rehearsal.time.time',return_value=250):report=rec.stop()
    from PySide6.QtWidgets import QApplication,QWidget
    from PySide6.QtGui import QFontDatabase
    from PySide6.QtTest import QTest
    from qfluentwidgets import Theme,setTheme
    app=QApplication.instance() or QApplication([])
    font_id=QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc')
    QFontDatabase.addApplicationFont('C:/Windows/Fonts/cambria.ttc')
    family=QFontDatabase.applicationFontFamilies(font_id)[0] if font_id>=0 else None
    config=sanitize_config(load_config());config.setdefault('asr',{})['enabled']=False
    window=fluent_window.FluentMainWindow(config)
    if family:
        for child in [window,*window.findChildren(QWidget)]:
            if child is window.titleBar.titleLabel:continue
            font=child.font();font.setFamily(family);child.setFont(font)
    window.presentation_page.review_panel.show_result(review_material(client,material,scene=plan['scene']))
    window.coaching_page.run_local_strategy()
    window.navigationInterface.panel.expand();window.show();QTest.qWait(400)
    for theme in (Theme.LIGHT,Theme.DARK):
        setTheme(theme,save=False);app.processEvents();QTest.qWait(80)
        # Use registered interfaces, never navigate by assumptions about Qt parent chains.
        window.switchTo(next(area for area in window.findChildren(QWidget) if area.objectName()=='workbench' and area is not window.workbench_page))
        QTest.qWait(350)
        assert window.grab().save(str(out/('workbench-'+theme.value.lower()+'.png')))
        for route,tab,name in [('prepare','prepare','planning'),('prepare','review','material-review'),('rehearse','live','rehearsal')]:
            window._open_workflow(route)
            page=window.presentation_page if route=='prepare' else window.rehearsal_page
            page.task_tabs.set_current(tab);QTest.qWait(350)
            assert window.grab().save(str(out/(name+'-'+theme.value.lower()+'.png')))
        window.workbench_page.scene_selector.set_scene('primary_open_class')
        window._open_workflow('defense');QTest.qWait(350)
        assert window.grab().save(str(out/('teaching-'+theme.value.lower()+'.png')))
        window.workbench_page.scene_selector.set_scene('iot_design')
    assert window._worker is None
    window._closing=True  # Only synthetic drafts exist; bypass the interactive discard dialog.
    window.close();window.deleteLater();app.processEvents()
    receipt=dict(origin='synthetic',scenes=22,network_calls=0,devices_started=False,material_version_id=material['material_version_id'],plan_id=plan['id'],rehearsal_id=report['id'])
    (out/'verification.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False))


if __name__=='__main__':main()
