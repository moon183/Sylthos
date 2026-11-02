"""配置路径规则测试（frozen/源码两种运行形态，SPEC 第 9 节）。"""
from __future__ import annotations

import sys
from pathlib import Path


def test_project_root_source_mode():
    from src.config import _project_root

    root = _project_root()
    assert (root / "config.json").exists()


def test_project_root_frozen_mode(monkeypatch, tmp_path):
    fake_exe = tmp_path / "GesturePPT" / "GesturePPT.exe"
    fake_exe.parent.mkdir(parents=True)
    fake_exe.touch()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))
    from src.config import _project_root

    assert _project_root() == fake_exe.parent.resolve()
