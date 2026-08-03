import os
from typing import Optional

MAX_OPENROUTER_KEYS = 5


def _collect_keys(prefix: str, count: int, single_var: str = "") -> list[str]:
    keys: list[str] = []
    for i in range(1, count + 1):
        key = os.getenv(f"{prefix}{i}", "").strip()
        # Skip empty values and placeholder values from .env.example
        if key and not key.endswith("...") and len(key) > 20:
            keys.append(key)
    if not keys and single_var:
        fallback = os.getenv(single_var, "").strip()
        if fallback and not fallback.endswith("...") and len(fallback) > 20:
            keys.append(fallback)
    return keys


class KeyManager:
    _instance: Optional["KeyManager"] = None

    def __init__(self):
        self._keys: list[str] = _collect_keys("OPENROUTER_KEY_", MAX_OPENROUTER_KEYS, "OPENROUTER_API_KEY")
        if not self._keys:
            # Don't crash startup — app still serves dashboard, LLM calls return fallback responses
            print(
                "[KeyManager] WARNING: No OpenRouter API keys found. "
                "Set OPENROUTER_KEY_1..5 in Railway Variables. LLM agents will use fallback responses."
            )
            self._keys = ["__no_key__"]
        self._agent_assignments: dict[str, str] = {}
        self._round_robin_idx: int = 0

        # Gemini keys are a separate pool — used as a last-resort fallback
        # once every free OpenRouter model/key combo is rate-limited.
        self._gemini_keys: list[str] = _collect_keys("GEMINI_KEY_", 5, "GEMINI_API_KEY")
        self._gemini_idx: int = 0

    def get_gemini_keys(self) -> list[str]:
        return list(self._gemini_keys)

    @classmethod
    def get_instance(cls) -> "KeyManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def assign_key(self, agent_name: str) -> str:
        if agent_name not in self._agent_assignments:
            key = self._keys[self._round_robin_idx % len(self._keys)]
            self._agent_assignments[agent_name] = key
            self._round_robin_idx += 1
        return self._agent_assignments[agent_name]

    def rotate_key(self, agent_name: str) -> str:
        current = self._agent_assignments.get(agent_name)
        if current in self._keys:
            idx = (self._keys.index(current) + 1) % len(self._keys)
        else:
            idx = self._round_robin_idx % len(self._keys)
        new_key = self._keys[idx]
        self._agent_assignments[agent_name] = new_key
        return new_key

    def get_key(self, agent_name: str) -> str:
        return self._agent_assignments.get(agent_name, self._keys[0])
