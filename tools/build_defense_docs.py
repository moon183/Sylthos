"""Build editable defense handouts from their Markdown content sources.

Use the document-authoring runtime with python-docx installed. This tool does
not import the application, read config.json, or change the existing demo deck.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
SOURCES = ("七天分工与交付计划", "项目报告与PPT参考稿")


def plain(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text.replace("**", "").replace("`", "")


def add_runs(paragraph, text: str) -> None:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    for index, part in enumerate(text.split("**")):
        run = paragraph.add_run(part.replace("`", ""))
        run.bold = bool(index % 2)


def setup_document(title: str):
    doc = Document()
    doc.core_properties.title = title
    doc.core_properties.subject = "四人七天答辩筹备与项目说明参考"
    doc.core_properties.author = ""
    doc.core_properties.last_modified_by = ""
    # The bundled Word template contains blue title borders. Strip style
    # residue so the plain black report headings remain the visual authority.
    for style in doc.styles:
        for border in list(style.element.iter(qn("w:pBdr"))):
            border.getparent().remove(border)
    section = doc.sections[0]
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    section.top_margin = section.bottom_margin = Cm(1.7)
    section.left_margin = section.right_margin = Cm(1.85)
    section.header_distance = section.footer_distance = Cm(0.75)
    for name, size in (("Normal", 10.5), ("Title", 21),
                       ("Heading 1", 15), ("Heading 2", 11.5)):
        style = doc.styles[name]
        style.font.name = "Microsoft YaHei"
        style.font.size = Pt(size)
        style.font.color.rgb = RGBColor(0, 0, 0)
        fonts = style.element.get_or_add_rPr().get_or_add_rFonts()
        fonts.set(qn("w:eastAsia"), "微软雅黑")
        fonts.set(qn("w:ascii"), "Microsoft YaHei")
        fonts.set(qn("w:hAnsi"), "Microsoft YaHei")
        style.paragraph_format.line_spacing = 1.25
        style.paragraph_format.space_after = Pt(6)
        style.paragraph_format.widow_control = True
    doc.styles["Title"].paragraph_format.space_after = Pt(12)
    for name in ("Heading 1", "Heading 2"):
        doc.styles[name].font.bold = True
        doc.styles[name].paragraph_format.space_before = Pt(10)
        doc.styles[name].paragraph_format.keep_with_next = True
    header = section.header.paragraphs[0]
    run = header.add_run("Sylthos  答辩筹备参考  2026年10月25日")
    run.font.name, run.font.size = "Microsoft YaHei", Pt(8)
    run.font.color.rgb = RGBColor(0, 0, 0)
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    footer.add_run("第 ").font.size = Pt(8)
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    footer._p.append(field)
    footer.add_run(" 页").font.size = Pt(8)
    return doc


def add_table(doc, rows: list[list[str]]) -> None:
    table = doc.add_table(rows=0, cols=len(rows[0]))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    count = len(rows[0])
    widths = {2: [4.2, 13.1], 3: [3.1, 7.2, 7.0],
              4: [2.2, 4.0, 6.1, 5.0], 5: [2.0, 3.825, 3.825, 3.825, 3.825]}[count]
    if "页码" in rows[0]:
        widths = [1.15, 2.6, 8.15, 5.4]
    if "参与者" in rows[0]:
        widths = [1.25, 3.35, 3.65, 4.45, 4.6]
    if "提供人" in rows[0]:
        widths = [2.2, 2.2, 12.9]
    if "风险" in rows[0]:
        widths = [4.0, 11.3, 2.0]
    if "成员" in rows[0]:
        widths = [3.2, 3.2, 6.8, 4.1]
    if "资料" in rows[0]:
        widths = [5.0, 12.3]
    for column, width in zip(table.columns, widths):
        column.width = Cm(width)
    borders = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        edge = OxmlElement(f"w:{side}")
        for key, value in (("val", "single"), ("sz", "4"), ("color", "D9D9D9")):
            edge.set(qn(f"w:{key}"), value)
        borders.append(edge)
    table._tbl.tblPr.append(borders)
    margins = OxmlElement("w:tblCellMar")
    for side, value in (("top", "80"), ("bottom", "80"), ("left", "100"), ("right", "100")):
        item = OxmlElement(f"w:{side}")
        item.set(qn("w:w"), value)
        item.set(qn("w:type"), "dxa")
        margins.append(item)
    table._tbl.tblPr.append(margins)
    for row_index, values in enumerate(rows):
        row = table.add_row()
        props = row._tr.get_or_add_trPr()
        props.append(OxmlElement("w:cantSplit"))
        if row_index == 0:
            props.append(OxmlElement("w:tblHeader"))
        for col_index, (cell, value, width) in enumerate(zip(row.cells, values, widths)):
            cell.width = Cm(width)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            paragraph = cell.paragraphs[0]
            paragraph.paragraph_format.space_after = Pt(1)
            paragraph.paragraph_format.space_before = Pt(1)
            paragraph.paragraph_format.line_spacing = 1.15
            paragraph.paragraph_format.keep_with_next = row_index == 0
            if col_index == 0:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            add_runs(paragraph, value)
            for run in paragraph.runs:
                run.font.size = Pt(9)
                run.bold = row_index == 0
            if row_index == 0:
                shade = OxmlElement("w:shd")
                shade.set(qn("w:fill"), "E6EDF3")
                cell._tc.get_or_add_tcPr().append(shade)
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(2)
    paragraph.paragraph_format.line_spacing = 0.3
    paragraph.add_run().font.size = Pt(2)


def build(source: Path, destination: Path) -> None:
    lines = source.read_text(encoding="utf-8").splitlines()
    doc = setup_document(plain(lines[0].removeprefix("# ")))
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue
        if line.startswith("|"):
            rows = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                values = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", value) for value in values):
                    rows.append(values)
                index += 1
            add_table(doc, rows)
            continue
        if line == "<!-- pagebreak -->":
            # Logical Markdown groups should flow naturally in Word. A forced
            # break can itself spill and create a blank page after a full page.
            pass
        elif line.startswith("# "):
            add_runs(doc.add_paragraph(style="Title"), line[2:])
        elif line.startswith("## "):
            add_runs(doc.add_paragraph(style="Heading 1"), line[3:])
        elif line.startswith("### "):
            add_runs(doc.add_paragraph(style="Heading 2"), line[4:])
        elif line.startswith("- "):
            paragraph = doc.add_paragraph()
            paragraph.paragraph_format.left_indent = Cm(0.35)
            paragraph.paragraph_format.first_line_indent = Cm(-0.35)
            add_runs(paragraph, "• " + line[2:])
        else:
            add_runs(doc.add_paragraph(), line)
        index += 1
    destination.parent.mkdir(parents=True, exist_ok=True)
    doc.save(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs" / "defense")
    args = parser.parse_args()
    for name in SOURCES:
        target = args.output_dir / f"{name}.docx"
        build(ROOT / "docs" / "defense" / f"{name}.md", target)
        print(target)


if __name__ == "__main__":
    main()
