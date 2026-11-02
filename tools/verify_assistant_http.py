"""Local-only HTTP acceptance probe. Uses synthetic credentials, never user config."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from threading import Thread
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.assistant_api import ApiSettings, ChatClient
from src.assistant_service import generate_plan, analyse_rehearsal, format_plan_md, format_review_md
from src.presentation_materials import read_pptx
from src.presentation_store import PresentationStore


def main():
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            assert self.path == '/v1/chat/completions'
            assert self.headers['Authorization'] == 'Bearer local-test-only'
            request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            assert request['model'] == 'local-model'
            user = request['messages'][-1]['content']
            if '请只回复 OK' in user:
                content = 'OK'
                calls.append('connection')
            else:
                data = json.loads(user)
                if 'outline' in data:
                    value = dict(overview='本机模拟建议：问题、方法、演示、结果。', slide_plans=[
                        dict(page=s['page'], budget_weight=2, key_points=['本机模拟重点'], script='本机模拟讲稿，仅用于验证传输。',
                             transition='接下来介绍下一部分。', questions=['有哪些限制？'], issues=[]) for s in data['slides']])
                    calls.append('plan')
                else:
                    value = dict(summary='本机模拟复盘：核对时间分配后再练习。', suggestions=[
                        dict(page=1, advice='本机模拟建议：精简背景说明。', evidence_ids=['page_1'])])
                    calls.append('review')
                content = json.dumps(value, ensure_ascii=False)
            response = json.dumps({'choices':[{'finish_reason':'stop', 'message':{'content':content}}]}, ensure_ascii=False).encode('utf8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(response)))
            self.end_headers()
            self.wfile.write(response)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    output = ROOT / 'build' / 'assistant_http' / uuid4().hex
    store = PresentationStore(output / 'library')
    try:
        client = ChatClient(ApiSettings(enabled=True, api_key='local-test-only', model='local-model',
                                        base_url=f'http://127.0.0.1:{server.server_port}/v1'))
        client.test_connection()
        material = store.save_material(read_pptx(ROOT / 'demo.pptx'))
        generated = generate_plan(client, material, '模拟受众', 480, '只验证调用链')
        plan = store.save_plan(material['material_version_id'], '模拟受众', 480, '只验证调用链',
                              generated['slide_plans'], overview=generated['overview'], generation=generated['generation'])
        context = next(c for c in store.contexts() if c['plan_id'] == plan['id'])
        report = dict(id=uuid4().hex, status='completed', duration_s=500, command_total=8, rejections=1,
                      page_stay={i:50 for i in range(1,10)}, page_gaps=1, page_seen=True, presentation_context=context)
        review = analyse_rehearsal(client, report, store)
        assert sum(s['budget_s'] or 0 for s in plan['slide_plans']) == 480
        assert review['rehearsal_id'] == report['id']
        (output / 'plan.md').write_text(format_plan_md(plan), encoding='utf8')
        (output / 'review.md').write_text(format_review_md(review), encoding='utf8')
        receipt = dict(result='passed', supplier_connected=False, transport='real HTTP on loopback',
                       calls=calls, pages=len(plan['slide_plans']), budget_s=480)
        (output / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf8')
        print(json.dumps(receipt, ensure_ascii=False))
        print('Evidence:', output)
        return 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


if __name__ == '__main__':
    raise SystemExit(main())
