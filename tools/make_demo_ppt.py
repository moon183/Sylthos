"""生成答辩/排练用演示 PPT（tools/make_demo_ppt.py）。

通过 PowerPoint COM 创建一份演示文稿 demo.pptx，包含各功能演示所需的素材页：
九页基础操作稿，内容来自 tools/demo_slides.json；不含嵌入视频。
运行将覆盖根目录 demo.pptx，修改前请备份。
用法：D:\\Anaconda\\envs\\gesture\\python.exe tools\\make_demo_ppt.py
"""
from __future__ import annotations

import sys
import json
from pathlib import Path

import pythoncom
import win32com.client

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "demo.pptx"

SLIDES = json.loads((ROOT / "tools" / "demo_slides.json").read_text(encoding="utf-8"))


def main() -> int:
    pythoncom.CoInitialize()
    app = win32com.client.Dispatch("PowerPoint.Application")
    pres = app.Presentations.Add()
    for title, body in SLIDES:
        slide = pres.Slides.Add(pres.Slides.Count + 1, 2)  # 2 = ppLayoutText
        slide.Shapes(1).TextFrame.TextRange.Text = title
        slide.Shapes(2).TextFrame.TextRange.Text = body
    pres.SaveAs(str(OUT))
    pres.Close()
    app.Quit()
    print(f"已生成 {OUT}（{len(SLIDES)} 页）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
