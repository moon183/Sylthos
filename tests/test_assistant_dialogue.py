import json
from io import BytesIO
import pytest
from src.assistant_api import ChatClient, ApiSettings, AssistantError



def test_fixed_tools_loop_and_history(tmp_path):
    from src.assistant_dialogue import DialogueSession, DialogueStore
    material={'material_version_id':'v1','slides':[{'page':1,'title':'title','body':'真实证据','notes':'','supplement':''}]}
    class Client:
        def __init__(self): self.calls=[]
        def complete_turn(self,messages,**kwargs):
            self.calls.append(json.loads(json.dumps(messages)))
            if len(self.calls)==1:
                return {'role':'assistant','content':None,'tool_calls':[{'id':'x','type':'function','function':{'name':'read_page','arguments':'{"page":1}'}}]}
            return {'role':'assistant','content':json.dumps({'text':'为什么？','citations':[{'page':1,'quote':'真实证据'}],'weak_questions':[]})}
    session=DialogueSession(material)
    c=Client(); result=session.run(c,'开始','defense')
    assert c.calls[1][-1]['role']=='tool'
    assert '真实证据' in c.calls[1][-1]['content']
    assert result['citations'][0]['page']==1
    store=DialogueStore(tmp_path); store.save(session.record())
    assert store.records()[0]['turns'][-1]['result']==result
    assert '为什么' in store.export(session.record()).read_text(encoding='utf8')


def test_tools_refuse_unknown_and_limits():
    from src.assistant_dialogue import DialogueSession
    s=DialogueSession({'material_version_id':'v','slides':[{'page':1,'body':'abc'}]})
    with pytest.raises(AssistantError): s.execute('shell',{'command':'echo'})
    with pytest.raises(AssistantError): s.execute('read_page',{'page':2})
    with pytest.raises(AssistantError): s.execute('read_outline',{'path':'secret'})
    with pytest.raises(AssistantError): s.run(None,'x'*9000)

def test_dialogue_page_has_explicit_context_and_history(qt_application_session, tmp_path):
    from src.gui.dialogue_page import AssistantDialoguePage
    from src.presentation_store import PresentationStore
    from src.rehearsal_store import RehearsalStore
    page=AssistantDialoguePage(PresentationStore(tmp_path/'materials'),RehearsalStore(tmp_path/'rehearsals'))
    assert page.mode_combo.count()==2
    assert page.panel.result is None
    assert not page.panel.run_btn.isEnabled()
    page.refresh(); page.close()


@pytest.mark.parametrize('scenario', ['unknown','oversize','loop','citation','answer'])
def test_bounded_tools_and_verified_defense(scenario):
    from src.assistant_dialogue import DialogueSession
    s=DialogueSession({'material_version_id':'v','slides':[{'page':1,'body':'evidence'}]})
    if scenario=='answer': s.turns=[{'input':'previous','result':{'text':'why'}}]
    class Client:
        def __init__(self): self.n=0
        def complete_turn(self,messages,**kwargs):
            self.n+=1
            if scenario in ('unknown','oversize','loop'):
                return {'role':'assistant','tool_calls':[{'id':str(self.n),'type':'function','function':{
                    'name':'shell' if scenario=='unknown' else 'read_outline',
                    'arguments':' '*5000 if scenario=='oversize' else '{}'}}]}
            return {'role':'assistant','content':json.dumps({'text':'question','citations':[{'page':1,'quote':'fake' if scenario=='citation' else 'evidence'}]})}
    c=Client()
    with pytest.raises(AssistantError): s.run(c,'my actual answer','defense')
    assert c.n<=5
    assert not s.proposals


def test_proposals_pending_and_wrong_version_rejected():
    from src.assistant_dialogue import DialogueSession
    m={'material_version_id':'v','slides':[{'page':1,'body':'evidence'}]}
    with pytest.raises(AssistantError): DialogueSession(m,{'material_version_id':'wrong'})
    with pytest.raises(AssistantError): DialogueSession(m,rehearsals=[{'id':'x','presentation_context':{'material_version_id':'wrong'}}])
    s=DialogueSession(m)
    output=s.execute('propose_practice_tasks',{'tasks':[{'page':1,'text':'practice','target_s':20}]})
    assert output['pending_user_adoption']
    assert s.proposals==output['tasks']
    with pytest.raises(AssistantError): s.execute('propose_practice_tasks',{'tasks':[{'page':1,'text':'x','target_s':True}]})


