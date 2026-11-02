"""Defense document checks runnable without the GUI or pytest installation.

Run: python -m unittest discover -s tests -p test_defense_materials.py -v
"""
from pathlib import Path
import re
import unittest
from urllib.parse import unquote
import xml.etree.ElementTree as ET
import zipfile


ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "docs" / "defense"
NAMES = ("七天分工与交付计划", "项目报告与PPT参考稿")
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def normalize(text):
    return re.sub(r"\s+", "", text)


def source_text(markdown):
    parts = []
    for line in markdown.splitlines():
        line = line.strip()
        if not line or line.startswith("<!--"):
            continue
        if line.startswith("|"):
            cells = [part.strip() for part in line.strip("|").split("|")]
            if all(re.fullmatch(r":?-+:?", cell) for cell in cells):
                continue
            line = "".join(cells)
        line = re.sub(r"^#{1,3}\s+|^-\s+", "", line)
        line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
        parts.append(line.replace("**", "").replace("`", ""))
    return normalize("".join(parts))


class DefenseMaterialsTests(unittest.TestCase):
    def test_each_source_has_an_editable_document(self):
        for name in NAMES:
            with self.subTest(name=name):
                self.assertTrue((FOLDER / f"{name}.md").is_file())
                with zipfile.ZipFile(FOLDER / f"{name}.docx") as archive:
                    self.assertIsNone(archive.testzip())
                    for part in ("[Content_Types].xml", "word/document.xml", "word/styles.xml"):
                        ET.fromstring(archive.read(part))

    def test_docx_preserves_all_markdown_content_in_order(self):
        for name in NAMES:
            with self.subTest(name=name):
                with zipfile.ZipFile(FOLDER / f"{name}.docx") as archive:
                    root = ET.fromstring(archive.read("word/document.xml"))
                actual = "".join(node.text or "" for node in root.findall(".//w:t", NS))
                actual = normalize(actual.replace("• ", ""))
                expected = source_text((FOLDER / f"{name}.md").read_text(encoding="utf-8"))
                self.assertEqual(expected, actual)

    def test_all_relative_evidence_links_exist(self):
        for name in NAMES:
            path = FOLDER / f"{name}.md"
            for link in re.findall(r"\[[^\]]*\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
                if "://" not in link:
                    with self.subTest(document=name, link=link):
                        self.assertTrue((path.parent / unquote(link.split("#", 1)[0])).is_file())

    def test_plans_and_results_are_explicitly_separate(self):
        text = (FOLDER / "项目报告与PPT参考稿.md").read_text(encoding="utf-8")
        for phrase in ("本周拟实现", "当前没有本轮真人准确率", "待实测填写",
                       "不是本轮重新测试", "分发次数不等于PPT执行确认",
                       "当前custom_gestures目录为空"):
            self.assertIn(phrase, text)
        self.assertNotRegex(text, r"(?:识别率高达|准确率达到|提升至)\s*\d")

    def test_schedule_covers_four_owners_and_seven_days(self):
        text = (FOLDER / "七天分工与交付计划.md").read_text(encoding="utf-8")
        for role in ("A 技术负责人", "B AI功能负责人", "C 测试与演示负责人", "D 材料负责人"):
            self.assertIn(role, text)
        for day in range(1, 8):
            self.assertRegex(text, rf"\| D{day} 10月\d+日 \|")
        for phrase in ("第五天冻结", "PPT从第一天开始", "完整演示视频", "回归", "API密钥"):
            self.assertIn(phrase, text)

    def test_docx_has_repeating_table_headers_and_no_fixed_row_heights(self):
        for name in NAMES:
            with zipfile.ZipFile(FOLDER / f"{name}.docx") as archive:
                root = ET.fromstring(archive.read("word/document.xml"))
            for table in root.findall(".//w:tbl", NS):
                self.assertIsNotNone(table.find("w:tr/w:trPr/w:tblHeader", NS))
                for paragraph in table.findall("w:tr[1]/w:tc/w:p", NS):
                    self.assertIsNotNone(paragraph.find("w:pPr/w:keepNext", NS))
            self.assertFalse(root.findall(".//w:trHeight", NS))

    def test_logical_sections_do_not_force_empty_pages(self):
        # Native Word showed blank pages when a full section's trailing break
        # moved to the next page. Keep section markers out of the final layout.
        for name in NAMES:
            with zipfile.ZipFile(FOLDER / f"{name}.docx") as archive:
                root = ET.fromstring(archive.read("word/document.xml"))
            self.assertFalse(root.findall(".//w:br[@w:type='page']", NS), name)

    def test_no_template_title_border_residue(self):
        for name in NAMES:
            with zipfile.ZipFile(FOLDER / f"{name}.docx") as archive:
                for member in ("word/document.xml", "word/styles.xml"):
                    root = ET.fromstring(archive.read(member))
                    self.assertFalse(root.findall(".//w:pBdr", NS), (name, member))


if __name__ == "__main__":
    unittest.main()
