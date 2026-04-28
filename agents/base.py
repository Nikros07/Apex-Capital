import asyncio
import json
import os
import re
from typing import Callable, Optional

import httpx

from utils.key_manager import KeyManager

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "meta-llama/llama-3.1-8b-instruct:free"


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

        for attempt in range(max_retries):
            key = self.km.get_key(self.name)
            try:
                async with httpx.AsyncClient(timeout=90.0) as client:
                    resp = await client.post(
                        OPENROUTER_URL,
                        headers={
                            "Authorization": f"Bearer {key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://apexcapital.ai",
                            "X-Title": "Apex Capital Management",
                        },
                        json={
                            "model": MODEL,
                            "messages": [
                                {"role": "system", "content": full_system},
                                {"role": "user", "content": user_message},
                            ],
                            "temperature": 0.7,
                            "max_tokens": 1024,
                        },
                    )

                    if resp.status_code == 429:
                        self.km.rotate_key(self.name)
                        await asyncio.sleep(2)
                        continue

                    if resp.status_code != 200:
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2)
                            continue
                        return json.dumps({"error": f"API error {resp.status_code}"})

                    data = resp.json()
                    return data["choices"][0]["message"]["content"].strip()

            except httpx.TimeoutException:
                if attempt < max_retries - 1:
                    await asyncio.sleep(3)
                    continue
                return json.dumps({"error": "timeout"})
            except Exception as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
                    continue
                return json.dumps({"error": str(e)})

        return json.dumps({"error": "max retries exceeded"})

    async def search(self, query: str) -> list[dict]:
        key = os.getenv("TAVILY_API_KEY", "")
        if not key:
            return []
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
        except Exception:
            pass
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
