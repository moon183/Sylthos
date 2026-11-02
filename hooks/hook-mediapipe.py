# PyInstaller hook：收集 mediapipe 随包分发的模型/资源文件（SPEC 第 9 节）
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = collect_data_files("mediapipe")
hiddenimports = collect_submodules("mediapipe")
