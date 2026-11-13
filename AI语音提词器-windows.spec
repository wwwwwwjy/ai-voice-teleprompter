# -*- mode: python ; coding: utf-8 -*-
"""Windows 免安装便携版 PyInstaller 配置。必须在 Windows 中执行。"""

from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs


HERE = Path(SPECPATH).resolve()
vosk_datas, vosk_binaries, vosk_hiddenimports = collect_all("vosk")
sounddevice_binaries = collect_dynamic_libs("_sounddevice_data")

a = Analysis(
    [str(HERE / "src" / "main.py")],
    pathex=[str(HERE / "src")],
    binaries=vosk_binaries + sounddevice_binaries,
    datas=[
        (str(HERE / "models" / "vosk-model-small-cn-0.22"),
         "models/vosk-model-small-cn-0.22"),
        (str(HERE / "src" / "resources" / "donation"),
         "resources/donation"),
    ] + vosk_datas,
    hiddenimports=["sounddevice", "numpy", "docx"] + vosk_hiddenimports,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="汪同学的AI语音提词器",
    console=False,
    icon=str(HERE / "icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="汪同学的AI语音提词器",
)
