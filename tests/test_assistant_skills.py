"""Application Skill contracts; all data and clients are synthetic."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from threading import Event
from unittest.mock import Mock

import pytest

from src.assistant_api import AssistantError, AssistantCancelled, ApiSettings
from src.assistant_skill_runtime import (load_skill, skill_metadata, skill_prompt, material_snapshot,
                                        validate_metadata, validate_refs)
from src.assistant_service import generate_plan
from src.assistant_dialogue import DialogueSession, DialogueStore
from src.material_review import review_material, local_material_checks, format_material_review


@pytest.fixture
def material():
    return dict(material_id='a'*32,material_version_id='b'*32,private_path='C:/private/deck.pptx',
        slides=[dict(page=1,title='实现方案',body='已实现手势翻页。训练集准确率98%。',notes='未开展陌生人实验。',supplement='',hidden=False,warnings=[]),
                dict(page=2,title='实验结论',body='陌生人识别准确率98%。',notes='',supplement='',hidden=False,warnings=['图片需人工核对'])])


def ref(page=1,field='body',quote='已实现手势翻页。'):
    return dict(page=page,field=field,quote=quote)


def plan_client():
    def complete(messages,**kwargs):
        payload=json.loads(messages[-1]['content'])
        return dict(overview='合成讲述建议',slide_plans=[dict(page=s['page'],budget_weight=1,
            key_points=['说明实现与验证边界'],script='合成建议讲稿',transition='接下来说明验证。',questions=['如何验证？'],issues=[],
            source_refs=[ref(s['page'],'body',s['body'])]) for s in payload['slides']])
    return SimpleNamespace(complete=Mock(side_effect=complete),settings=ApiSettings(enabled=True,api_key='SYNTHETIC_SECRET'))


@pytest.mark.parametrize('identity',['planning','defense','material_review'])
def test_skills_have_executable_contract_and_version(identity):
    skill=load_skill(identity)
    profile=next(iter(skill['spec']['profiles']))
    metadata=skill_metadata(skill,profile)
    validate_metadata(metadata)
    assert len(metadata['sha256'])==64
    assert skill['spec']['steps'] and skill['spec']['validation']
    assert 'Skill' in skill_prompt(skill,profile)


def test_skill_paths_and_corrupt_files_fail_before_use(tmp_path):
    with pytest.raises(AssistantError):load_skill('../planning')
    with pytest.raises(AssistantError):load_skill('planning',tmp_path)
    folder=tmp_path/'planning';folder.mkdir()
    (folder/'skill.json').write_text('{}')
    (folder/'SKILL.md').write_text('instructions')
    with pytest.raises(AssistantError):load_skill('planning',tmp_path)


def test_editable_skill_instructions_change_hash_and_prompt(tmp_path):
    import shutil
    original=load_skill('planning')
    root=Path(__file__).resolve().parents[1]/'src'/'assistant_skills'
    shutil.copytree(root/'planning',tmp_path/'planning')
    path=tmp_path/'planning'/'SKILL.md'
    path.write_text(path.read_text(encoding='utf-8')+'\n合成策略版本验证标记',encoding='utf-8')
    changed=load_skill('planning',tmp_path)
    assert changed['sha256']!=original['sha256']
    assert '合成策略版本验证标记' in skill_prompt(changed,'innovation')


@pytest.mark.parametrize('profile',['innovation','classroom','pitch'])
def test_planning_profiles_and_exact_budget(material,profile):
    client=plan_client()
    plan=generate_plan(client,material,'同学',120,'实现',scenario=profile)
    assert sum(r['budget_s'] or 0 for r in plan['slide_plans'])==120
    assert plan['skill']['profile']==profile
    assert plan['slide_plans'][0]['source_refs']==[ref(1,'body',material['slides'][0]['body'])]
    messages=client.complete.call_args.args[0]
    assert load_skill('planning')['spec']['profiles'][profile]['instructions'] in messages[0]['content']
    assert 'private' not in messages[1]['content']
    assert 'SYNTHETIC_SECRET' not in str(plan)


@pytest.mark.parametrize('references', [[],[ref(1,'body','编造原句')],[ref(2,'body','陌生人识别准确率98%。')],
                                      [ref(1,'notes','已实现手势翻页。')],[ref(),ref()]])
def test_planning_rejects_ungrounded_or_duplicate_refs(material,references):
    client=plan_client()
    original=client.complete.side_effect
    def complete(*args,**kwargs):
        result=original(*args,**kwargs)
        result['slide_plans'][0]['source_refs']=references
        return result
    client.complete.side_effect=complete
    with pytest.raises(AssistantError):generate_plan(client,material,'',120,'',scenario='innovation')


def test_hidden_and_blank_page_behavior(material):
    material['slides'][1]['hidden']=True
    result=generate_plan(plan_client(),material,'',100,'',scenario='classroom')
    assert result['slide_plans'][1]['budget_s'] is None
    assert result['slide_plans'][0]['budget_s']==100
    for field in ('title','body','notes','supplement'):material['slides'][0][field]=''
    client=plan_client()
    with pytest.raises(AssistantError,match='空白'):generate_plan(client,material,'',100,'',scenario='classroom')
    client.complete.assert_not_called()


def test_material_snapshot_does_not_mutate_or_leak_and_rejects_oversize(material):
    original=deepcopy(material)
    assert 'private' not in str(material_snapshot(material))
    assert original==material
    material['slides'][0]['body']='x'*60001
    with pytest.raises(AssistantError,match='60000'):material_snapshot(material)


def review_client(material,findings=None):
    return SimpleNamespace(complete=Mock(return_value=dict(summary='以下是合成检查建议。',
        checked_pages=[s['page'] for s in material['slides'] if not s['hidden']],findings=findings or [])))


def finding(kind='evidence',citations=None):
    return dict(kind=kind,priority='medium',reason='当前可读取文字未说明独立测试条件，建议核对。',
                action='补充测试数据划分和指标定义。',citations=[ref()] if citations is None else citations)


def test_material_review_checks_two_locations_and_limits(material):
    f=finding('consistency',[ref(1,'body','训练集准确率98%。'),ref(2,'body','陌生人识别准确率98%。')])
    client=review_client(material,[f])
    output=review_material(client,material)
    assert output['skill']['id']=='material_review'
    assert output['findings']==[f]
    assert any(v['page']==2 for v in output['local_checks'])
    assert '外部事实未核实' in format_material_review(output)
    assert 'private' not in client.complete.call_args.args[0][1]['content']


@pytest.mark.parametrize('f',[finding(citations=[]),finding(citations=[ref(1,'body','虚构')]),
    finding('consistency',[ref()]),finding('consistency',[ref(),ref(1,'body','手势翻页')]),
    {**finding(),'kind':'fraud'},{**finding(),'action':''}])
def test_material_review_rejects_bad_findings(material,f):
    with pytest.raises(AssistantError):review_material(review_client(material,[f]),material)


def test_review_requires_exact_visible_page_scope(material):
    client=review_client(material)
    client.complete.return_value['checked_pages']=[1]
    with pytest.raises(AssistantError,match='范围'):review_material(client,material)
    material['slides'][1]['hidden']=True
    assert review_material(client,material)['checked_pages']==[1]
    client.complete.return_value['findings']=[finding(citations=[ref(2,'body','陌生人识别准确率98%。')])]
    with pytest.raises(AssistantError):review_material(client,material)


def test_review_empty_findings_not_asserted_clean_and_cancel_safe(material):
    result=review_material(review_client(material),material)
    assert '不证明材料没有问题' in format_material_review(result)
    cancel=Event();cancel.set()
    client=review_client(material)
    with pytest.raises(AssistantCancelled):review_material(client,material,cancel=cancel)
    client.complete.assert_not_called()


def defense_client(material,assessment='not_assessed',question='你们如何实现手势翻页？',dimension='method',answer_quote=''):
    result=dict(text='合成评价与提问',citations=[dict(page=1,quote=material['slides'][0]['body'][:100])],weak_questions=[],answer_quote=answer_quote,
                defense_feedback=dict(assessment=assessment,reason='合成教练判断，需人工复核。',question=question,dimension=dimension))
    return SimpleNamespace(complete_turn=Mock(return_value=dict(role='assistant',content=json.dumps(result,ensure_ascii=False))))


def test_defense_rule_based_followup_advance_and_summary(material,tmp_path):
    session=DialogueSession(material,defense_profile='adaptive')
    session.run(defense_client(material),'开始提问','defense')
    assert session.defense_state['answers']==0
    text='我们尚未做独立测试。'
    for index,dimension in [(1,'method'),(2,'method'),(3,'evidence')]:
        session.run(defense_client(material,'partial',f'请说明第{index}项验证细节？',dimension,text),text,'defense')
    assert session.defense_state['dimension_index']==1 and session.defense_state['followups']==0
    session.run(defense_client(material,'adequate','哪些条件下会失效？','limits',text),text,'defense')
    assert session.defense_state['dimension_index']==2
    count=len(session.defense_state['questions'])
    session.run(defense_client(material,'uncertain','','limits',text),'','defense',summarize=True)
    assert len(session.defense_state['questions'])==count
    record=session.record()
    assert record['skill']['id']=='defense' and record['defense_state']['answers']==4
    DialogueStore(tmp_path).save(record)
    assert DialogueStore(tmp_path).records()[0]['skill']==record['skill']


def test_defense_no_summary_without_actual_answer_or_first_evaluation(material):
    s=DialogueSession(material,defense_profile='adaptive')
    client=defense_client(material)
    with pytest.raises(AssistantError,match='回答'):s.run(client,'',summarize=True)
    client.complete_turn.assert_not_called()
    with pytest.raises(AssistantError,match='首次'):s.run(defense_client(material,'adequate'),'开始','defense')
    assert s.defense_state['questions']==[] and not s.turns
    s.run(client,'开始','defense')
    client.complete_turn.reset_mock()
    with pytest.raises(AssistantError,match='回答'):s.run(client,'',summarize=True)
    client.complete_turn.assert_not_called()


@pytest.mark.parametrize('assessment,question,dimension,quote',[
    ('partial','如何准备下轮实验？','limits','真实回答'),
    ('not_assessed','如何准备下轮实验？','method','真实回答'),
    ('partial','你们如何实现手势翻页？','method','真实回答'),
    ('partial','方法是什么？证据是什么？','method','真实回答'),
    ('partial','如何准备下轮实验？','method','伪造回答')])
def test_defense_bad_turn_never_advances_state(material,assessment,question,dimension,quote):
    s=DialogueSession(material,defense_profile='adaptive')
    s.run(defense_client(material),'开始','defense')
    before=deepcopy(s.record())
    with pytest.raises(AssistantError):s.run(defense_client(material,assessment,question,dimension,quote),'真实回答','defense')
    assert s.record()==before


def test_defense_missing_feedback_and_cancel_do_not_save(material):
    s=DialogueSession(material,defense_profile='evidence')
    client=defense_client(material,dimension='evidence')
    result=json.loads(client.complete_turn.return_value['content']);del result['defense_feedback']
    client.complete_turn.return_value['content']=json.dumps(result)
    with pytest.raises(AssistantError):s.run(client,'开始','defense')
    assert not s.turns
    cancel=Event()
    def complete(*args,**kwargs):
        cancel.set();return defense_client(material,dimension='evidence').complete_turn.return_value
    client.complete_turn=complete
    with pytest.raises(AssistantCancelled):s.run(client,'开始','defense',cancel=cancel)
    assert not s.turns and not s.defense_state['questions']


def test_gui_plan_skill_adoption_profile_and_review_stale_guard(tmp_path,qt_application_session):
    from src.gui.presentation_page import PresentationPage
    from src.presentation_store import PresentationStore
    from test_presentation_store import draft
    store=PresentationStore(tmp_path/'library')
    saved=store.save_material(draft())
    page=PresentationPage(store)
    page.scene_selector.set_scene('pitch')
    generated=page._prepare_ai_plan()(plan_client())
    assert generated['skill']['profile']=='pitch'
    assert page._adopt_ai_plan(generated)
    assert page._loaded_plan['skill']['profile']=='pitch'
    assert store.load_plan(page._loaded_plan['id'])['skill']==generated['skill']
    assert page.save_plan()
    assert page._loaded_plan['skill']['profile']=='pitch'
    page.scene_selector.set_scene('innovation')
    assert not page._adopt_ai_plan(generated)
    panel=page.review_panel
    panel._token='old';panel.busy=True;panel._cancel=Event()
    pending_cancel=panel._cancel
    page.supplement_edit.setPlainText('编辑材料，旧检查请求失效')
    assert pending_cancel.is_set() and panel.result is None
    panel._ready('old',{})
    assert panel.result is None and not panel.run_btn.isEnabled()
    page.deleteLater()


def test_gui_defense_profile_switch_invalidates_session(tmp_path,qt_application_session,monkeypatch):
    from src.gui import dialogue_page as module
    from src.presentation_store import PresentationStore
    from src.rehearsal_store import RehearsalStore
    from test_presentation_store import draft
    monkeypatch.setattr(module,'PROJECT_ROOT',tmp_path)
    store=PresentationStore(tmp_path/'library');store.save_material(draft())
    page=module.AssistantDialoguePage(store,RehearsalStore(tmp_path/'history'))
    assert not page.defense_profile_combo.isEnabled()
    page.mode_combo.setCurrentIndex(1)
    assert page.defense_profile_combo.isEnabled()
    page.input.setPlainText('开始提问')
    result=page.prepare()(defense_client(store.materials()[0],dimension='method'))
    assert result['session'].defense_profile=='adaptive'
    page.session=result['session']
    page.defense_profile_combo.setCurrentIndex(1)
    assert page.session is None
    page.deleteLater()


def test_skill_resources_are_in_both_packaging_entries():
    root=Path(__file__).resolve().parents[1]
    for path in (root/'tools/build_exe.py',root/'GesturePPT.spec'):
        assert 'assistant_skills' in path.read_text(encoding='utf-8')


def test_cli_list_and_online_opt_in(material,tmp_path,capsys):
    from src.skills_cli import main
    assert main(['list'])==0
    assert 'material_review' in capsys.readouterr().out
    path=tmp_path/'material.json';path.write_text(json.dumps(material),encoding='utf-8')
    assert main(['review',str(path),'--out',str(tmp_path/'review.json')])==1
    assert not (tmp_path/'review.json').exists()


def test_skill_cli_roundtrip_preserves_metadata(material,tmp_path,monkeypatch):
    import src.skills_cli as cli
    monkeypatch.setattr(cli,'load_api_settings',lambda _:ApiSettings(enabled=True,api_key='fake'))
    monkeypatch.setattr(cli,'ChatClient',lambda _:plan_client())
    path=tmp_path/'material.json';path.write_text(json.dumps(material),encoding='utf-8')
    target=tmp_path/'plan.json'
    assert cli.main(['plan',str(path),'--online','--out',str(target),'--scenario','pitch'])==0
    assert json.loads(target.read_text(encoding='utf-8'))['skill']['profile']=='pitch'
    assert target.with_suffix('.md').exists()
    assert cli.main(['plan',str(path),'--online','--out',str(target)])==1


def test_saved_plan_rechecks_references_when_reloaded(tmp_path):
    from src.presentation_store import PresentationStore
    from test_presentation_store import draft
    store=PresentationStore(tmp_path/'library')
    saved=store.save_material(draft())
    generated=generate_plan(plan_client(),saved,'',60,'',scenario='innovation')
    plan=store.save_plan(saved['material_version_id'],'',60,'',generated['slide_plans'],skill=generated['skill'])
    path=store.root/'plans'/(plan['id']+'.json')
    edited=json.loads(path.read_text(encoding='utf-8'))
    edited['slide_plans'][0]['source_refs'][0]['quote']='篡改的引用'
    path.write_text(json.dumps(edited),encoding='utf-8')
    with pytest.raises(AssistantError,match='引用'):store.load_plan(plan['id'])


def test_three_skills_real_local_http_with_synthetic_credentials(material):
    import threading
    from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
    from src.assistant_api import ChatClient
    calls=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            messages=body['messages'];payload=json.loads(messages[1]['content'])
            calls.append(payload)
            if 'slides' in payload and 'scenario' in payload:
                result=plan_client().complete(messages)
            elif 'checked_pages' in payload:
                result=dict(summary='本机合成HTTP结果',checked_pages=payload['checked_pages'],findings=[finding()])
            else:
                result=json.loads(defense_client(material).complete_turn.return_value['content'])
            data=json.dumps({'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':json.dumps(result,ensure_ascii=False)}}]}).encode('utf-8')
            self.send_response(200);self.end_headers();self.wfile.write(data)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        client=ChatClient(ApiSettings(enabled=True,api_key='SYNTHETIC_SECRET',base_url=f'http://127.0.0.1:{server.server_port}',model='synthetic'))
        plan=generate_plan(client,material,'',120,'',scenario='innovation')
        review=review_material(client,material)
        session=DialogueSession(material,defense_profile='adaptive')
        defense=session.run(client,'开始提问','defense')
        assert [v['skill']['id'] for v in (plan,review,defense)]==['planning','material_review','defense']
        assert client.request_count==3
        assert 'private' not in json.dumps(calls) and 'SYNTHETIC_SECRET' not in json.dumps([plan,review,session.record()])
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)


def test_defense_multiple_proposal_tools_cannot_bypass_three_task_cap(material):
    session=DialogueSession(material,defense_profile='adaptive')
    final=defense_client(material).complete_turn.return_value
    calls=[]
    for i in range(2):
        calls.append(dict(id=f't{i}',type='function',function=dict(name='propose_practice_tasks',
            arguments=json.dumps(dict(tasks=[dict(page=1,text=f'合成练习{i}-{j}') for j in range(2)])))))
    client=SimpleNamespace(complete_turn=Mock(side_effect=[dict(role='assistant',tool_calls=calls),final]))
    with pytest.raises(AssistantError,match='合计最多三项'):session.run(client,'开始','defense')
    assert not session.turns and not session.proposals and not session.defense_state['questions']
