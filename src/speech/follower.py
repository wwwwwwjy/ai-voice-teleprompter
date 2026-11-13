"""
语音跟随引擎 v2 — 滑动窗口 + 模糊匹配 + 跳段检测
"""


# 配置常量
JUMP_THRESHOLD = 5         # 偏移超此字数触发跳段
JUMP_CONFIRM_COUNT = 2     # 连续确认次数（防抖）
BUFFER_SIZE = 10           # 语音缓冲区大小（字）
MIN_MATCH_CHARS = 3        # 最少匹配字数
SEARCH_WINDOW = 500        # 局部搜索窗口大小


def _normalize_text(text: str) -> str:
    """归一化语音和稿件文本，去掉空白标点，只保留可朗读字符。"""
    chars: list[str] = []
    for ch in text:
        if '\u4e00' <= ch <= '\u9fff':
            chars.append(ch)
        elif ch.isascii() and ch.isalnum():
            chars.append(ch.lower())
    return ''.join(chars)


class TextFollower:
    """语音文字跟随器。滑动窗口匹配，支持跳段和防抖。"""

    def __init__(self, jump_threshold: int = JUMP_THRESHOLD):
        self._lines: list[str] = []
        self._flat_text = ""
        self._search_text = ""
        self._search_offsets: list[int] = []
        self._line_offsets: list[int] = []
        self._total_chars = 0
        self._total_search_chars = 0

        # 当前位置（全局字符偏移）
        self._global_pos = 0
        self._search_pos = 0

        # 语音缓冲区
        self._speech_buffer = ""
        self._last_partial = ""

        # 跳段防抖
        self._jump_count = 0

        # 可配置阈值
        self._jump_threshold = jump_threshold

    # ================================================================
    # 文档加载
    # ================================================================

    def load_document(self, lines: list[str]):
        self._lines = list(lines)
        self._line_offsets = []
        self._search_offsets = []
        offset = 0
        for line in lines:
            self._line_offsets.append(offset)
            for idx, ch in enumerate(line):
                normalized = _normalize_text(ch)
                if normalized:
                    self._search_offsets.append(offset + idx)
            offset += len(line)
        self._flat_text = ''.join(lines)
        self._search_text = _normalize_text(self._flat_text)
        self._total_chars = len(self._flat_text)
        self._total_search_chars = len(self._search_text)
        self._global_pos = 0
        self._search_pos = 0
        self._speech_buffer = ""
        self._last_partial = ""
        self._jump_count = 0

    # ================================================================
    # 核心匹配
    # ================================================================

    def feed_text(self, recognized: str, is_final: bool = False) -> dict | None:
        """
        输入识别文字，返回匹配结果。

        Returns:
            dict with line_idx, char_idx, is_jump  or None
        """
        if not recognized or not self._search_text:
            return None

        text = _normalize_text(recognized)
        if not text:
            return None

        # Vosk partial 通常是累计文本，这里只取相对上一次 partial 的增量。
        chunk = text
        if not is_final:
            if self._last_partial and text.startswith(self._last_partial):
                chunk = text[len(self._last_partial):]
            self._last_partial = text
        else:
            if self._last_partial and text.startswith(self._last_partial):
                chunk = text[len(self._last_partial):]
            self._last_partial = ""

        if not chunk:
            return None

        self._speech_buffer += chunk
        if len(self._speech_buffer) > BUFFER_SIZE:
            self._speech_buffer = self._speech_buffer[-BUFFER_SIZE:]

        if len(self._speech_buffer) < MIN_MATCH_CHARS:
            return None

        # 先局部搜索
        best_pos = self._search(self._speech_buffer, local=True)

        # 局部没找到，全局搜索
        if best_pos is None:
            best_pos = self._search(self._speech_buffer, local=False)

        if best_pos is None:
            return None

        # 计算距离
        distance = best_pos - self._search_pos
        is_jump = abs(distance) > self._jump_threshold

        # 跳段防抖
        if is_jump:
            self._jump_count += 1
            if self._jump_count < JUMP_CONFIRM_COUNT:
                return None  # 等待确认
            self._jump_count = 0
        else:
            self._jump_count = 0

        # 更新位置到本次匹配缓冲区的末尾，更贴近正在朗读的位置。
        current_search_pos = min(
            best_pos + len(self._speech_buffer) - 1,
            max(0, self._total_search_chars - 1)
        )
        self._search_pos = current_search_pos + 1
        original_pos = self._search_to_original(current_search_pos)
        self._global_pos = original_pos

        # 转换为行列
        line_idx, char_idx = self._global_to_line_char(original_pos)

        return {
            "line_idx": line_idx,
            "char_idx": char_idx,
            "is_jump": is_jump,
        }

    # ================================================================
    # 滑动窗口搜索
    # ================================================================

    def _search(self, pattern: str, local: bool = True) -> int | None:
        """搜索 pattern 在文档中的最佳匹配位置。"""
        if len(pattern) < MIN_MATCH_CHARS:
            return None

        # 确定搜索范围
        if local:
            start = max(0, self._search_pos - SEARCH_WINDOW)
            end = min(self._total_search_chars, self._search_pos + SEARCH_WINDOW)
        else:
            start = 0
            end = self._total_search_chars

        region = self._search_text[start:end]
        if len(region) < MIN_MATCH_CHARS:
            return None

        exact = region.find(pattern)
        if exact >= 0:
            return start + exact

        best_pos = None
        best_score = 0.0

        max_i = max(0, len(region) - MIN_MATCH_CHARS + 1)

        for i in range(max_i):
            window = region[i:i + len(pattern)]
            score = self._char_match_score(pattern, window)

            if score > best_score:
                best_score = score
                best_pos = start + i

                # 精确匹配 → 立即返回
                if score >= 1.0:
                    return best_pos

        return best_pos if best_score >= 0.72 else None

    @staticmethod
    def _char_match_score(a: str, b: str) -> float:
        """返回短文本相似度，允许少量漏字或错字。"""
        if not a or not b:
            return 0.0
        matches = 0
        for ca, cb in zip(a, b):
            if ca == cb:
                matches += 1
        positional_score = matches / max(len(a), len(b))
        coverage_score = TextFollower._subsequence_score(a, b)
        return max(positional_score, coverage_score)

    @staticmethod
    def _subsequence_score(a: str, b: str) -> float:
        """衡量 a 有多少字符能按顺序出现在 b 中。"""
        if not a or not b:
            return 0.0
        j = 0
        for ch in b:
            if j < len(a) and a[j] == ch:
                j += 1
        return j / len(a)

    # ================================================================
    # 坐标转换
    # ================================================================

    def _global_to_line_char(self, global_pos: int) -> tuple[int, int]:
        for i in range(len(self._line_offsets) - 1, -1, -1):
            if global_pos >= self._line_offsets[i]:
                return (i, global_pos - self._line_offsets[i])
        return (0, 0)

    def _search_to_original(self, search_pos: int) -> int:
        if not self._search_offsets:
            return 0
        idx = max(0, min(search_pos, len(self._search_offsets) - 1))
        return self._search_offsets[idx]

    def get_current_line(self) -> int:
        line_idx, _ = self._global_to_line_char(self._global_pos)
        return line_idx

    def get_current_position(self) -> tuple[int, int]:
        return self._global_to_line_char(self._global_pos)

    def advance_by_chars(self, count: int) -> tuple[int, int]:
        """按稿件字符数向前推进，用于识别暂时滞后时的语速辅助跟随。"""
        if count <= 0 or not self._flat_text:
            return self.get_current_position()
        self._global_pos = min(self._total_chars - 1, self._global_pos + count)
        self._search_pos = self._original_to_search(self._global_pos)
        return self.get_current_position()

    def set_position(self, line_idx: int, char_idx: int = 0):
        if line_idx < len(self._line_offsets):
            self._global_pos = self._line_offsets[line_idx] + char_idx
            self._search_pos = self._original_to_search(self._global_pos)
            self._speech_buffer = ""
            self._last_partial = ""
            self._jump_count = 0

    def reset(self):
        self._global_pos = 0
        self._search_pos = 0
        self._speech_buffer = ""
        self._last_partial = ""
        self._jump_count = 0

    def _original_to_search(self, global_pos: int) -> int:
        for i, original_pos in enumerate(self._search_offsets):
            if original_pos >= global_pos:
                return i
        return max(0, len(self._search_offsets) - 1)
