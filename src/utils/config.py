"""
配置持久化工具
使用 JSON 文件存储用户设置和窗口状态。
"""

import json
from pathlib import Path

# ============================================================
# 配置文件路径
# ============================================================

# 放在用户 home 目录下，不污染项目目录
CONFIG_DIR = Path.home() / ".voice_teleprompter"
CONFIG_FILE = CONFIG_DIR / "config.json"
LAST_TEXT_FILE = CONFIG_DIR / "last_text.txt"

# ============================================================
# 默认配置
# ============================================================

DEFAULT_CONFIG = {
    "font_size": 36,
    "font_bold": False,
    "words_per_line": 20,
    "scroll_speed": 5,
    "pos_percentage": 50,
    "voice_follow_enabled": False,
    "window_width": 900,
    "window_height": 700,
    "mic_device": "",
    "jump_threshold": 5,
    "scripts_dir": str(CONFIG_DIR / "scripts"),
    "auto_save": True,
    "model_path": "",
    "preserve_line_breaks": True,
}


def ensure_config_dir() -> None:
    """确保配置目录存在"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def get_scripts_dir(config: dict | None = None) -> Path:
    """获取当前文稿目录。"""
    cfg = config if config is not None else load_config()
    path = Path(cfg.get("scripts_dir") or DEFAULT_CONFIG["scripts_dir"]).expanduser()
    return path


def get_configured_model_path(config: dict | None = None) -> Path | None:
    """获取用户设置的语音模型目录。未设置或路径无效时返回 None。"""
    cfg = config if config is not None else load_config()
    raw_path = str(cfg.get("model_path") or "").strip()
    if not raw_path:
        return None
    path = Path(raw_path).expanduser()
    if path.is_dir():
        return path
    return None


def load_config() -> dict:
    """
    加载用户配置。如果配置文件不存在，返回默认配置。

    Returns:
        配置字典
    """
    ensure_config_dir()
    if not CONFIG_FILE.exists():
        return dict(DEFAULT_CONFIG)

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        # 合并：用默认值补全可能缺失的键
        config = dict(DEFAULT_CONFIG)
        config.update(saved)
        return config
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_CONFIG)


def save_config(config: dict) -> None:
    """
    保存用户配置。

    Args:
        config: 配置字典
    """
    ensure_config_dir()
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except OSError:
        pass  # 静默失败，不影响使用


def save_last_text(text: str) -> None:
    """
    保存最后编辑的文本（用于下次打开恢复）。

    Args:
        text: 文本内容
    """
    ensure_config_dir()
    try:
        with open(LAST_TEXT_FILE, "w", encoding="utf-8") as f:
            f.write(text)
    except OSError:
        pass


def load_last_text() -> str:
    """
    加载上次保存的文本。

    Returns:
        文本内容，如果没有则返回空字符串
    """
    ensure_config_dir()
    if not LAST_TEXT_FILE.exists():
        return ""
    try:
        with open(LAST_TEXT_FILE, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""
