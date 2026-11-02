"""交接迁移回归：链接、源码索引及实际演示稿不得与内容源脱节。"""
from pathlib import Path
import ast
import json
import re
import runpy
from urllib.parse import unquote
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def test_current_handoff_local_links_resolve():
    # 历史全文保持原貌，旧产物路径不作为当前交付契约。
    docs = [ROOT / name for name in (
        'HANDOVER.md', 'README.md', 'DEMO.md', 'CURRENT_STATE.md',
        'docs/CODE_REFERENCE.md', 'docs/CONFIG_REFERENCE.md',
        'docs/DOCUMENTATION_UPDATE_20261023.md', 'docs/DOCUMENT_INDEX.md',
        'SYNC_RECORD.md', 'docs/reviews/README.md',
        'docs/reviews/HANDOFF_AUDIT_20261024.md')]
    missing = []
    for doc in docs:
        for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)', doc.read_text(encoding='utf8')):
            target = unquote(link.split('#', 1)[0])
            if not target or '://' in target:
                continue
            if not (doc.parent / target).exists():
                missing.append((doc.name, target))
    assert not missing


def test_code_reference_names_exist_in_referenced_modules():
    text = (ROOT / 'docs/CODE_REFERENCE.md').read_text(encoding='utf8')
    rows = re.findall(r'^\| \[([^]]+)\]\([^)]+\) \| (.*?) \|$', text, re.M)
    assert rows
    for relative, definitions in rows:
        tree = ast.parse((ROOT / relative).read_text(encoding='utf-8-sig'))
        actual = {node.name for node in tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))}
        documented = set(re.findall(r'`([^`]+)`', definitions))
        assert documented <= actual, (relative, documented - actual)


def test_demo_generator_and_delivered_deck_match_content_source():
    expected = json.loads((ROOT / 'tools/demo_slides.json').read_text(encoding='utf8'))
    generator = runpy.run_path(str(ROOT / 'tools/make_demo_ppt.py'))
    assert generator['SLIDES'] == expected
    ns = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
    with zipfile.ZipFile(ROOT / 'demo.pptx') as package:
        slides = sorted((n for n in package.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml', n)),
                        key=lambda n: int(re.search(r'slide(\d+)', n).group(1)))
        assert len(slides) == len(expected)
        for path, (title, body) in zip(slides, expected):
            node = ET.fromstring(package.read(path))
            actual = ''.join(t.text or '' for t in node.findall('.//a:t', ns))
            # 不依赖Office如何把文字拆成run；保留中文标点和所有正文内容。
            assert re.sub(r'\s+', '', title + body) == re.sub(r'\s+', '', actual), path


def test_fluent_gui_dependency_is_in_install_manifest_and_spec():
    requirements = (ROOT / 'requirements.txt').read_text(encoding='utf8')
    spec = (ROOT / 'SPEC.md').read_text(encoding='utf8')
    for package in ('PySide6-Fluent-Widgets', 'cv2-enumerate-cameras'):
        assert re.search(r'^' + re.escape(package) + r'(?:[<>=!~].*)?$', requirements, re.M)
        assert package in spec