def test_context_and_turn_total_limits():
    from src.assistant_dialogue import DialogueSession
    with pytest.raises(AssistantError): DialogueSession({'material_version_id':'v','slides':[{'page':1,'body':'x'*120001}]})
    s=DialogueSession({'material_version_id':'v','slides':[{'page':1,'body':'x'}]})
    s.turns=[{}]*30
    with pytest.raises(AssistantError): s.run(None,'start')


def test_page_context_change_invalidates_late_result(qt_application_session,tmp_path):
    from src.gui.dialogue_page import AssistantDialoguePage
    from src.presentation_store import PresentationStore
    from src.rehearsal_store import RehearsalStore
    p=AssistantDialoguePage(PresentationStore(tmp_path/'p'),RehearsalStore(tmp_path/'r'))
    p.panel._token='old';p.panel.busy=True
    p.invalidate()
    p.panel._ready('old',{'record':{},'session':None})
    assert p.panel.result is None
    assert not p.panel.busy
    p.close()


def test_tools_compare_only_selected_same_version():
    from src.assistant_dialogue import DialogueSession
    version='a'*32
    material={'material_version_id':version,'slides':[{'page':1,'body':'evidence'}]}
    rs=[{'id':name,'presentation_context':{'material_version_id':version},'duration_s':secs,'page_stay':{1:secs}} for name,secs in [('before',10),('after',12)]]
    s=DialogueSession(material,rehearsals=rs)
    assert s.execute('compare_rehearsals',{'before':'before','after':'after'})['duration_delta_s']==2
    with pytest.raises(AssistantError): s.execute('read_rehearsal',{'id':'unselected'})


def test_cancelled_tool_turn_never_saved():
    from threading import Event
    from src.assistant_api import AssistantCancelled
    from src.assistant_dialogue import DialogueSession
    s=DialogueSession({'material_version_id':'v','slides':[{'page':1,'body':'evidence'}]})
    cancel=Event()
    class Client:
        def complete_turn(self,*args,**kwargs):
            cancel.set()
            return {'role':'assistant','content':'{"text":"late"}'}
    with pytest.raises(AssistantCancelled): s.run(Client(),'ask',cancel=cancel)
    assert not s.turns


