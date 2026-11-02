"""Chat Completions transport contract; no real provider or credentials."""
from io import BytesIO
import json
from threading import Event
from urllib.error import HTTPError, URLError

import pytest


def response(content='{"ok":true}', finish='stop'):
    return BytesIO(json.dumps({'choices': [{'finish_reason': finish, 'message': {'content': content}}]}).encode())


def settings(**kwargs):
    from src.assistant_api import ApiSettings
    return ApiSettings(**{'enabled': True, 'api_key': 'fictional-test-key', **kwargs})


def test_settings_roundtrip_atomic_defaults_and_secret_not_in_repr(tmp_path):
    from src.assistant_api import ApiSettings, load_api_settings, save_api_settings
    path = tmp_path / 'assistant_api.local.json'
    assert not load_api_settings(path).enabled
    assert load_api_settings(path).api_key == ''
    configured = settings(base_url='https://example.com/v1', model='my-model')
    save_api_settings(configured, path)
    assert load_api_settings(path) == configured
    assert 'fictional-test-key' not in repr(configured)
    assert not list(tmp_path.glob('*.tmp'))
    assert not ApiSettings().enabled


@pytest.mark.parametrize('base,expected', [('https://example.com', 'https://example.com/chat/completions'),
    ('https://example.com/v1/', 'https://example.com/v1/chat/completions'),
    ('https://example.com/v1/chat/completions', 'https://example.com/v1/chat/completions')])
def test_endpoint_normalization(base, expected):
    assert settings(base_url=base).endpoint == expected


def test_post_payload_bearer_json_and_non_thinking_mode():
    from src.assistant_api import ChatClient
    captured = {}
    def opened(request, timeout):
        captured.update(url=request.full_url, method=request.method, headers=dict(request.header_items()),
                        body=json.loads(request.data), timeout=timeout)
        return response()
    result = ChatClient(settings(), open_url=opened).complete([{'role':'user', 'content':'返回 json'}])
    assert result == {'ok': True}
    assert captured['method'] == 'POST'
    assert captured['headers']['Authorization'] == 'Bearer fictional-test-key'
    assert captured['body']['response_format'] == {'type':'json_object'}
    assert captured['body']['thinking'] == {'type':'disabled'}
    assert captured['body']['stream'] is False and captured['timeout'] == 120


@pytest.mark.parametrize('changes', [{'enabled':False}, {'api_key':''}, {'model':''},
    {'base_url':'file:///private'}, {'base_url':'https://user:key@example.com'},
    {'base_url':'https://example.com?key=secret'}, {'api_key':'bad\r\nheader'}])
def test_bad_or_disabled_config_never_sends(changes):
    from src.assistant_api import AssistantError, ChatClient
    sent = []
    with pytest.raises(AssistantError):
        ChatClient(settings(**changes), open_url=lambda *a, **k: sent.append(a)).complete([])
    assert sent == []


@pytest.mark.parametrize('code', [301, 302, 400, 401, 402, 403, 404, 429, 500])
def test_http_errors_are_bounded_and_do_not_expose_secrets(code, caplog):
    from src.assistant_api import AssistantError, ChatClient
    calls = []
    def failed(request, timeout):
        calls.append(request)
        raise HTTPError(request.full_url, code, 'fictional-test-key PRIVATE MATERIAL', {}, BytesIO(b'secret'))
    with pytest.raises(AssistantError) as error:
        ChatClient(settings(), open_url=failed).complete([])
    assert len(calls) == (2 if code in (429, 500) else 1)
    assert 'fictional-test-key' not in str(error.value) + caplog.text
    assert 'PRIVATE MATERIAL' not in str(error.value) + caplog.text


@pytest.mark.parametrize('payload', [b'not-json', b'{}',
    b'{"choices":[null]}',
    b'{"choices":[{"finish_reason":"length","message":{"content":"{}"}}]}',
    b'{"choices":[{"finish_reason":"stop","message":{"content":""}}]}'])
def test_invalid_or_truncated_response_rejected(payload):
    from src.assistant_api import AssistantError, ChatClient
    with pytest.raises(AssistantError):
        ChatClient(settings(), open_url=lambda *a, **k: BytesIO(payload)).complete([])


def test_cancelled_before_send_and_after_response():
    from src.assistant_api import AssistantCancelled, ChatClient
    cancelled = Event()
    cancelled.set()
    sent = []
    with pytest.raises(AssistantCancelled):
        ChatClient(settings(), open_url=lambda *a, **k: sent.append(a)).complete([], cancel=cancelled)
    assert not sent
    cancelled.clear()
    def opened(*args, **kwargs):
        cancelled.set()
        return response()
    with pytest.raises(AssistantCancelled):
        ChatClient(settings(), open_url=opened).complete([], cancel=cancelled)


