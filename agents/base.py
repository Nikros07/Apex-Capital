import asyncio
import json
import os
import re
from typing import Callable, Optional

import httpx

from utils.key_manager import KeyManager

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Gemini free tier — last-resort fallback once every OpenRouter model/key
# combo above is rate-limited or unavailable. Generous free daily quota,
# separate from OpenRouter's limits.
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_MODELS = ["gemini-2.0-flash", "gemini-1.5-flash"]

# All free-tier models on OpenRouter — no credit needed, no balance required.
# Rotated automatically when one is rate-limited or unavailable.
FREE_MODELS = [
    "meta-llama/llama-3.1-8b-instruct:free",
    "meta-llama/llama-3.2-3b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
    "google/gemma-3-12b-it:free",
    "google/gemma-3-4b-it:free",
    "qwen/qwen-2.5-7b-instruct:free",
    "deepseek/deepseek-r1:free",
    "nousresearch/hermes-3-llama-3.1-8b:free",
]
MODEL = FREE_MODELS[0]  # default — overridden per-call if rate-limited


class BaseAgent:
    def __init__(self, name: str, personality_header: str,
                 broadcast: Optional[Callable] = None):
        self.name = name
        self.personality_header = personality_header
        self.broadcast = broadcast
        self.km = KeyManager.get_instance()
        self.km.assign_key(name)

    async def _broadcast(self, event_type: str, data: dict):
        if not self.broadcast:
            return
        msg = {"type": event_type, "agent": self.name, **data}
        try:
            if asyncio.iscoroutinefunction(self.broadcast):
                await self.broadcast(msg)
            else:
                self.broadcast(msg)
        except Exception:
            pass

    async def call_llm(self, system_prompt: str, user_message: str,
                       max_retries: int = 3) -> str:
        full_system = f"{self.personality_header}\n\n{system_prompt}"

        # Try every free model once — move to next on rate-limit / error
        # Cap at len(FREE_MODELS) unique attempts to keep pipeline fast
        model_index = 0

        for attempt in range(len(FREE_MODELS)):
            key = self.km.get_key(self.name)
            if key == "__no_key__":
                return json.dumps({"error": "No OpenRouter API key configured. Add OPENROUTER_KEY_1 in Railway Variables."})

            model = FREE_MODELS[model_index % len(FREE_MODELS)]

            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        OPENROUTER_URL,
                        headers={
                            "Authorization": f"Bearer {key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://apexcapital.ai",
                            "X-Title": "Apex Capital Management",
                        },
                        json={
                            "model": model,
                            "messages": [
                                {"role": "system", "content": full_system},
                                {"role": "user", "content": user_message},
                            ],
                            "temperature": 0.7,
                            "max_tokens": 800,
                        },
                    )

                    if resp.status_code == 429:
                        # Rate-limited on this model → rotate key AND model
                        self.km.rotate_key(self.name)
                        model_index += 1
                        await asyncio.sleep(1)
                        continue

                    if resp.status_code in (402, 403):
                        # Payment / permission error — skip this model entirely
                        model_index += 1
                        continue

                    if resp.status_code != 200:
                        model_index += 1
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2)
                        continue

                    data = resp.json()
                    choices = data.get("choices") or []
                    if not choices:
                        model_index += 1
                        continue

                    content = (choices[0].get("message") or {}).get("content", "").strip()
                    if content:
                        return content
                    # Empty content — try next model
                    model_index += 1
                    continue

            except httpx.TimeoutException:
                model_index += 1
                await asyncio.sleep(1)
                continue
            except Exception as e:
                model_index += 1
                await asyncio.sleep(1)
                continue

        # All OpenRouter free models/keys exhausted — try Gemini before giving up.
        gemini_result = await self._call_gemini(full_system, user_message)
        if gemini_result is not None:
            return gemini_result

        return json.dumps({"error": "all free models exhausted or rate-limited"})

    async def _call_gemini(self, full_system: str, user_message: str) -> Optional[str]:
        gemini_keys = self.km.get_gemini_keys()
        if not gemini_keys:
            return None

        for key in gemini_keys:
            for model in GEMINI_MODELS:
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        resp = await client.post(
                            GEMINI_URL.format(model=model),
                            params={"key": key},
                            json={
                                "system_instruction": {"parts": [{"text": full_system}]},
                                "contents": [{"role": "user", "parts": [{"text": user_message}]}],
                                "generationConfig": {"temperature": 0.7, "maxOutputTokens": 800},
                            },
                        )

                        if resp.status_code != 200:
                            # 429 rate-limit, 4xx/5xx — try next model/key
                            continue

                        data = resp.json()
                        candidates = data.get("candidates") or []
                        if not candidates:
                            continue
                        parts = (candidates[0].get("content") or {}).get("parts") or []
                        content = "".join(p.get("text", "") for p in parts).strip()
                        if content:
                            return content

                except Exception:
                    continue

        return None

    async def search(self, query: str) -> list[dict]:
        """
        Search with automatic fallback chain:
          1. Tavily (if TAVILY_API_KEY set and credits remain)
          2. DuckDuckGo (free, no key needed)
        """
        key = os.getenv("TAVILY_API_KEY", "")
        if key:
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(
                        "https://api.tavily.com/search",
                        json={
                            "api_key": key,
                            "query": query,
                            "search_depth": "basic",
                            "max_results": 5,
                            "include_answer": True,
                        },
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        results = data.get("results", [])
                        if data.get("answer"):
                            results.insert(0, {
                                "title": "Summary",
                                "content": data["answer"],
                                "url": "",
                            })
                        return results
                    # Any non-200 (402 credits, 429 rate limit, 5xx, etc.) → DDG
            except Exception:
                pass

        # Free fallback — DuckDuckGo (no API key, no credits)
        return await self._search_ddg(query)

    async def _search_ddg(self, query: str) -> list[dict]:
        """DuckDuckGo search — completely free, no key required."""
        loop = asyncio.get_running_loop()
        try:
            def _ddg_sync():
                from duckduckgo_search import DDGS
                with DDGS() as ddgs:
                    hits = list(ddgs.text(query, max_results=5))
                return [
                    {
                        "title": h.get("title", ""),
                        "content": h.get("body", "")[:400],
                        "url": h.get("href", ""),
                    }
                    for h in hits
                ]
            return await loop.run_in_executor(None, _ddg_sync)
        except Exception as e:
            print(f"[Search] DuckDuckGo fallback failed for '{query}': {e}")
            return []

    async def search_multiple(self, queries: list[str]) -> list[dict]:
        tasks = [self.search(q) for q in queries]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        combined = []
        for r in results:
            if isinstance(r, list):
                combined.extend(r)
        return combined

    def _format_search_results(self, results: list[dict]) -> str:
        if not results:
            return "No search results available."
        lines = []
        for r in results[:8]:
            title = r.get("title", "")
            content = r.get("content", "")[:300]
            lines.append(f"• {title}: {content}")
        return "\n".join(lines)

    def _parse_json(self, text: str, default: dict) -> dict:
        text = text.strip()
        try:
            return json.loads(text)
        except Exception:
            pass
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
        return default
