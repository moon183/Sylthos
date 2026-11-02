"""Hermetic full workflow: real loopback HTTP, fictional key, synthetic rehearsal.

Never loads the user's API settings, starts a device, or contacts a supplier.
"""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread
from unittest.mock import patch
from uuid import uuid4

from src.assistant_api import ApiSettings, ChatClient
from src.assistant_service import generate_plan, analyse_rehearsal, format_plan_md
from src.assistant_dialogue import DialogueSession, DialogueStore
from src.coaching import PracticeStore, compare_rehearsals, format_comparison_md
from src.presentation_materials import read_pptx
from src.presentation_store import PresentationStore
from src.rehearsal import RehearsalRecorder, format_report_md
from src.rehearsal_store import RehearsalStore
from src.speech_review import analyse_speech, format_speech_review_md, local_pacing_hint


def main():
    output = ROOT / 'build' / 'complete_acceptance' / uuid4().hex
    library = PresentationStore(output / 'library')
    material = library.save_material(read_pptx(ROOT / 'demo.pptx'))
    quote = material['slides'][0]['title']
    calls = []
    segment = dict(id='synthetic-final', started_at=1002., ended_at=1007., text='这是合成转写原句，说明实现依据。')

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass

        def do_POST(self):
            assert self.path == '/v1/chat/completions'
            assert self.headers['Authorization'] == 'Bearer fictional-local-validation'
            request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            messages = request['messages']
            finish = 'stop'
            if request.get('tools'):
                info = json.loads(messages[1]['content'])
                if messages[-1]['role'] != 'tool':
                    message = dict(role='assistant', content=None, tool_calls=[
                        dict(id='page-call', type='function', function=dict(name='read_page', arguments='{"page":1}')),
                        dict(id='task-call', type='function', function=dict(name='propose_practice_tasks', arguments=json.dumps(
                            {'tasks':[dict(page=1,text='合成练习：精简开场',target_s=15)]},ensure_ascii=False)))])
                    finish = 'tool_calls'
                    calls.append('tool_request')
                else:
                    assert any(m['role']=='tool' and m['tool_call_id']=='page-call' for m in messages)
                    value = dict(text='本机模拟：请解释这一页的实现依据。', citations=[dict(page=1,quote=quote)],
                                 answer_quote=info['input'], weak_questions=['合成薄弱问题：如何验证结果？'])
                    message = dict(role='assistant',content=json.dumps(value,ensure_ascii=False))
                    calls.append('defense' if info['mode']=='defense' else 'tool_answer')
            elif '请只回复 OK' in messages[-1]['content']:
                message = dict(role='assistant',content='OK');calls.append('connection')
            else:
                data = json.loads(messages[-1]['content'])
                if 'outline' in data:
                    value = dict(overview='本机模拟讲述思路。',slide_plans=[dict(page=s['page'],budget_weight=1,
                        key_points=['合成重点'],script='合成建议讲稿。',transition='接下来介绍实现。',questions=['有哪些依据？'],issues=[])
                        for s in data['slides']]);calls.append('plan')
                elif 'transcripts' in data:
                    source = data['transcripts'][0]
                    value = dict(summary='合成建议。',findings=[dict(kind='coverage',segment_id=source['id'],
                        quote=source['text'],pages=source['pages'],comment='合成建议：核对本句是否说明了实现依据。')],limitations=[])
                    calls.append('speech_review')
                else:
                    value = dict(summary='合成统计建议。',suggestions=[dict(page=1,advice='合成练习：精简开场',evidence_ids=['page_1'])])
                    calls.append('statistical_review')
                message = dict(role='assistant',content=json.dumps(value,ensure_ascii=False))
            raw = json.dumps({'choices':[dict(finish_reason=finish,message=message)]},ensure_ascii=False).encode()
            self.send_response(200);self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)

    server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread = Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        client = ChatClient(ApiSettings(enabled=True,api_key='fictional-local-validation',model='local-validation',
                                       base_url=f'http://127.0.0.1:{server.server_port}/v1'))
        client.test_connection()
        generated = generate_plan(client,material,'合成受众',480,'验证完整流程')
        plan = library.save_plan(material['material_version_id'],generated['audience'],480,generated['focus'],
                                 generated['slide_plans'],overview=generated['overview'],generation=generated['generation'])
        context = next(c for c in library.contexts() if c['plan_id']==plan['id'])
        history = RehearsalStore(output/'rehearsals')
        recorder = RehearsalRecorder(history)
        with patch('src.rehearsal.time.time',return_value=1000.) as clock:
            recorder.start(context);recorder.on_page(1,1000.)
            recorder.on_page(2,1006.);clock.return_value=1008.
            recorder.on_page(2,1008.)
            assert recorder.on_transcript(segment)
            recorder.on_page(None,1009.);recorder.on_page(1,1010.)
            recorder.on_command('SWIPE_LEFT',1010.)
            clock.return_value=1020.;before=recorder.stop()
            assert before['transcripts'][0]['alignment']=='multiple_pages'
            clock.return_value=1100.;recorder.start(context);recorder.on_page(1,1100.)
            clock.return_value=1110.;after=recorder.stop()
        assert len(history.reports())==2
        comparison = compare_rehearsals(before,after)
        assert comparison['pages'][0]['delta_s'] < 0
        review = analyse_rehearsal(client,before,library)
        tasks = PracticeStore(output/'tasks')
        task_context = dict(context,rehearsal_id=before['id'])
        task = tasks.add(task_context,review['suggestions'][0]['advice'],1,15)
        assert tasks.add(task_context,review['suggestions'][0]['advice'],1,15)['id']==task['id']
        tasks.set_status(task['id'],'done')
        assert PracticeStore(output/'tasks').list_tasks()[0]['status']=='done'
        speech = analyse_speech(client,before,library)
        tool_session = DialogueSession(material,plan,[before,after],context)
        answer = tool_session.run(client,'比较后我应优先练习什么？')
        assert answer['proposals'][0]['page']==1
        defense = DialogueSession(material,plan,[before],context)
        defense.run(client,'开始提问','defense')
        defense.run(client,'我的回答依据系统实现。','defense')
        defense.run(client,'我的回答依据系统实现。','defense',summarize=True)
        dialogues = DialogueStore(output/'dialogues');dialogues.save(defense.record())
        assert len(dialogues.records()[0]['turns'])==3
        dialogues.export(defense.record())
        assert isinstance(local_pacing_hint(before,plan),str)
        (output/'plan.md').write_text(format_plan_md(plan),encoding='utf8')
        (output/'rehearsal.md').write_text(format_report_md(before),encoding='utf8')
        (output/'comparison.md').write_text(format_comparison_md(comparison),encoding='utf8')
        (output/'speech.md').write_text(format_speech_review_md(speech),encoding='utf8')
        receipt = dict(result='passed',supplier_connected=False,devices_started=False,
            transport='real loopback HTTP with fictional key',pages=len(material['slides']),calls=calls,
            tasks=len(tasks.list_tasks()),defense_turns=len(defense.turns),timeline_visits=len(before['page_timeline']))
        (output/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps(receipt,ensure_ascii=False));print('Evidence:',output)
        return 0
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)


if __name__=='__main__': raise SystemExit(main())
