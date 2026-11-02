"""生成《摄像头 60fps 实测报告》docx（kimi-word 技能：python-docx 简单文档路线）。"""
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

OUT = r"D:\Kimicode\Gesturerecognition\摄像头60fps实测报告.docx"

doc = Document()

# 全局字体（中文用微软雅黑）
style = doc.styles["Normal"]
style.font.name = "Microsoft YaHei"
style.font.size = Pt(10.5)
style.element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")

# 标题
title = doc.add_heading("关于所购摄像头无法达到 60fps 的实测报告", level=0)
title.alignment = WD_ALIGN_PARAGRAPH.CENTER

meta = doc.add_paragraph()
meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = meta.add_run("测试日期：2026-09-13    测试设备：所购摄像头（系统识别名称：4K USB Camera）\n"
                   "测试环境：Windows 11 笔记本，USB 连接")
run.font.size = Pt(9)
run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

# 结论框
doc.add_heading("一句话结论", level=1)
p = doc.add_paragraph()
r = p.add_run("该摄像头在全部分辨率与编码格式下，输出帧率上限均为 30fps，"
              "任何模式下都达不到 60fps；请商家核实“60 帧”宣传的实现条件，否则申请退换。")
r.bold = True

doc.add_heading("测试一：摄像头自身上报的支持模式（设备描述符枚举）", level=1)
doc.add_paragraph(
    "通过 Qt Multimedia（与 Windows 系统相机同源，走 Windows Media Foundation）"
    "枚举该摄像头自己声明支持的全部模式，结果如下：")

rows1 = [
    ("640×480", "JPEG / NV12 / YUYV", "30–30 fps"),
    ("1280×720", "JPEG / NV12", "30–30 fps"),
    ("1280×720", "YUYV", "仅 8 fps"),
    ("1920×1080", "JPEG / NV12", "30–30 fps"),
    ("2048×1536", "JPEG / NV12", "30–30 fps"),
    ("2560×1440", "JPEG / NV12", "仅 20 fps"),
    ("2592×1944", "JPEG / NV12", "30–30 fps"),
    ("2688×1520", "JPEG / NV12", "30–30 fps"),
    ("3840×2160（4K）", "JPEG / NV12", "仅 20 fps"),
    ("4032×3024", "JPEG / NV12", "仅 5–15 fps"),
]
t1 = doc.add_table(rows=1, cols=3)
t1.style = "Table Grid"
hdr = t1.rows[0].cells
for i, h in enumerate(("分辨率", "编码格式", "帧率范围")):
    hdr[i].text = h
    for pr in hdr[i].paragraphs:
        for rr in pr.runs:
            rr.bold = True
for r1 in rows1:
    cells = t1.add_row().cells
    for i, v in enumerate(r1):
        cells[i].text = v

p = doc.add_paragraph()
r = p.add_run("要点：设备描述符中不存在任何 60fps 模式——"
              "连最小的 640×480 分辨率上限也是 30fps。")
r.bold = True
r.font.color.rgb = RGBColor(0xC0, 0x00, 0x00)

doc.add_heading("测试二：实际取流测速（OpenCV，MSMF 后端 + MJPG 编码）", level=1)
doc.add_paragraph("软件主动请求 60fps/120fps，统计实际到达帧率（纯读帧，不含任何图像处理）：")

rows2 = [
    ("640×480 @ 60 fps", "29.6 fps"),
    ("640×480 @ 120 fps", "30.1 fps"),
    ("1280×720 @ 60 fps", "29.6 fps"),
    ("1280×720 @ 30 fps", "29.6 fps"),
    ("1920×1080 @ 60 fps", "29.6 fps"),
    ("1920×1080 @ 30 fps", "30.1 fps"),
    ("3840×2160 @ 30 fps", "19.6 fps"),
]
t2 = doc.add_table(rows=1, cols=2)
t2.style = "Table Grid"
hdr = t2.rows[0].cells
for i, h in enumerate(("请求模式", "实测帧率")):
    hdr[i].text = h
    for pr in hdr[i].paragraphs:
        for rr in pr.runs:
            rr.bold = True
for r2 in rows2:
    cells = t2.add_row().cells
    cells[0].text = r2[0]
    cells[1].text = r2[1]

p = doc.add_paragraph()
r = p.add_run("要点：无论请求 60 还是 120fps，设备实际只输出约 30fps。")
r.bold = True
r.font.color.rgb = RGBColor(0xC0, 0x00, 0x00)

doc.add_heading("给商家的问题", level=1)
for i, q in enumerate((
        "商品页宣传的“60 帧”需要在什么条件下实现？"
        "（哪个分辨率、哪种编码、是否需要专用驱动/软件）",
        "若确需特定条件，请提供对应的驱动/工具与设置方法；",
        "若该型号实际不支持 60fps，请按宣传不符处理退换事宜。"), start=1):
    doc.add_paragraph(f"{i}. {q}")

doc.add_paragraph()
note = doc.add_paragraph(
    "附注：以上测试均使用操作系统标准摄像头接口（Windows Media Foundation / DirectShow）"
    "与业界通用的 OpenCV、Qt 多媒体框架完成，结果可由商家用同类工具复现。")
note.runs[0].font.size = Pt(9)
note.runs[0].font.color.rgb = RGBColor(0x66, 0x66, 0x66)

doc.save(OUT)
print("saved:", OUT)
