"""
提词器核心状态管理
追踪文本的已读/正在读/未读状态，维护当前朗读位置。
"""

from dataclasses import dataclass, field
from enum import Enum, auto


class CharState(Enum):
    """文字状态"""
    UNREAD = auto()    # 未读 — 白色
    READING = auto()   # 正在读 — 白色 + 下划线
    READ = auto()      # 已读 — 灰色/半透明


@dataclass
class PrompterState:
    """提词器状态管理"""
    text: str = ""                              # 原始文本
    lines: list[str] = field(default_factory=list)  # 分行后的文本
    char_states: list[CharState] = field(default_factory=list)  # 每行状态
    current_line: int = 0                       # 当前朗读行索引
    current_char_in_line: int = 0               # 当前行内字符位置
    total_chars: int = 0                        # 总字符数

    def load_text(self, text: str, lines: list[str]):
        """加载文本"""
        self.text = text
        self.lines = lines
        self.total_chars = sum(len(line) for line in lines)
        self.current_line = 0
        self.current_char_in_line = 0

        # 初始化所有行状态为未读
        self.char_states = [CharState.UNREAD] * len(lines)

    def set_current_position(self, line_idx: int, char_idx: int = 0):
        """
        设置当前朗读位置。
        该位置之前的行标记为已读，该行标记为正在读，之后为未读。
        """
        if line_idx < 0 or line_idx >= len(self.lines):
            return

        self.current_line = line_idx
        self.current_char_in_line = char_idx

        for i in range(len(self.lines)):
            if i < line_idx:
                self.char_states[i] = CharState.READ
            elif i == line_idx:
                self.char_states[i] = CharState.READING
            else:
                self.char_states[i] = CharState.UNREAD

    def advance_one_char(self) -> bool:
        """
        向前推进一个字符。返回 False 表示已到达末尾。
        """
        if self.current_line >= len(self.lines):
            return False

        line = self.lines[self.current_line]
        self.current_char_in_line += 1

        if self.current_char_in_line >= len(line):
            # 当前行读完，标记为已读
            self.char_states[self.current_line] = CharState.READ
            self.current_line += 1
            self.current_char_in_line = 0

            if self.current_line < len(self.lines):
                self.char_states[self.current_line] = CharState.READING
            return self.current_line < len(self.lines)

        return True

    def jump_to_position(self, line_idx: int, char_idx: int = 0):
        """跳转到指定位置（用于智能跳段）"""
        self.set_current_position(line_idx, char_idx)

    def get_read_progress(self) -> float:
        """获取已读进度百分比"""
        if self.total_chars == 0:
            return 0.0
        read_count = sum(
            len(self.lines[i]) for i, s in enumerate(self.char_states)
            if s == CharState.READ
        )
        # 加上当前行已读字符
        if (self.current_line < len(self.lines) and
                self.char_states[self.current_line] == CharState.READING):
            read_count += self.current_char_in_line
        return read_count / self.total_chars

    def reset(self):
        """重置状态"""
        self.current_line = 0
        self.current_char_in_line = 0
        if self.lines:
            self.char_states = [CharState.UNREAD] * len(self.lines)
            if self.lines:
                self.char_states[0] = CharState.READING
