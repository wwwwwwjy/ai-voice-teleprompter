# CLAUDE.md — AI 语音提词器项目指引

## 项目概述

macOS / Windows 全屏语音提词器。支持平滑滚动、离线语音识别跟随、智能跳段。作者：汪同学。

## 快速启动

```bash
cd "/path/to/ai语音提词器"
source venv312/bin/activate
python src/main.py
```

## 打包

```bash
source venv312/bin/activate
pyinstaller AI语音提词器.spec
# 产物: dist/AI语音提词器.app
```

当前使用 PyInstaller onedir `.app` 打包，体积比 onefile 大，但启动时不再先解压整包，点击后更快显示加载框。

## 项目结构

```
src/
├── main.py                  ← 入口（启动浮窗 → 主窗口）
├── ui/
│   ├── main_window.py       ← 主控制面板（文件列表 + 设置 + 编辑器 + 预览）
│   ├── fullscreen.py        ← 全屏提词窗口（文字渲染 + 滚动 + 跟随）
│   ├── controls.py          ← 全屏悬浮控制条（滑块版）
│   ├── text_preview.py      ← 主页实时预览组件
│   ├── settings_dialog.py   ← 设置对话框（麦克风选择等）
│   └── splash.py            ← 启动加载浮窗
├── core/
│   ├── text_parser.py       ← 文字排版引擎（像素宽度折行）
│   ├── scroller.py          ← 平滑滚动引擎
│   └── prompter.py          ← 文字状态管理（已读/正在读/未读）
├── speech/
│   ├── recognizer.py        ← Vosk 语音识别（回调+工作线程分离）
│   └── follower.py          ← 语音跟随引擎（滑动窗口模糊匹配+跳段）
└── utils/
    ├── config.py            ← JSON 配置持久化
    └── file_io.py           ← 文本文件读写

models/vosk-model-small-cn-0.22/   ← Vosk 中文小模型 (~42MB)
AI语音提词器.spec                  ← PyInstaller 打包配置
AI语音提词器-windows.spec          ← Windows PyInstaller 打包配置
Info.plist                         ← macOS App 权限声明
convert_icon.py                    ← logo.png → icon.icns 转换脚本
```

## 技术栈

- Python 3.12（venv312）| PyQt6 | Vosk 离线语音识别 | sounddevice | PyInstaller

## 核心功能状态

| 功能 | 状态 | 说明 |
|------|------|------|
| 全屏文字滚动 | ✅ | 60fps 平滑滚动，速度 1-30 可调 |
| 文字格式调节 | ✅ | 字号 18-200，粗细切换，文本宽度 4-100 |
| 提词位置 | ✅ | 10%-90% 滑块，高亮行垂直位置可调 |
| 文件管理 | ✅ | 左侧文件列表，快速保存/加载 .txt |
| 实时预览 | ✅ | 主页右侧等比缩放预览，所见即所得 |
| 语音识别 | ✅ | Vosk 离线，回调+工作线程分离，不阻塞 |
| 语音跟随 | ✅ | 滑动窗口模糊匹配，跳段防抖确认 |
| 逐字渐变高亮 | ✅ | 当前字纯白，已读字渐灰淡出，无下划线 |
| 平滑滚动动画 | ✅ | 定时器内插，8% 缓动逼近目标 |
| 启动浮窗 | ✅ | 秒弹浮窗，后台加载模型 |
| 深浅色主题 | ❌ | 已删除（闪退），当前固定深色 |
| 键盘快捷键 | ✅ | 空格暂停，↑↓ 手动滚动，ESC 退出 |
| 支持作者 | ✅ | 设置页底部按钮弹出固定的支付宝与微信收款码 |

## 已修复的问题

- 语音识别回调阻塞 → 改为回调只收数据，工作线程做识别
- 全屏预览与全屏不一致 → 统一计算公式
- 语音跟随闪退 → QTimer 内插替代 QVariantAnimation
- 启动慢 → vosk/sounddevice 延迟导入 + 子线程模型加载 + 启动浮窗
- 外置 SSD 死锁 → 打包缓存指向 /tmp
- 语音跟随重复 partial 与标点干扰 → 只处理 partial 增量，匹配前归一化标点/空白
- 语音识别跑偏 → 开启语音跟随前把当前稿件注入 Vosk 动态语法，优先识别台词内容
- 快语速跟随滞后 → 音频块从 8000 降到 2000，队列满时丢旧音频，并加入语速辅助推进
- App 启动空白等待 → PyInstaller 从 onefile 改为 onedir `.app`，并给启动浮窗增加明确进度

## 待办

- 语音跟随识别准确度继续优化（当前小模型准确率有限，可考虑更大模型）
- 未做代码签名/公证，分发给他人需右键打开

## 图标

更新 logo.png 后运行 `python convert_icon.py`，然后重新打包。
