"""阈值热更新测试（P1，2026-09-12 实测反馈：设置页改完参数，
正在运行的监控不生效——检测器构造时已把阈值拷贝成成员变量）。

锁死：reload_config 后检测器读取新阈值；引擎模式/功能开关/录制状态不受打扰。
"""
from __future__ import annotations

import copy

from test_e2e import FULL_CFG

from src.decision import Mode
from src.pipeline import Pipeline


def test_reload_picks_up_new_threshold(tmp_path, monkeypatch):
    import src.pipeline as pl

    monkeypatch.setattr(pl, "PROJECT_ROOT", tmp_path)  # 隔离仓库真实 custom_gestures
    cfg = copy.deepcopy(FULL_CFG)
    pipeline = Pipeline(cfg, with_controls=True, screen_size=(1920, 1080))
    old = pipeline.swipe._min_disp
    pipeline.engine.mode = Mode.ARMED
    pipeline.engine.set_feature_enabled("laser", False)

    cfg["swipe"]["min_displacement_hs"] = 9.9  # 模拟设置页改动（共享同一 dict）
    pipeline.reload_config()

    assert pipeline.swipe._min_disp == 9.9 != old  # 新阈值生效
    assert pipeline.engine.mode is Mode.ARMED       # 模式不被重置
    assert pipeline.engine.enabled_features["laser"] is False  # 运行时开关保留


def test_reload_preserves_recorder(tmp_path, monkeypatch):
    import src.pipeline as pl

    monkeypatch.setattr(pl, "PROJECT_ROOT", tmp_path)
    pipeline = Pipeline(copy.deepcopy(FULL_CFG))
    recorder = pipeline.custom_recorder
    pipeline.reload_config()
    assert pipeline.custom_recorder is recorder  # 录制中的样本不被打断


def test_reload_preserves_custom_model(tmp_path, monkeypatch):
    """热更新不从硬盘重读模型失败而丢模型：custom_gestures 为空目录时 detector
    只是不可用，不抛异常；有模型时 reload 后仍可用。"""
    import csv
    import math

    import numpy as np

    import src.pipeline as pl
    from src.gestures.trajectory import train_from_directory

    monkeypatch.setattr(pl, "PROJECT_ROOT", tmp_path)
    # 造一个真实模型：circle 两类样本
    d = tmp_path / "custom_gestures" / "circle"
    d.mkdir(parents=True)
    for i in range(4):
        pts = [(0.5 + 0.12 * math.cos(2 * math.pi * j / 30),
                0.4 + 0.12 * math.sin(2 * math.pi * j / 30)) for j in range(30)]
        with open(d / f"{i}.csv", "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(pts)
    model, _ = train_from_directory(tmp_path / "custom_gestures", seed=0)
    model.save(tmp_path / "custom_gestures" / "model.json")

    pipeline = Pipeline(copy.deepcopy(FULL_CFG))
    assert pipeline.custom_detector.available
    pipeline.reload_config()
    assert pipeline.custom_detector.available  # 模型/模板重载后仍可用


def test_worker_reload_flag():
    from src.gui.worker import GestureWorker

    w = GestureWorker(copy.deepcopy(FULL_CFG))
    assert not w._reload_requested
    w.request_config_reload()
    assert w._reload_requested
