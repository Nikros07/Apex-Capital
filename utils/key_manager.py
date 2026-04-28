import os
from typing import Optional


class KeyManager:
    _instance: Optional["KeyManager"] = None

    def __init__(self):
        self._keys: list[str] = []
        for i in range(1, 6):
            key = os.getenv(f"OPENROUTER_KEY_{i}", "").strip()
            if key:
                self._keys.append(key)
        if not self._keys:
            fallback = os.getenv("OPENROUTER_API_KEY", "").strip()
            if fallback:
                self._keys.append(fallback)
        if not self._keys:
            raise ValueError(
                "No OpenRouter API keys found. Set OPENROUTER_KEY_1 through OPENROUTER_KEY_5 in .env"
            )
        self._agent_assignments: dict[str, str] = {}
        self._round_robin_idx: int = 0

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
