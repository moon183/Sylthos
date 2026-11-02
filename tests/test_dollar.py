"""$1 模板匹配引擎测试（2026-09-12 调研落地：小样本轨迹识别用几何模板匹配，见
RESEARCH_ROUND3.md 第三节；$1 论文：1 模板 97% / 3+ 模板 99% 准确率）。

全部合成数据，不依赖摄像头。
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np
import pytest

from src.gestures.dollar import DollarRecognizer, normalize_dollar


def _circle(n=48, radius=0.12, center=(0.5, 0.4), ccw=False):
    rng = range(n - 1, -1, -1) if ccw else range(n)
    return [(center[0] + radius * math.cos(2 * math.pi * i / n),
             center[1] + radius * math.sin(2 * math.pi * i / n)) for i in rng]


def _hline(n=40, y=0.4, x0=0.3, x1=0.7):
    return [(x0 + (x1 - x0) * i / (n - 1), y) for i in range(n)]


def _check(n=40):
    """打勾：先下后上。"""
    half = n // 2
    down = [(0.35 + 0.15 * i / half, 0.35 + 0.15 * i / half) for i in range(half)]
    up = [(0.50 + 0.25 * (i / (n - half)), 0.50 - 0.30 * (i / (n - half)))
          for i in range(n - half)]
    return down + up


def _zigzag(n=25):
    return [(0.3 + 0.02 * i, 0.4 + (0.12 if i % 2 else -0.12)) for i in range(n)]


def _write(root: Path, name: str, gen, count: int) -> None:
    d = root / name
    d.mkdir(parents=True)
    for i in range(count):
        with open(d / f"{i}.csv", "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(gen())


@pytest.fixture()
def recognizer(tmp_path):
    np.random.seed(0)
    _write(tmp_path, "circle", lambda: _circle(radius=0.10 + 0.04 * np.random.rand(),
                                               center=(0.45 + 0.1 * np.random.rand(),
                                                       0.40 + 0.1 * np.random.rand())), 6)
    _write(tmp_path, "check", lambda: [(x + 0.03 * np.random.randn() * 0.01,
                                        y + 0.03 * np.random.randn() * 0.01)
                                       for x, y in _check()], 6)
    rec = DollarRecognizer()
    assert rec.load_directory(tmp_path) == 12
    return rec


# ---------- 归一化性质 ----------

def test_normalize_translation_scale_invariance():
    a = normalize_dollar(_circle(radius=0.08, center=(0.3, 0.3)))
    b = normalize_dollar(_circle(radius=0.30, center=(0.7, 0.6)))
    assert np.allclose(a, b, atol=1e-6)


def test_normalize_fixed_points():
    assert normalize_dollar(_circle(n=100)).shape == (32, 2)
    assert normalize_dollar(_circle(n=15)).shape == (32, 2)


# ---------- 识别 ----------

def test_circle_scores_higher_than_line_on_circle_templates(recognizer):
    scored = dict(recognizer.score_templates(_circle()))
    best = recognizer.recognize(_circle())
    assert best["label"] == "circle"
    assert best["score"] >= 0.75
    # 横线打圆模板：得分应明显低于真圆
    line_best = recognizer.recognize(_hline())
    assert line_best["score"] < best["score"] - 0.1


def test_check_recognized(recognizer):
    best = recognizer.recognize(_check())
    assert best["label"] == "check" and best["score"] >= 0.7


def test_direction_sensitive():
    """$1 方向敏感：逆时针画圈不应高分命中顺时针模板（顺/逆时针可作两个手势）。"""
    cw = DollarRecognizer()
    cw._templates = [("cw", normalize_dollar(_circle()))]
    score_cw = cw.recognize(_circle())["score"]
    score_ccw = cw.recognize(_circle(ccw=True))["score"]
    assert score_cw > score_ccw + 0.15


def test_margin_structure(recognizer):
    """距离比拒绝门的数据结构：最优/次优异类/领先幅度齐全。"""
    res = recognizer.recognize(_circle())
    assert set(res) >= {"label", "score", "second_label", "second_score", "margin"}
    assert res["second_label"] == "check"
    assert res["margin"] == pytest.approx(res["score"] - res["second_score"])


def test_empty_recognizer_returns_none():
    assert DollarRecognizer().recognize(_circle()) is None


def test_load_directory_missing(tmp_path):
    rec = DollarRecognizer()
    assert rec.load_directory(tmp_path / "nonexistent") == 0
    assert not rec.has_templates
