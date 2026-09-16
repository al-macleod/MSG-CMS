"""Ollama integration.

Only HTTP transport and prompt construction live here. The rest of the
application can evolve independently of Ollama's API details.
"""

import json
import urllib.error
import urllib.request

from PyQt6.QtCore import QObject, QThread, pyqtSignal


DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "llama3.2"
DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful, privacy-conscious academic copilot. "
    "Be concise, honest, and safe."
)


def build_system_prompt(system_prompt, persona=""):
    prompt = (system_prompt or DEFAULT_SYSTEM_PROMPT).strip()
    if persona and persona.strip():
        prompt += f"\nPersona: {persona.strip()}"
    return prompt


class OllamaWorker(QObject):
    """Perform one Ollama request on a worker thread."""

    finished = pyqtSignal(str, str)
    failed = pyqtSignal(str)

    def ask(self, url, model, prompt, system):
        try:
            body = json.dumps({
                "model": model or DEFAULT_MODEL,
                "prompt": prompt,
                "system": build_system_prompt(system),
                "stream": False,
            }).encode()
            request = urllib.request.Request(
                (url or DEFAULT_OLLAMA_URL).rstrip("/") + "/api/generate",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=90) as response:
                result = json.loads(response.read().decode())
            answer = result.get("response", "").strip()
            self.finished.emit(prompt, answer or "Ollama returned an empty response.")
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            self.failed.emit(f"Could not reach Ollama: {exc}")


class OllamaClient(QObject):
    """Small async facade used by the chat UI."""

    response = pyqtSignal(str, str)
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.thread = None

    def ask(self, url, model, prompt, system_prompt, persona=""):
        self.thread = QThread()
        worker = OllamaWorker()
        worker.moveToThread(self.thread)
        self.thread.started.connect(
            lambda: worker.ask(url, model, prompt, build_system_prompt(system_prompt, persona))
        )
        worker.finished.connect(self.response)
        worker.failed.connect(self.error)
        worker.finished.connect(self.thread.quit)
        worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()
