import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from speech.recognizer import _build_grammar_json


class RecognizerGrammarTest(unittest.TestCase):
    def test_builds_script_biased_grammar(self):
        grammar = json.loads(_build_grammar_json("大家好，欢迎使用AI语音提词器。"))

        self.assertIn("[unk]", grammar)
        self.assertTrue(any("欢 迎 使 用" in phrase for phrase in grammar))
        self.assertLessEqual(len(grammar), 451)

    def test_empty_script_disables_grammar(self):
        self.assertEqual(_build_grammar_json("，。！？"), "")


if __name__ == "__main__":
    unittest.main()
