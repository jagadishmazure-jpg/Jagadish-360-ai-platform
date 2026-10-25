"""Model backends behind the gateway. All speak the OpenAI chat-completions shape.

- OpenAICompatBackend: OpenAI, Azure OpenAI, Ollama and vLLM (all expose /v1/chat/completions or the Azure variant).
- LlamaCppBackend: an open GGUF model in-process on CPU (llama-cpp-python, optional dependency).
- StubBackend: deterministic, offline; used by CI so tests never need a key or a model file.
Keys come only from environment variables and are never logged or returned.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from .guardrails import safe_error


@dataclass
class Completion:
    text: str
    model: str
    tokens_in: int
    tokens_out: int
    latency_s: float


class BackendError(RuntimeError):
    pass


class CircuitBreaker:
    """Opens after `threshold` consecutive failures; half-opens after `cooldown_s`."""

    def __init__(self, threshold: int = 3, cooldown_s: float = 30.0, clock=time.monotonic):
        self.threshold, self.cooldown_s, self.clock = threshold, cooldown_s, clock
        self.failures, self.opened_at = 0, None

    @property
    def open(self) -> bool:
        if self.opened_at is None:
            return False
        if self.clock() - self.opened_at >= self.cooldown_s:
            return False  # half-open: allow one try
        return True

    def success(self) -> None:
        self.failures, self.opened_at = 0, None

    def failure(self) -> None:
        self.failures += 1
        if self.failures >= self.threshold:
            self.opened_at = self.clock()


@dataclass
class Backend:
    name: str
    kind: str  # "closed" | "open"
    quality: float  # prior quality score 0-1 from results/live_eval.json (or a default)
    breaker: CircuitBreaker = field(default_factory=CircuitBreaker)

    def complete(self, messages: list[dict], max_tokens: int = 256, temperature: float = 0.0) -> Completion:
        raise NotImplementedError


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


@dataclass
class StubBackend(Backend):
    """Deterministic offline model. Answers from a small lookup, else echoes a summary."""

    answers: dict[str, str] = field(default_factory=dict)
    fail_times: int = 0

    def complete(self, messages, max_tokens=256, temperature=0.0):
        if self.fail_times > 0:
            self.fail_times -= 1
            raise BackendError("stub transient failure")
        q = messages[-1]["content"]
        text = next((a for k, a in self.answers.items() if k.lower() in q.lower()), f"[{self.name}] {q[:80]}")
        tin = sum(_approx_tokens(m["content"]) for m in messages)
        return Completion(text, self.name, tin, _approx_tokens(text), 0.0)


@dataclass
class OpenAICompatBackend(Backend):
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    key_env: str | None = "AZURE_OPENAI_API_KEY"
    azure_api_version: str | None = None  # set for Azure OpenAI; then model = deployment name
    timeout_s: float = 60.0
    retries: int = 2
    max_calls: int | None = None
    calls: int = 0

    def _request(self, payload: dict) -> dict:
        if self.azure_api_version:
            url = f"{self.base_url.rstrip('/')}/openai/deployments/{self.model}/chat/completions?api-version={self.azure_api_version}"
            headers = {"api-key": os.environ.get(self.key_env or "", "")}
        else:
            url = f"{self.base_url.rstrip('/')}/chat/completions"
            key = os.environ.get(self.key_env or "", "") if self.key_env else ""
            headers = {"Authorization": f"Bearer {key}"} if key else {}
        if not url.startswith(("https://", "http://127.0.0.1", "http://localhost", "http://ollama", "http://vllm")):
            raise BackendError("refusing non-https remote endpoint")
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", **headers})  # noqa: S310
        with urllib.request.urlopen(req, timeout=self.timeout_s) as r:  # noqa: S310 (scheme checked above)
            return json.loads(r.read())

    def complete(self, messages, max_tokens=256, temperature=0.0):
        if self.max_calls is not None and self.calls >= self.max_calls:
            raise BackendError(f"call cap reached ({self.max_calls})")
        payload = {"model": self.model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
        delay = 1.0
        for attempt in range(self.retries + 1):
            t0 = time.perf_counter()
            try:
                self.calls += 1
                j = self._request(payload)
                u = j.get("usage", {})
                text = j["choices"][0]["message"]["content"] or ""
                return Completion(text, self.model, u.get("prompt_tokens", 0), u.get("completion_tokens", 0), time.perf_counter() - t0)
            except urllib.error.HTTPError as e:
                if e.code not in (429, 500, 502, 503, 504) or attempt == self.retries:
                    raise BackendError(f"HTTP {e.code}") from None
            except (urllib.error.URLError, TimeoutError) as e:
                if attempt == self.retries:
                    raise BackendError(safe_error(e)) from None
            time.sleep(delay)
            delay *= 2
        raise BackendError("unreachable")


@dataclass
class LlamaCppBackend(Backend):
    model_path: str = ""
    n_ctx: int = 1024
    n_threads: int | None = None
    _llm: object = None

    def _load(self):
        if self._llm is None:
            from llama_cpp import Llama  # optional dependency

            self._llm = Llama(self.model_path, n_ctx=self.n_ctx, n_threads=self.n_threads, verbose=False, seed=0)
        return self._llm

    def complete(self, messages, max_tokens=256, temperature=0.0):
        llm = self._load()
        t0 = time.perf_counter()
        r = llm.create_chat_completion(messages=messages, max_tokens=max_tokens, temperature=temperature, seed=0)
        u = r["usage"]
        return Completion(r["choices"][0]["message"]["content"] or "", self.name, u["prompt_tokens"], u["completion_tokens"], time.perf_counter() - t0)


def from_config(cfg: dict) -> Backend:
    """Build a backend from a config dict (see config/gateway.example.json)."""
    t = cfg["type"]
    common = {"name": cfg["name"], "kind": cfg.get("kind", "open"), "quality": cfg.get("quality", 0.5)}
    if t == "stub":
        return StubBackend(**common, answers=cfg.get("answers", {}))
    if t == "llamacpp":
        return LlamaCppBackend(**common, model_path=os.path.expanduser(cfg["model_path"]))
    if t in ("openai", "azure-openai", "ollama", "vllm"):
        return OpenAICompatBackend(
            **common,
            base_url=cfg["base_url"],
            model=cfg["model"],
            key_env=cfg.get("key_env"),
            azure_api_version=cfg.get("api_version") if t == "azure-openai" else None,
            max_calls=cfg.get("max_calls"),
        )
    raise ValueError(f"unknown backend type {t}")
