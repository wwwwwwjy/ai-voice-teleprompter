# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包配置 — AI语音提词器
运行: pyinstaller AI语音提词器.spec
"""

from pathlib import Path
from runpy import run_path

HERE = Path(SPECPATH).resolve()
APP_VERSION = run_path(str(HERE / "src" / "version.py"))["APP_VERSION"]

# ---- vosk 动态库 ----
vosk_dylib = None
for p in HERE.glob("venv*/lib/python*/site-packages/vosk/libvosk.dyld"):
    vosk_dylib = str(p)
    break

binaries = [(vosk_dylib, "vosk")] if vosk_dylib else []

# ---- Analysis ----
a = Analysis(
    [str(HERE / "src" / "main.py")],
    pathex=[str(HERE / "src")],
    binaries=binaries,
    datas=[
        (str(HERE / "models" / "vosk-model-small-cn-0.22"), "models/vosk-model-small-cn-0.22"),
        (str(HERE / "src" / "resources" / "donation"), "resources/donation"),
    ],
    hiddenimports=["vosk", "sounddevice", "numpy"],
)

pyz = PYZ(a.pure)

# ---- EXE (onedir) ----
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AI语音提词器",
    console=False,
    icon=str(HERE / "icon.icns"),
)

# ---- COLLECT ----
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="AI语音提词器",
)

# ---- BUNDLE (.app) ----
app = BUNDLE(
    coll,
    name="AI语音提词器.app",
    icon=str(HERE / "icon.icns"),
    bundle_identifier="com.wangtongxue.ai-voice-teleprompter",
    info_plist={
        "CFBundleDevelopmentRegion": "zh_CN",
        "CFBundleDisplayName": "汪同学的AI语音提词器",
        "CFBundleName": "汪同学的AI语音提词器",
        "CFBundleShortVersionString": APP_VERSION,
        "CFBundleVersion": APP_VERSION,
        "NSMicrophoneUsageDescription": "我们需要访问您的麦克风来实现语音实时提词跟随功能。",
        "NSHighResolutionCapable": True,
    },
)
