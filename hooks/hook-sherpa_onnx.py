# PyInstaller hook：收集 sherpa_onnx 的 DLL（onnxruntime / c-api / cxx-api）与 Python 模块
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

datas = collect_data_files("sherpa_onnx")
binaries = collect_dynamic_libs("sherpa_onnx")
hiddenimports = collect_submodules("sherpa_onnx")