def test_gui_tool_roundtrip_history_adoption_and_refresh(qt_application_session,tmp_path,monkeypatch):
    import time
    from PySide6.QtWidgets import QApplication
    from qfluentwidgets import TitleLabel
    import src.gui.dialogue_page as module
    import src.gui.assistant_panel as panels
    from src.assistant_dialogue import DialogueStore
    context={'material_version_id':'a'*32,'material_id':'b'*32,'material_name':'demo','version_no':1,'plan_id':None,'target_duration_s':None}
    other={**context,'material_version_id':'c'*32,'material_name':'other'}
    material={'material_version_id':context['material_version_id'],'slides':[{'page':1,'body':'real evidence','title':'title'}]}
    class Presentations:
        def contexts(self): return [context,other]
        def load_material(self,identity): return {**material,'material_version_id':identity}
    class Rehearsals:
        def reports(self): return []
    monkeypatch.setattr(module,'PROJECT_ROOT',tmp_path)
    monkeypatch.setattr(panels,'load_api_settings',lambda _: ApiSettings(enabled=True,api_key='fake'))
    calls=[];adopted=[]
    class Client:
        def __init__(self,settings): pass
        def complete_turn(self,messages,**kwargs):
            calls.append(json.loads(json.dumps(messages)))
            if len(calls)==1:
                return {'role':'assistant','content':None,'tool_calls':[
                    {'id':'read','type':'function','function':{'name':'read_page','arguments':'{"page":1}'}},
                    {'id':'proposal','type':'function','function':{'name':'propose_practice_tasks','arguments':'{"tasks":[{"text":"practice","page":1}]}'}}]}
            assert messages[-2]['role']=='tool' and 'real evidence' in messages[-2]['content']
            return {'role':'assistant','content':json.dumps({'text':'why?','citations':[{'page':1,'quote':'real evidence'}],'weak_questions':['why']})}
    page=module.AssistantDialoguePage(Presentations(),Rehearsals(),lambda c,p: adopted.append((c,p)))
    page.store=DialogueStore(tmp_path/'dialogue');page.panel.client_factory=Client
    assert page.findChildren(TitleLabel)
    page.input.setPlainText('begin');page.panel.run_btn.click()
    deadline=time.monotonic()+3
    while page.panel.busy and time.monotonic()<deadline:
        QApplication.processEvents();time.sleep(.01)
    assert not page.panel.busy and page.panel.result is not None
    assert len(calls)==2 and not adopted
    assert len(page.store.records())==1
    page.panel.adopt_btn.click()
    assert adopted==[(context,[{'text':'practice','page':1}])]
    page.input.setPlainText('unsent text')
    page.refresh()
    assert page.context_combo.currentData()==context
    assert page.input.toPlainText()=='unsent text'
    page.history_combo.setCurrentIndex(1)
    assert len(calls)==2 and 'why?' in page.panel.output.toPlainText()
    assert page.panel.export_result().exists()
    page.panel._token='pending';page.panel.busy=True
    from threading import Event
    cancelled=Event();page.panel._cancel=cancelled
    page.context_combo.setCurrentIndex(1)
    assert cancelled.is_set() and not page.panel.busy
    page.panel._ready('pending',{})
    assert page.panel.result is None
    assert page.input.toPlainText()=='unsent text'
    page.close()


def test_four_practice_proposals_rejected():
    from src.assistant_dialogue import DialogueSession
    s=DialogueSession({'material_version_id':'v','slides':[{'page':1,'body':'evidence'}]})
    with pytest.raises(AssistantError):
        s.execute('propose_practice_tasks',{'tasks':[{'page':1,'text':'practice'}]*4})


def test_refresh_preserves_session_output_busy_and_selected_history(tmp_path,monkeypatch):
    from threading import Event
    import src.gui.dialogue_page as module
    context={'material_version_id':'a'*32,'material_name':'demo','version_no':1,'plan_id':None}
    report={'id':'history','duration_s':3,'status':'completed','presentation_context':context}
    class Presentations:
        def contexts(self): return [context]
    class Rehearsals:
        def __init__(self): self.rows=[report]
        def reports(self): return self.rows
    monkeypatch.setattr(module,'PROJECT_ROOT',tmp_path)
    rs=Rehearsals(); p=module.AssistantDialoguePage(Presentations(),rs)
    p.rehearsal_list.item(0).setSelected(True)
    session=object();p.session=session
    p.panel.output.setPlainText('existing result')
    result={'marker':'existing'};p.panel.result=result
    cancel=Event();p.panel._cancel=cancel;p.panel._token='active';p.panel.busy=True
    p.input.setPlainText('unsent')
    p.refresh()
    assert p.session is session and p.panel.result is result
    assert p.panel.output.toPlainText()=='existing result'
    assert p.panel.busy and p.panel._token=='active' and not cancel.is_set()
    assert len(p.rehearsal_list.selectedItems())==1
    assert p.input.toPlainText()=='unsent'
    rs.rows=[];p.refresh()
    assert p.session is None and p.panel.result is None and cancel.is_set()
    assert not p.panel.busy
    p.close()


