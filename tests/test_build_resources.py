"""构建资源回归：演示稿和离线数据随包，失败不发布资源。"""
import importlib.util
from pathlib import Path


def load_builder():
    p = Path(__file__).resolve().parents[1] / 'tools/build_exe.py'
    spec = importlib.util.spec_from_file_location('test_build_script', p)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_portable_build_copies_required_and_optional_resources(tmp_path, monkeypatch):
    m = load_builder()
    source = tmp_path / 'source'
    source.mkdir()
    for name, data in [('config.json', b'{"theme":"user"}'), ('demo.pptx', b'deck'),
                       ('models/offline/model.onnx', b'model'),
                       ('custom_gestures/circle/sample.csv', b'x,y'),
                       ('logs/app.log', b'private runtime log')]:
        p = source / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    monkeypatch.setattr(m, 'ROOT', source)
    destination = tmp_path / 'portable'
    m.copy_runtime_resources(destination)
    for relative in ['config.json', 'demo.pptx', 'models/offline/model.onnx',
                     'custom_gestures/circle/sample.csv']:
        assert (destination / relative).read_bytes() == (source / relative).read_bytes()
    assert not (destination / 'logs').exists()
    assert (source / 'config.json').read_bytes() == b'{"theme":"user"}'


def test_optional_models_do_not_prevent_basic_build(tmp_path, monkeypatch):
    m = load_builder()
    source = tmp_path / 'source'
    source.mkdir()
    for name in ('config.json', 'demo.pptx'):
        (source / name).write_text('resource')
    monkeypatch.setattr(m, 'ROOT', source)
    m.copy_runtime_resources(tmp_path / 'portable')
    assert (tmp_path / 'portable/demo.pptx').exists()


def test_failed_build_does_not_copy_resources(tmp_path, monkeypatch):
    m = load_builder()
    monkeypatch.setattr(m, 'ROOT', tmp_path)
    calls = []
    monkeypatch.setattr(m.subprocess, 'call', lambda cmd, **kw: calls.append((cmd, kw)) or 7)
    monkeypatch.setattr(m, 'copy_runtime_resources', lambda _: (_ for _ in ()).throw(AssertionError('failed build published')))
    out = tmp_path / 'stage'
    assert m.main(['--dist-dir', str(out)]) == 7
    command, options = calls[0]
    assert command[command.index('--distpath') + 1] == str(out)
    assert options['cwd'] == tmp_path


def test_build_ignores_host_tool_dll_search_path(tmp_path, monkeypatch):
    m = load_builder()
    monkeypatch.setattr(m, 'ROOT', tmp_path)
    monkeypatch.setenv('PATH', 'C:/host/poppler/Library/bin;C:/other/conda')
    monkeypatch.setenv('SystemRoot', 'C:/Windows')
    calls = []
    monkeypatch.setattr(m.subprocess, 'call', lambda cmd, **kw: calls.append((cmd, kw)) or 7)
    assert m.main(['--dist-dir', str(tmp_path / 'stage')]) == 7
    command, options = calls[0]
    path = options['env']['PATH']
    assert 'poppler' not in path and 'other/conda' not in path
    assert str(Path('C:/Windows') / 'System32') in path
    assert str(Path(m.sys.executable).resolve().parent) in path
    assert '--clean' in command  # 不复用包含旧DLL来源的分析缓存

def test_shareable_resources_are_sanitized_without_touching_source(tmp_path, monkeypatch):
    import json
    m = load_builder()
    source = tmp_path / 'source'
    source.mkdir()
    original = dict(theme='dark', camera_index=2, asr=dict(enabled=True, online=dict(api_key='private', access_token='token', endpoint='https://example.test/v1')), nested=[dict(password='pw', client_secret='secret', model_path='C:\\Users\\person\\model', other='/home/person/file')])
    raw = json.dumps(original).encode()
    (source/'config.json').write_bytes(raw)
    (source/'demo.pptx').write_bytes(b'deck')
    for name in ('custom_gestures/private.csv', 'logs/record.json', 'assistant_api.local.json', 'models/offline/model.onnx'):
        p=source/name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b'private')
    monkeypatch.setattr(m, 'ROOT', source)
    destination=tmp_path/'portable'
    m.copy_runtime_resources(destination, shareable=True)
    sanitized=json.loads((destination/'config.json').read_text(encoding='utf-8'))
    assert sanitized['theme']=='dark' and sanitized['camera_index']==2
    assert sanitized['asr']['enabled'] is False
    assert sanitized['asr']['online']==dict(api_key='', access_token='', endpoint='https://example.test/v1')
    assert sanitized['nested']==[dict(password='',client_secret='',model_path='',other='')]
    assert (source/'config.json').read_bytes()==raw
    assert not (destination/'custom_gestures').exists()
    assert not (destination/'logs').exists()
    assert not (destination/'assistant_api.local.json').exists()
    assert (destination/'models/offline/model.onnx').exists()


def test_shareable_archive_uses_sanitized_staging_file(tmp_path, monkeypatch):
    import json
    m=load_builder()
    (tmp_path/'config.json').write_text(json.dumps(dict(api_key='private',asr=dict(enabled=True))))
    (tmp_path/'demo.pptx').write_bytes(b'deck')
    monkeypatch.setattr(m,'ROOT',tmp_path)
    checked=[]
    def build(cmd, **kwargs):
        resource=Path(cmd[cmd.index('--add-data')+1].rsplit(';',1)[0])
        assert resource != tmp_path/'config.json'
        assert resource.name=='config.json'
        data=json.loads(resource.read_text(encoding='utf-8'))
        assert data['api_key']=='' and data['asr']['enabled'] is False
        checked.append(resource)
        return 0
    monkeypatch.setattr(m.subprocess,'call',build)
    assert m.main(['--shareable','--dist-dir',str(tmp_path/'stage')])==0
    assert checked and not checked[0].exists()
    assert json.loads((tmp_path/'config.json').read_text())['api_key']=='private'