def test_connection_test_sends_only_minimal_text_not_material():
    from src.assistant_api import ChatClient
    bodies = []
    def opened(request, timeout):
        bodies.append(json.loads(request.data))
        return response('OK')
    assert ChatClient(settings(), open_url=opened).test_connection() == '连接成功，接口已返回正文。'
    assert bodies[0]['max_tokens'] == 16 and 'response_format' not in bodies[0]


def test_connection_test_temporarily_disables_thinking():
    from src.assistant_api import ChatClient
    bodies = []
    configured = settings(thinking=True)
    def opened(request, timeout):
        bodies.append(json.loads(request.data))
        return response('OK')
    ChatClient(configured, open_url=opened).test_connection()
    assert bodies[0]['thinking'] == {'type':'disabled'}
    assert configured.thinking is True


def test_bad_settings_json_does_not_silently_replace_file(tmp_path):
    from src.assistant_api import AssistantError, load_api_settings
    path = tmp_path / 'local.json'
    path.write_text('broken', encoding='utf8')
    with pytest.raises(AssistantError):
        load_api_settings(path)
    assert path.read_text(encoding='utf8') == 'broken'


def test_invalid_output_limit_reports_parameter_instead_of_json_error(tmp_path):
    from src.assistant_api import AssistantError, load_api_settings
    path = tmp_path / 'api.json'
    path.write_text(json.dumps({'enabled':True, 'api_key':'private-test-key', 'max_tokens':10000000000}), encoding='utf8')
    with pytest.raises(AssistantError, match='max_tokens.*393216') as error:
        load_api_settings(path)
    assert 'private-test-key' not in str(error.value)
    assert json.loads(path.read_text(encoding='utf8'))['max_tokens'] == 10000000000


@pytest.mark.parametrize('budget', [None, 65536, 131072, 393216])
def test_output_budget_uses_model_limits_not_old_app_cap(budget):
    configured = settings(max_tokens=budget)
    configured.validate(require_ready=True)


def test_omitting_output_budget_uses_provider_default():
    from src.assistant_api import ChatClient
    bodies = []
    def opened(request, timeout):
        bodies.append(json.loads(request.data))
        return response()
    ChatClient(settings(max_tokens=None), open_url=opened).complete([])
    assert 'max_tokens' not in bodies[0]


def test_large_valid_completion_is_not_rejected_at_two_megabytes():
    from src.assistant_api import ChatClient
    text = 'x' * (2 * 1024 * 1024 + 100)
    result = ChatClient(settings(), open_url=lambda *a, **k: response(text)).complete([], json_result=False)
    assert result == text


def test_json_syntax_error_reports_location_without_echoing_secret(tmp_path):
    from src.assistant_api import AssistantError, load_api_settings
    path = tmp_path / 'api.json'
    path.write_text('{\n"api_key": "private-test-key",\n}', encoding='utf8')
    with pytest.raises(AssistantError, match='第.*行') as error:
        load_api_settings(path)
    assert 'private-test-key' not in str(error.value)


def test_redirect_handler_refuses_authorization_forwarding():
    from src.assistant_api import NoRedirect
    from urllib.request import Request
    assert NoRedirect().redirect_request(Request('https://example.com'), None, 302, 'moved', {}, 'https://other.example') is None


@pytest.mark.parametrize('timeout', [120, 300, 600])
def test_long_generation_timeout_supported(timeout):
    settings(timeout_s=timeout).validate(require_ready=True)


@pytest.mark.parametrize('wrapped', [False, True])
def test_timeout_explains_adjustment_without_retry_or_secret(wrapped):
    from src.assistant_api import ChatClient, AssistantError
    calls = []
    def opened(*args, **kwargs):
        calls.append(1)
        error = TimeoutError('private-test-key')
        raise URLError(error) if wrapped else error
    with pytest.raises(AssistantError, match='120.*秒') as caught:
        ChatClient(settings(timeout_s=120), open_url=opened).complete([])
    assert 'API 设置' in str(caught.value)
    assert 'private-test-key' not in str(caught.value)
    assert calls == [1]


def test_complete_turn_preserves_tools_and_reasoning():
    from src.assistant_api import ChatClient, ApiSettings
    calls=[]
    message={'role':'assistant','content':None,'reasoning_content':'reason','tool_calls':[{'id':'c1','type':'function','function':{'name':'read_outline','arguments':'{}'}}]}
    def opened(req,timeout):
        calls.append(json.loads(req.data))
        return BytesIO(json.dumps({'choices':[{'finish_reason':'tool_calls','message':message}]}).encode())
    client=ChatClient(ApiSettings(enabled=True,api_key='fake'),open_url=opened)
    assert client.complete_turn([{'role':'user','content':'ask'}],tools=[{'type':'function'}])==message
    assert calls[0]['tools']==[{'type':'function'}]
    assert 'response_format' not in calls[0]
