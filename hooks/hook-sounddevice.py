# PyInstaller hook：sounddevice 的 PortAudio 动态库在 _sounddevice_data 包里
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

datas = collect_data_files("_sounddevice_data")
binaries = collect_dynamic_libs("_sounddevice_data")
