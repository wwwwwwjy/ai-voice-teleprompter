# 技术方案

## 技术栈

| 层级 | 技术 | 版本 | 用途 |
|------|------|------|------|
| 语言 | Python | 3.10+ | 主开发语言 |
| UI | PyQt6 | 6.x | 窗口、全屏渲染、控件 |
| 语音识别 | Vosk | 0.3.45 | 离线语音识别引擎 |
| 模型 | vosk-model-small-cn | 0.22 | 中文小模型（含英文），~42MB |
| 音频采集 | sounddevice | 0.4.x | 麦克风音频流捕获 |
| 数值计算 | numpy | 1.24+ | 音频数据处理 |
| 打包 | PyInstaller | 6.x | 打包为 Mac .app |

## 项目结构

```
ai语音提词器/
├── src/
│   ├── main.py              # 入口，启动主窗口
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── main_window.py   # 主控制面板窗口
│   │   ├── fullscreen.py    # 全屏提词窗口
│   │   └── controls.py      # 悬浮控制条组件
│   ├── core/
│   │   ├── __init__.py
│   │   ├── prompter.py      # 提词器核心逻辑（文字状态管理）
│   │   ├── scroller.py      # 平滑滚动引擎
│   │   └── text_parser.py   # 文本解析与排版
│   ├── speech/
│   │   ├── __init__.py
│   │   ├── recognizer.py    # Vosk 语音识别封装
│   │   └── follower.py      # 语音跟随匹配与跳段逻辑
│   └── utils/
│       ├── __init__.py
│       ├── config.py        # 配置读写（字体、速度等持久化）
│       └── file_io.py       # 文本文件读写
├── models/                  # Vosk 模型存放（gitignore）
├── docs/                    # 项目文档
├── dev-log/                 # 开发日志
└── requirements.txt         # Python 依赖
```

## 核心模块设计

### 1. 文字排版引擎（text_parser.py）

- 输入：原始文本字符串 + 每行字数 + 字体大小
- 输出：分行列表 `List[str]`，每行不超过指定字数
- 支持中英文混排，中文按 1 字、英文单词按实际长度计

### 2. 滚动引擎（scroller.py）

- 基于 QTimer 定时刷新
- 每帧 y 偏移量增加，形成平滑滚动
- 速度映射：用户设置的速度值 → 每秒像素移动量
- 暂停/恢复控制

### 3. 语音识别（recognizer.py）

- 使用 sounddevice 捕获音频流
- 送入 Vosk 识别器，获取实时识别结果
- 返回：`(识别的文字, 置信度)`
- 采样率 16000Hz，单声道

### 4. 语音跟随（follower.py）

- 维护当前朗读位置指针
- 将识别文字与文档文字做模糊匹配
- 匹配到 → 更新位置指针，标记已读文字
- 跳段检测：当前匹配位置与上一位置距离 > 5 个字 → 触发跳转
- 防抖机制：连续 2 次确认后才跳转，避免识别错误导致误跳

### 5. 全屏窗口（fullscreen.py）

- 继承 QMainWindow，全屏显示
- 黑色背景，白色/灰色文字
- 使用 QPainter 手动绘制文字，精确控制位置和透明度
- 底部半透明悬浮控制条
- 鼠标移动显示控制条，3 秒无操作自动隐藏

## 数据流

```
麦克风 → sounddevice → Vosk → 识别文字
                                  ↓
                              follower.py
                                  ↓
                          匹配文本位置 → 更新 prompter.py 状态
                                  ↓
                          scroller.py 调整滚动偏移
                                  ↓
                          fullscreen.py 重绘画面
```

## 性能约束

- 语音识别延迟 < 500ms
- 全屏画面刷新率 ≥ 30fps
- 内存占用 < 500MB
- 模型大小 < 100MB
