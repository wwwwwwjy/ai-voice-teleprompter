"""文本文件读写与常见文稿格式导入工具。"""

import subprocess
import sys
from pathlib import Path


IMPORTABLE_SUFFIXES = {".txt", ".doc", ".docx", ".rtf", ".odt"}


def read_text_file(filepath: str) -> str:
    """
    读取文本文件内容。

    Args:
        filepath: 文件路径

    Returns:
        文件文本内容（字符串）

    Raises:
        FileNotFoundError: 文件不存在
        UnicodeDecodeError: 编码错误（尝试其他编码）
    """
    # 优先尝试 UTF-8
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        # 尝试 GBK（Windows 中文文件）
        with open(filepath, "r", encoding="gbk") as f:
            return f.read()


def write_text_file(filepath: str, content: str) -> None:
    """
    将文本内容写入文件（UTF-8 编码）。

    Args:
        filepath: 文件路径
        content: 要写入的文本
    """
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)


def read_importable_document(filepath: str) -> str:
    """读取 txt，或使用 macOS textutil 抽取 Word/富文本正文。"""
    path = Path(filepath)
    if path.suffix.lower() == ".txt":
        return read_text_file(str(path))
    if path.suffix.lower() not in IMPORTABLE_SUFFIXES:
        raise ValueError(f"不支持的文件类型：{path.suffix or '无扩展名'}")

    if sys.platform == "darwin":
        result = subprocess.run(
            ["/usr/bin/textutil", "-convert", "txt", "-stdout", "-encoding", "UTF-8", str(path)],
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            message = result.stderr.decode("utf-8", errors="replace").strip()
            raise ValueError(message or f"无法读取 {path.name}")
        return result.stdout.decode("utf-8", errors="replace")

    if path.suffix.lower() == ".docx":
        try:
            from docx import Document
        except ImportError as exc:
            raise ValueError("Windows 版本缺少 Word 文档解析组件") from exc
        document = Document(str(path))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)

    raise ValueError(
        f"Windows 版暂不支持旧格式 {path.suffix}，请在 Word 中另存为 DOCX 或 TXT 后导入")
