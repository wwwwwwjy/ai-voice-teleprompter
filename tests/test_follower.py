import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from speech.follower import TextFollower


class TextFollowerTest(unittest.TestCase):
    def test_matches_across_punctuation(self):
        follower = TextFollower(jump_threshold=20)
        follower.load_document(["大家好，欢迎使用AI语音提词器。"])

        result = follower.feed_text("欢迎使用", is_final=True)

        self.assertIsNotNone(result)
        self.assertEqual(result["line_idx"], 0)
        self.assertGreaterEqual(result["char_idx"], 3)

    def test_partial_text_uses_increment_only(self):
        follower = TextFollower(jump_threshold=20)
        follower.load_document(["今天天气很好我们一起去录制视频"])

        first = follower.feed_text("今天天气", is_final=False)
        second = follower.feed_text("今天天气很好", is_final=False)

        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertGreaterEqual(second["char_idx"], first["char_idx"])

    def test_current_position_tracks_match_end(self):
        follower = TextFollower(jump_threshold=20)
        follower.load_document(["今天天气很好"])

        follower.feed_text("今天天气", is_final=True)
        line_idx, char_idx = follower.get_current_position()

        self.assertEqual(line_idx, 0)
        self.assertEqual(char_idx, 3)

    def test_advance_by_chars_moves_position(self):
        follower = TextFollower(jump_threshold=20)
        follower.load_document(["今天天气很好"])

        line_idx, char_idx = follower.advance_by_chars(4)

        self.assertEqual(line_idx, 0)
        self.assertEqual(char_idx, 4)

    def test_repeated_final_after_partial_does_not_duplicate_buffer(self):
        follower = TextFollower(jump_threshold=20)
        follower.load_document(["今天我们测试语音跟随功能"])

        follower.feed_text("今天我们", is_final=False)
        result = follower.feed_text("今天我们", is_final=True)

        self.assertIsNone(result)

    def test_set_position_resets_partial_state(self):
        follower = TextFollower(jump_threshold=20)
        follower.load_document(["第一句内容", "第二句内容"])

        follower.feed_text("第一句", is_final=False)
        follower.set_position(1, 0)
        result = follower.feed_text("第二句", is_final=False)

        self.assertIsNotNone(result)
        self.assertEqual(result["line_idx"], 1)


if __name__ == "__main__":
    unittest.main()
