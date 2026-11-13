"""
Vosk 离线语音识别封装
音频采集（回调）与识别处理（工作线程）分离，避免阻塞。
"""

import sys
import json
import queue
import threading
from pathlib import Path

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from utils.config import get_configured_model_path

# vosk 和 sounddevice 延迟导入（重库，启动时才加载）


def _find_model_in_dir(base: Path) -> str:
    """在指定目录查找 Vosk 模型。"""
    if not base.exists() or not base.is_dir():
        return ""
    if base.name.startswith("vosk-model") or ((base / "am").is_dir() and (base / "conf").is_dir()):
        return str(base)
    for entry in base.iterdir():
        if entry.is_dir() and (
            entry.name.startswith("vosk-model") or
            ((entry / "am").is_dir() and (entry / "conf").is_dir())
        ):
            return str(entry)
    return ""


def find_model_path() -> str:
    """动态查找 Vosk 模型路径。"""
    configured = get_configured_model_path()
    if configured is not None:
        found = _find_model_in_dir(configured)
        if found:
            return found

    if getattr(sys, 'frozen', False):
        meipass = Path(sys._MEIPASS)
        found = _find_model_in_dir(meipass / "models")
        if found:
            return found

    base_paths = [
        Path(__file__).parent.parent.parent / "models",
        Path.home() / ".voice_teleprompter" / "models",
        Path("models"),
    ]
    for base in base_paths:
        found = _find_model_in_dir(base)
        if found:
            return found

    return ""


def _normalize_for_grammar(text: str) -> str:
    chars: list[str] = []
    for ch in text:
        if '\u4e00' <= ch <= '\u9fff':
            chars.append(ch)
        elif ch.isascii() and ch.isalnum():
            chars.append(ch.lower())
    return ''.join(chars)


def _add_phrase(phrases: list[str], seen: set[str], phrase: str):
    if len(phrase) < 2 or phrase in seen:
        return
    seen.add(phrase)
    phrases.append(" ".join(phrase))


