"""Grounded generation, page coverage, deterministic timing, and review evidence."""
from copy import deepcopy
from threading import Event

import pytest


def material(count=3):
    from src.assistant_api import ApiSettings
    return dict(material_id='a'*32, material_version_id='b'*32, name='演讲',
                slides=[dict(page=i, title=f'标题{i}', body=f'正文{i}', notes=f'备注{i}', supplement='', hidden=False, warnings=[])
                        for i in range(1, count+1)])


class FakeClient:
    def __init__(self, outputs=None):
        from src.assistant_api import ApiSettings
        self.settings = ApiSettings(enabled=True, api_key='private-test-key')
        self.outputs = list(outputs or [])
        self.messages = []

    def complete(self, messages, **kwargs):
        self.messages.append(messages)
        if self.outputs:
            return self.outputs.pop(0)
        import json
        payload = json.loads(messages[-1]['content'])
        return {'overview':'先讲问题，再讲方法。', 'slide_plans':[
            dict(page=s['page'], budget_weight=s['page'], key_points=['讲清方法'], script='讲述建议',
                 transition='接下来介绍结果', questions=['方法有什么限制？'], issues=[],
                 source_refs=[dict(page=s['page'],field='body',quote=s['body'][:100])]) for s in payload['slides']]}


def test_generation_batches_have_full_outline_and_exact_total_budget(monkeypatch):
    import src.assistant_service as module
    import json
    monkeypatch.setattr(module, 'BATCH_PAGES', 2)
    client = FakeClient()
    source = material(5)
    original = deepcopy(source)
    result = module.generate_plan(client, source, '老师', 480, '实验')
    assert len(client.messages) == 3
    for messages in client.messages:
        request = json.loads(messages[-1]['content'])
        assert len(request['outline']) == 5
        assert request['audience'] == '老师' and request['focus'] == '实验'
    assert [s['page'] for s in result['slide_plans']] == [1,2,3,4,5]
    assert sum(s['budget_s'] for s in result['slide_plans']) == 480
    assert all(s['budget_s'] >= 1 for s in result['slide_plans'])
    assert source == original and 'private-test-key' not in str(result)


def test_hidden_page_keeps_number_without_spending_budget():
    from src.assistant_service import generate_plan
    source = material()
    source['slides'][1]['hidden'] = True
    result = generate_plan(FakeClient(), source, '', 60, '')
    assert result['slide_plans'][1]['budget_s'] is None
    assert sum(s['budget_s'] or 0 for s in result['slide_plans']) == 60


def test_resaving_a_plan_does_not_drift_page_budgets():
    from src.assistant_service import retime_plan
    rows = [dict(page=i, budget_s=seconds, key_points=[], script='') for i, seconds in enumerate([40,80,360],1)]
    assert retime_plan(rows, 480) == rows
    adjusted = retime_plan(rows, 360)
    assert sum(r['budget_s'] for r in adjusted) == 360
    assert retime_plan(adjusted, 360) == adjusted


@pytest.mark.parametrize('rows', [[], [dict(page=99, budget_weight=1, key_points=[], script='')],
    [dict(page=True, budget_weight=1, key_points=[], script='')],
    [dict(page=1, budget_weight=-1, key_points=[], script='')],
    [dict(page=1, budget_weight=1, key_points='bad', script='')]])
def test_bad_page_coverage_or_schema_rejected(rows):
    from src.assistant_service import generate_plan
    from src.assistant_api import AssistantError
    client = FakeClient([{'overview':'建议', 'slide_plans':rows}])
    with pytest.raises(AssistantError):
        generate_plan(client, material(1), '', 60, '')


def test_all_hidden_or_oversize_input_stops_before_api(monkeypatch):
    import src.assistant_service as module
    from src.assistant_api import AssistantError
    source = material(1)
    source['slides'][0]['hidden'] = True
    client = FakeClient()
    with pytest.raises(AssistantError):
        module.generate_plan(client, source, '', 60, '')
    source['slides'][0]['hidden'] = False
    monkeypatch.setattr(module, 'MAX_INPUT_CHARS', 5)
    with pytest.raises(AssistantError):
        module.generate_plan(client, source, '', 60, '')
    assert client.messages == []


def test_cancel_drops_partial_batches(monkeypatch):
    import src.assistant_service as module
    from src.assistant_api import AssistantCancelled
    monkeypatch.setattr(module, 'BATCH_PAGES', 1)
    cancel = Event()
    client = FakeClient()
    original = client.complete
    def stop(*args, **kwargs):
        value = original(*args, **kwargs)
        cancel.set()
        return value
    client.complete = stop
    with pytest.raises(AssistantCancelled):
        module.generate_plan(client, material(2), '', 60, '', cancel=cancel)
    assert len(client.messages) == 1


def test_generated_plan_metadata_roundtrips_and_export(tmp_path):
    from src.presentation_store import PresentationStore
    from test_presentation_store import draft
    from src.assistant_service import generate_plan, format_plan_md
    store = PresentationStore(tmp_path)
    saved = store.save_material(draft())
    generated = generate_plan(FakeClient(), saved, '老师', 480, '方法')
    plan = store.save_plan(saved['material_version_id'], '老师', 480, '方法',
                          generated['slide_plans'], overview=generated['overview'], generation=generated['generation'])
    assert store.load_plan(plan['id']) == plan
    assert plan['generation']['model'] == 'deepseek-flash'
    assert 'private-test-key' not in str(plan)
    assert '480' in format_plan_md(plan) and '讲述建议' in format_plan_md(plan)


def report():
    return dict(id='c'*32, status='completed', duration_s=200, commands={'SWIPE_LEFT':2},
                command_total=2, rejections=1, page_stay={1:100,2:80}, page_gaps=1, page_seen=True)


def test_review_uses_computed_evidence_without_claiming_speech_content():
    from src.assistant_service import analyse_rehearsal, format_review_md
    import json
    client = FakeClient([{'summary':'下一次可以精简前半段。', 'suggestions':[
        {'page':1, 'advice':'尝试缩短这页讲述。', 'evidence_ids':['page_1']}]}])
    result = analyse_rehearsal(client, report())
    prompt = json.loads(client.messages[0][-1]['content'])
    assert prompt['metrics']['command_total'] == 2
    assert prompt['metrics']['pages'][0]['actual_s'] == 100
    assert prompt['speech_transcript_available'] is False
    assert '漏讲' in client.messages[0][0]['content']
    assert '100' in result['suggestions'][0]['evidence'][0]
    assert 'private-test-key' not in format_review_md(result)


@pytest.mark.parametrize('evidence,page', [(['invented'],1), (['page_1'],2)])
def test_review_rejects_unknown_or_cross_page_evidence(evidence, page):
    from src.assistant_service import analyse_rehearsal
    from src.assistant_api import AssistantError
    client = FakeClient([{'summary':'建议', 'suggestions':[{'page':page, 'advice':'建议', 'evidence_ids':evidence}]}])
    with pytest.raises(AssistantError):
        analyse_rehearsal(client, report())
