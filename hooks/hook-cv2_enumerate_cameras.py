from PyInstaller.utils.hooks import collect_all, collect_delvewheel_libs_directory

datas, binaries, hiddenimports = collect_all('cv2_enumerate_cameras')
datas, binaries = collect_delvewheel_libs_directory(
    'cv2_enumerate_cameras', datas=datas, binaries=binaries)
