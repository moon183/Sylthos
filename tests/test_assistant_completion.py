"""Main-window wiring does not start capture or accept stale advice."""
from types import SimpleNamespace


class Text:
    def __init__(self): self.text=''
    def setText(self,text): self.text=text


def test_review_adoption_uses_fixed_report_context_and_rejects_stale_result():
    from src.gui.fluent_window import FluentMainWindow
    calls=[]
    target=SimpleNamespace(rehearsal_page=SimpleNamespace(_last_report={
        'id':'a'*32,'presentation_context':{'material_version_id':'b'*32}},
        ai_panel=SimpleNamespace(status_label=Text())),
        _save_practice_tasks=lambda context,proposals:calls.append((context,proposals)) or True)
    assert not FluentMainWindow._adopt_practice_review(target,{'rehearsal_id':'c'*32,'suggestions':[]})
    assert not calls
    result={'rehearsal_id':'a'*32,'suggestions':[{'page':1,'advice':'压缩背景','evidence':['事实']}]}
    assert FluentMainWindow._adopt_practice_review(target,result)
    assert calls[0][0]['rehearsal_id']=='a'*32
    assert calls[0][1][0]['text']=='压缩背景'


def test_timed_transcript_only_reaches_active_explicit_opt_in_recorder():
    from src.gui.fluent_window import FluentMainWindow
    captured=[]
    enabled=[False]
    recorder=SimpleNamespace(active=True,on_transcript=lambda segment:captured.append(segment))
    target=SimpleNamespace(_worker=SimpleNamespace(recorder=recorder),_transcript_opt_in_at=0,
        rehearsal_page=SimpleNamespace(capture_transcripts_check=SimpleNamespace(isChecked=lambda:enabled[0])))
    segment={'id':'capture-id','started_at':1000,'ended_at':1001,'text':'最终转写'}
    FluentMainWindow._on_timed_segment(target,segment)
    assert not captured
    enabled[0]=True
    FluentMainWindow._on_timed_segment(target,segment)
    assert captured==[segment]
    recorder.active=False
    FluentMainWindow._on_timed_segment(target,segment)
    assert len(captured)==1


def test_segment_captured_before_opt_in_is_not_collected_after_toggle():
    from src.gui.fluent_window import FluentMainWindow
    captured=[]
    target=SimpleNamespace(_worker=SimpleNamespace(recorder=SimpleNamespace(active=True,on_transcript=captured.append)),
        _transcript_opt_in_at=1001,
        rehearsal_page=SimpleNamespace(capture_transcripts_check=SimpleNamespace(isChecked=lambda:True)))
    FluentMainWindow._on_timed_segment(target,{'id':'old','started_at':1000,'ended_at':1002,'text':'开启前采集'})
    assert captured==[]
    final={'id':'new','started_at':1002,'ended_at':1003,'text':'开启后采集'}
    FluentMainWindow._on_timed_segment(target,final)
    assert captured==[final]


def test_adoption_message_can_describe_tasks_instead_of_a_plan():
    from src.gui.assistant_panel import AssistantPanel
    status=Text()
    target=SimpleNamespace(result={'suggestions':[]},adopt=lambda result:True,busy=False,
        status_label=status,adopt_success_text='已保存为练习任务。')
    assert AssistantPanel.adopt_result(target)
    assert status.text=='已保存为练习任务。'