def _build_grammar_json(text: str, max_phrases: int = 450) -> str:
    """
    根据当前稿件生成 Vosk 动态语法。

    小模型通用识别容易把台词识别成近音字；提词器场景里已知稿件，
    所以把稿件短句作为候选语法可以显著降低跑偏概率。
    """
    normalized = _normalize_for_grammar(text)
    if len(normalized) < 2:
        return ""

    phrases: list[str] = []
    seen: set[str] = set()

    # 先加入较完整的短句，保留上下文。
    clause = ""
    for ch in text:
        normalized_ch = _normalize_for_grammar(ch)
        if normalized_ch:
            clause += normalized_ch
            continue
        if clause:
            for start in range(0, len(clause), 16):
                _add_phrase(phrases, seen, clause[start:start + 24])
            clause = ""
    if clause:
        for start in range(0, len(clause), 16):
            _add_phrase(phrases, seen, clause[start:start + 24])

    # 再加入滑动片段，覆盖用户从任意位置开始读的情况。
    for size in (4, 6, 8, 10, 12):
        if len(phrases) >= max_phrases:
            break
        step = max(1, size // 2)
        for start in range(0, max(1, len(normalized) - size + 1), step):
            _add_phrase(phrases, seen, normalized[start:start + size])
            if len(phrases) >= max_phrases:
                break

    # Vosk grammar 支持 [unk]，保留它可以避免完全限制死。
    phrases.append("[unk]")
    return json.dumps(phrases, ensure_ascii=False)


class SpeechRecognizer(QObject):
    """离线语音识别器。音频回调只收数据，工作线程做识别，互不阻塞。"""

    partial_result = pyqtSignal(str)
    final_result = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    status_changed = pyqtSignal(bool)
    debug_info = pyqtSignal(str)
    model_ready = pyqtSignal(bool, str)  # (success, path_or_error)

    SAMPLE_RATE = 16000
    BLOCK_SIZE = 2000
    CHANNELS = 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._model = None
        self._audio_stream = None
        self._worker_thread: threading.Thread | None = None
        self._audio_queue: queue.Queue = queue.Queue(maxsize=8)
        self._device: str | None = None
        self._result_count = 0
        self._callback_count = 0
        self._model_path = ""
        self._loader: _ModelLoader | None = None
        self._reference_text = ""
        self._grammar_json = ""

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def model_loaded(self) -> bool:
        return self._model is not None

    @property
    def model_path(self) -> str:
        return self._model_path or find_model_path()

    def set_device(self, device_name: str):
        self._device = device_name if device_name else None

    def set_reference_text(self, text: str):
        """设置当前稿件，用于约束 Vosk 优先识别稿件里的台词。"""
        self._reference_text = text or ""
        self._grammar_json = _build_grammar_json(self._reference_text)
        if self._grammar_json:
            phrase_count = max(0, len(json.loads(self._grammar_json)) - 1)
            self.debug_info.emit(f"台词热词({phrase_count})")

    def clear_model(self):
        """清除已加载模型，供用户切换模型路径后重新加载。"""
        self.stop()
        self._model = None
        self._model_path = ""

    def load_model(self) -> bool:
        import vosk
        path = find_model_path()
        if not path:
            self.error_occurred.emit("未找到语音模型，请确认 models/ 目录存在。")
            return False

        try:
            self._model = vosk.Model(path)
            self._model_path = path
            self.debug_info.emit(f"模型: {Path(path).name}")
            return True
        except Exception as e:
            self.error_occurred.emit(f"模型加载失败：{e}")
            return False

    def load_model_async(self):
        """在子线程中加载模型，完成后通过 model_ready 信号通知。"""
        if self._model is not None:
            self.model_ready.emit(True, self._model_path)
            return
        if self._loader is not None and self._loader.isRunning():
            return

        path = find_model_path()
        if not path:
            self.model_ready.emit(False, "未找到语音模型")
            return

        self._loader = _ModelLoader(path)
        self._loader.finished_signal.connect(self._on_model_loaded)
        self._loader.start()

    def _on_model_loaded(self, success: bool, data: str, model: object):
        if success:
            self._model = model
            self._model_path = data
            self.model_ready.emit(True, data)
        else:
            self.model_ready.emit(False, data)

    # ================================================================
    # 启动 / 停止
    # ================================================================

    def start(self):
        if self._running:
            return
        if self._model is None:
            if not self.load_model():
                return

        import vosk
        import sounddevice as sd

        self._running = True
        self._result_count = 0
        self._callback_count = 0
        # 清空旧队列
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break

        # 启动音频流（回调只负责把原始数据放入队列）
        device_id = None
        if self._device:
            device_id = self._find_device_by_name(self._device)

        try:
            self._audio_stream = sd.InputStream(
                samplerate=self.SAMPLE_RATE,
                blocksize=self.BLOCK_SIZE,
                device=device_id,
                channels=self.CHANNELS,
                dtype='int16',
                callback=self._audio_callback,
            )
            self._audio_stream.start()
            self.debug_info.emit("麦克风已打开")
        except sd.PortAudioError as e:
            self._running = False
            self.error_occurred.emit(
                f"无法访问麦克风：{e}\n\n"
                "请检查：系统设置 → 隐私与安全性 → 麦克风 → 允许终端/提词器"
            )
            return

        # 启动工作线程（从队列取音频数据 → Vosk 识别 → 发信号）
        self._worker_thread = threading.Thread(target=self._recognition_loop, daemon=True)
        self._worker_thread.start()
        self.status_changed.emit(True)

    def stop(self):
        self._running = False

        # 关闭音频流
        if self._audio_stream is not None:
            try:
                self._audio_stream.stop()
                self._audio_stream.close()
            except Exception:
                pass
            self._audio_stream = None

        # 等待工作线程退出
        if self._worker_thread is not None:
            self._worker_thread.join(timeout=2.0)
            self._worker_thread = None

        self.status_changed.emit(False)

    # ================================================================
    # 音频回调 — 只收数据，不做任何耗时操作
    # ================================================================

    def _audio_callback(self, indata, frames, time_info, status):
        """PortAudio 回调：仅把原始音频字节放入队列，立即返回。"""
        if not self._running:
            return

        self._callback_count += 1
        if self._callback_count % 50 == 0:
            self.debug_info.emit(f"音频({self._callback_count})")

        # 保留最新音频。队列满时丢弃最旧块，避免越识别越滞后。
        try:
            self._audio_queue.put_nowait(bytes(indata))
        except queue.Full:
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._audio_queue.put_nowait(bytes(indata))
            except queue.Full:
                pass

    # ================================================================
    # 识别工作线程 — 从队列取音频 → Vosk → 发信号
    # ================================================================

    def _recognition_loop(self):
        """工作线程：循环读取音频数据，送入 Vosk 识别器。"""
        import vosk
        grammar_json = self._grammar_json
        try:
            if grammar_json:
                rec = vosk.KaldiRecognizer(self._model, self.SAMPLE_RATE, grammar_json)
            else:
                rec = vosk.KaldiRecognizer(self._model, self.SAMPLE_RATE)
        except Exception:
            rec = vosk.KaldiRecognizer(self._model, self.SAMPLE_RATE)
        rec.SetWords(True)
        if hasattr(rec, "SetPartialWords"):
            rec.SetPartialWords(True)

        while self._running:
            try:
                audio_data = self._audio_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            try:
                # 送入 Vosk 识别
                is_final = rec.AcceptWaveform(audio_data)
                if is_final:
                    result_json = rec.Result()
                else:
                    result_json = rec.PartialResult()

                # 解析结果
                data = json.loads(result_json)
                text = data.get("text", data.get("partial", "")).strip()

                if text:
                    self._result_count += 1
                    if is_final:
                        self.final_result.emit(text)
                    else:
                        self.partial_result.emit(text)

            except json.JSONDecodeError:
                continue
            except Exception:
                continue

    # ================================================================
    # 辅助
    # ================================================================

    @staticmethod
    def _find_device_by_name(name: str) -> int | None:
        import sounddevice as sd
        try:
            devices = sd.query_devices()
            for i, dev in enumerate(devices):
                if dev['name'] == name and dev['max_input_channels'] > 0:
                    return i
        except Exception:
            pass
        return None


class _ModelLoader(QThread):
    """后台线程加载 Vosk 模型，不阻塞 UI。"""
    finished_signal = pyqtSignal(bool, str, object)

    def __init__(self, model_path: str):
        super().__init__()
        self._path = model_path

    def run(self):
        try:
            import vosk
            model = vosk.Model(self._path)
            self.finished_signal.emit(True, self._path, model)
        except BaseException as e:
            self.finished_signal.emit(False, str(e), None)
