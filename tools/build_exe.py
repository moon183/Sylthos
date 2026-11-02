"""打包脚本（PLAN 步骤 24 / SPEC 第 9 节）：

    python tools/build_exe.py

--onedir 优先（启动快、排错容易）；hook 收集 mediapipe 模型文件；
资源路径兼容 sys._MEIPASS；产物路径不得含中文。
打包后请在无 Python 环境的干净 Windows 机器上验证 dist/GesturePPT/GesturePPT.exe。
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
import os
from pathlib import PureWindowsPath, PurePosixPath
import re
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def sanitize_config(value):
    """Return a shareable copy, retaining ordinary non-private settings."""
    if isinstance(value, dict):
        sanitized = {}
        for key, child in value.items():
            normalized = re.sub(r'[^a-z0-9]', '', key.lower())
            credential = (normalized in ('key', 'authorization', 'credential', 'credentials')
                          or any(part in normalized for part in
                                 ('apikey', 'accesskey', 'token', 'password', 'passwd', 'secret', 'privatekey')))
            sanitized[key] = '' if credential else sanitize_config(child)
        return sanitized
    if isinstance(value, list):
        return [sanitize_config(child) for child in value]
    if isinstance(value, str) and (PureWindowsPath(value).is_absolute()
                                  or PurePosixPath(value).is_absolute()
                                  or value.startswith(('~/', '~\\'))):
        return ''
    return value


def write_shareable_config(destination: Path) -> None:
    source = json.loads((ROOT / 'config.json').read_text(encoding='utf-8-sig'))
    if not isinstance(source, dict):
        raise ValueError('配置必须为 JSON 对象。')
    sanitized = sanitize_config(source)
    if not isinstance(sanitized.get('asr'), dict):
        sanitized['asr'] = {}
    sanitized['asr']['enabled'] = False
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(sanitized, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def copy_runtime_resources(destination: Path, shareable=False) -> None:
    """外置资源随exe目录迁移；不复制运行日志或修改源配置。"""
    destination.mkdir(parents=True, exist_ok=True)
    if shareable:
        write_shareable_config(destination / 'config.json')
    for filename in (("demo.pptx",) if shareable else ("config.json", "demo.pptx")):
        shutil.copy2(ROOT / filename, destination / filename)
    for directory in (("models",) if shareable else ("models", "custom_gestures")):
        source = ROOT / directory
        if source.is_dir():
            shutil.copytree(source, destination / directory, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="构建Sylthos本机使用包（包含当前配置与已有模型）")
    parser.add_argument("--dist-dir", type=Path, default=ROOT / "dist",
                        help="输出父目录；可先构建到临时目录，验收后再替换旧版")
    parser.add_argument('--shareable', action='store_true',
                        help='生成共享包：脱敏内外配置，关闭语音，不复制个人手势样本')
    args = parser.parse_args(argv)
    output = args.dist_dir.resolve()
    if any("一" <= ch <= "鿿" for ch in str(ROOT)):
        print("错误：项目路径包含中文，PyInstaller + mediapipe 会因此失败，请移动项目。")
        return 1
    # 限定DLL搜索目录，避免宿主工具（如Poppler）的同名ICU覆盖系统ICU。
    env_dir = Path(sys.executable).resolve().parent
    windows = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join(str(p) for p in (
        env_dir, env_dir / "Scripts", env_dir / "Library" / "bin",
        windows / "System32", windows,
    ))
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onedir", "--noconsole", "--clean",
        "--additional-hooks-dir=" + str(ROOT / "hooks"),
        "--distpath", str(output),
        "--specpath", str(ROOT / "build" / "spec"),
        "--name", "GesturePPT",
        "--add-data", str(ROOT / "config.json") + ";.",
        "--add-data", str(ROOT / "src" / "strategy_policies.json") + ";src",
        "--add-data", str(ROOT / "src" / "assistant_skills") + ";src/assistant_skills",
        "--add-data", str(ROOT / "src" / "scenario_skills") + ";src/scenario_skills",
        str(ROOT / "src" / "main.py"),
    ]
    with ExitStack() as stack:
        if args.shareable:
            stage_parent = ROOT / 'build'
            stage_parent.mkdir(parents=True, exist_ok=True)
            stage = Path(stack.enter_context(TemporaryDirectory(prefix='shareable-', dir=stage_parent)))
            staged_config = stage / 'config.json'
            write_shareable_config(staged_config)
            cmd[cmd.index('--add-data') + 1] = str(staged_config) + ';.'
        print("执行:", " ".join(cmd))
        code = subprocess.call(cmd, cwd=ROOT, env=env)
    if code == 0:
        if args.shareable:
            copy_runtime_resources(output / 'GesturePPT', shareable=True)
            print(f"共享包已输出：{output / 'GesturePPT'}（配置已脱敏，语音默认关闭，不含个人手势样本）")
            return code
        copy_runtime_resources(output / "GesturePPT")
        print(f"已复制配置、演示PPT及已有模型/手势样本到 {output / 'GesturePPT'}")
        print("这是本机使用包，保留当前配置；对外分发前请检查密钥和个人绝对路径。")
    return code


if __name__ == "__main__":
    sys.exit(main())
