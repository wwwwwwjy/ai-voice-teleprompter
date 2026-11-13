"""
文字解析与排版引擎
将原始文本按屏幕像素宽度自动折行，支持中英文混排。
"""


def parse_text(text: str, max_pixel_width: int,
               font_metrics=None, preserve_line_breaks: bool = True) -> list[str]:
    """
    将文本按指定像素宽度拆分。

    手动换行是强制分行边界；行内文字仍会按像素宽度自动折行。
    连续换行会生成空行，因此原稿的段落间距可以完整保留。

    参数：
        text: 原始文本（保留换行与段落）
        max_pixel_width: 每行最大像素宽度
        font_metrics: QFontMetrics 对象（用于测量文字像素宽度）

    返回：行列表
    """
    if not text:
        return []

    normalized = text.replace('\r\n', '\n').replace('\r', '\n')
    if not preserve_line_breaks:
        normalized = normalized.replace('\n', '')
        if not normalized:
            return []
    lines: list[str] = []

    for paragraph in normalized.split('\n'):
        # 空段落也必须占一行，才能保留用户输入的段落间距。
        if paragraph == '':
            lines.append('')
            continue

        current_line: list[str] = []
        current_width = 0.0
        for ch in paragraph:
            if font_metrics is not None:
                char_width = font_metrics.horizontalAdvance(ch)
            else:
                char_width = _estimate_char_width(ch)

            if current_line and current_width + char_width > max_pixel_width:
                lines.append(''.join(current_line))
                current_line = []
                current_width = 0.0

            current_line.append(ch)
            current_width += char_width

        lines.append(''.join(current_line))

    return lines


def _estimate_char_width(ch: str) -> float:
    """
    估算字符宽度（无 QFontMetrics 时的降级方案）。
    中文字符约为英文字符的 2 倍宽。
    """
    if '一' <= ch <= '鿿' or '　' <= ch <= '〿':
        return 2.0
    if ch.isascii():
        return 1.0
    return 2.0  # 其他全角字符