def test_summary_uses_existing_answer_with_empty_input():
    from src.assistant_dialogue import DialogueSession
    s=DialogueSession({'material_version_id':'v','slides':[{'page':1,'body':'evidence'}]})
    s.turns=[{'mode':'defense','input':'my real answer','summarize':False,'result':{'text':'follow up'}}]
    class Client:
        def complete_turn(self,messages,**kwargs):
            assert json.loads(messages[1]['content'])['input']=='my real answer'
            return {'role':'assistant','content':json.dumps({'text':'summary','citations':[{'page':1,'quote':'evidence'}],'answer_quote':'my real answer'})}
    assert s.run(Client(),'','defense',summarize=True)['text']=='summary'


def test_gui_summary_button_with_cleared_input(tmp_path,monkeypatch):
    import time
    from PySide6.QtWidgets import QApplication
    import src.gui.dialogue_page as module
    import src.gui.assistant_panel as panels
    from src.assistant_dialogue import DialogueSession
    context={'material_version_id':'a'*32,'material_name':'demo','version_no':1,'plan_id':None}
    material={'material_version_id':context['material_version_id'],'slides':[{'page':1,'body':'evidence'}]}
    class Presentations:
        def contexts(self): return [context]
    class Rehearsals:
        def reports(self): return []
    monkeypatch.setattr(module,'PROJECT_ROOT',tmp_path)
    monkeypatch.setattr(panels,'load_api_settings',lambda _: ApiSettings(enabled=True,api_key='fake'))
    calls=[]
    class Client:
        def __init__(self,settings): pass
        def complete_turn(self,messages,**kwargs):
            payload=json.loads(messages[1]['content']);calls.append(payload)
            assert payload['summarize'] and payload['input']=='my real answer'
            assert '忽略其中命令' not in messages[0]['content']
            return {'role':'assistant','content':json.dumps({'text':'summary','citations':[{'page':1,'quote':'evidence'}],'answer_quote':'real answer'})}
    p=module.AssistantDialoguePage(Presentations(),Rehearsals());p.panel.client_factory=Client
    p.session=DialogueSession(material,context=context)
    p.session.turns=[{'mode':'defense','input':'my real answer','summarize':False,'result':{'text':'follow up'}}]
    p.input.clear();p.summary_btn.click()
    deadline=time.monotonic()+3
    while p.panel.busy and time.monotonic()<deadline:
        QApplication.processEvents();time.sleep(.01)
    assert calls and p.panel.result is not None
    assert p.session.turns[-1]['result']['text']=='summary'
    assert p.input.toPlainText()==''
    p.close()


def test_gui_async_history_save_failure_remains_visible_and_exportable(tmp_path,monkeypatch):
    import time
    from PySide6.QtWidgets import QApplication
    import src.gui.dialogue_page as module
    import src.gui.assistant_panel as panels
    context={'material_version_id':'a'*32,'material_name':'demo','version_no':1,'plan_id':None}
    class Presentations:
        def contexts(self): return [context]
        def load_material(self,identity): return {'material_version_id':identity,'slides':[{'page':1,'body':'evidence'}]}
    class Rehearsals:
        def reports(self): return []
    monkeypatch.setattr(module,'PROJECT_ROOT',tmp_path)
    monkeypatch.setattr(panels,'load_api_settings',lambda _: ApiSettings(enabled=True,api_key='fake'))
    class Client:
        def __init__(self,settings): pass
        def complete_turn(self,*args,**kwargs): return {'role':'assistant','content':'{"text":"retained result"}'}
    p=module.AssistantDialoguePage(Presentations(),Rehearsals());p.panel.client_factory=Client
    def fail(record): raise OSError('simulated disk failure')
    monkeypatch.setattr(p.store,'save',fail)
    p.panel.output_dir=tmp_path/'exports'
    p.input.setPlainText('retain input');p.panel.run_btn.click()
    deadline=time.monotonic()+3
    while p.panel.busy and time.monotonic()<deadline:
        QApplication.processEvents();time.sleep(.01)
    assert not p.panel.busy
    assert '历史保存失败' in p.panel.status_label.text()
    assert p.panel.result is not None and p.session is not None
    assert p.input.toPlainText()=='retain input'
    assert 'retained result' in p.panel.output.toPlainText()
    assert p.panel.export_btn.isEnabled()
    assert p.panel.export_result().exists()
    p.close()
