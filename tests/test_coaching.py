import pytest
from src.coaching import PracticeStore, compare_rehearsals, format_comparison_md

V = 'a' * 32

def report(identity, pages, target=60, version=V):
    return dict(id=identity, presentation_context=dict(material_version_id=version, target_duration_s=target), duration_s=sum(pages.values()), page_stay=pages)

def test_restart_and_status(tmp_path):
    store = PracticeStore(tmp_path)
    task = store.add(dict(material_version_id=V, rehearsal_id='b'*32), '../练习第2页', 2, 30)
    store.set_status(task['id'], 'done')
    saved = PracticeStore(tmp_path).list_tasks(V)[0]
    assert saved['status'] == 'done'
    assert saved['context']['rehearsal_id'] == 'b'*32
    assert saved['page'] == 2
    assert len(list(tmp_path.glob('*.json'))) == 1

@pytest.mark.parametrize('kwargs', [dict(text=''), dict(text='x', page=0), dict(text='x', target_s=float('nan')), dict(text='x', page=True)])
def test_invalid(tmp_path, kwargs):
    with pytest.raises(ValueError):
        PracticeStore(tmp_path).add({'material_version_id':V}, **kwargs)

def test_corrupt_and_path_guard(tmp_path):
    (tmp_path/'broken.json').write_text('{}')
    store = PracticeStore(tmp_path)
    assert store.list_tasks() == []
    assert store.errors
    with pytest.raises(ValueError):
        store.set_status('../escape', 'done')

def test_compare_requires_same_version():
    for version in (None, 'b'*32):
        with pytest.raises(ValueError):
            compare_rehearsals(report('first', {1:10}), report('next', {1:8}, version=version))

def test_compare_unknown_and_target_change():
    result = compare_rehearsals(report('chosen first', {1:40, 2:20}), report('chosen next', {1:30, 3:8}, 80))
    assert result['before_id'] == 'chosen first'
    assert result['target_changed']
    assert result['pages'][1]['after_s'] is None
    assert result['pages'][1]['delta_s'] is None
    assert result['pages'][0]['delta_s'] == -10
    assert '不代表' in format_comparison_md(result)

def test_failed_replace_keeps_previous_task(tmp_path, monkeypatch):
    import src.coaching as coaching
    store = PracticeStore(tmp_path)
    task = store.add({'material_version_id':V}, '保留旧状态')
    def fail(*args):
        raise OSError('模拟磁盘失败')
    monkeypatch.setattr(coaching.os, 'replace', fail)
    with pytest.raises(OSError):
        store.set_status(task['id'], 'done')
    assert store.list_tasks()[0]['status'] == 'pending'
    assert not list(tmp_path.glob('*.tmp'))

def test_invalid_page_evidence_rejected():
    with pytest.raises(ValueError):
        compare_rehearsals(report('first', {1:10}), report('next', {'no page':8}))

def test_adoption_is_idempotent_and_retains_done(tmp_path):
    store = PracticeStore(tmp_path)
    context = dict(material_version_id=V, rehearsal_id='b'*32, material_name='Original')
    task = store.add(context, 'practice', 1, 30)
    store.set_status(task['id'], 'done')
    context['material_name'] = 'display changed'
    same = PracticeStore(tmp_path).add(context, 'practice', 1, 30)
    assert same['id'] == task['id']
    assert same['status'] == 'done'
    assert len(store.list_tasks()) == 1
    assert store.add(dict(context, rehearsal_id='c'*32), 'practice', 1, 30)['id'] != task['id']


def test_retry_after_successful_write_error_does_not_duplicate(tmp_path, monkeypatch):
    import src.coaching as coaching
    store = PracticeStore(tmp_path)
    replace = coaching.os.replace
    def replaced_but_reported_error(*args):
        replace(*args)
        raise OSError('simulated lost success response')
    with monkeypatch.context() as patch:
        patch.setattr(coaching.os, 'replace', replaced_but_reported_error)
        with pytest.raises(OSError):
            store.add({'material_version_id': V, 'rehearsal_id':'b'*32}, 'practice', 1, 30)
    store.add({'material_version_id': V, 'rehearsal_id':'b'*32}, 'practice', 1, 30)
    assert len(store.list_tasks()) == 1

def test_adoption_identity_includes_plan_source(tmp_path):
    store=PracticeStore(tmp_path)
    context=dict(material_version_id=V, rehearsal_id='b'*32, plan_id='c'*32)
    first=store.add(context, 'practice', 1, 30)
    other=store.add(dict(context, plan_id='d'*32), 'practice', 1, 30)
    assert first['id'] != other['id']
    assert store.add(context, 'practice', 1, 30)['id']==first['id']
