from typing import Callable, Optional

from agents.base import BaseAgent

PERSONALITY = (
    "You are Elena, a macro economist at Apex Capital. You are calm, data-driven, "
    "and always contextualize individual stocks within the broader market environment. "
    "You reference Fed policy, sector rotation, and global risk-off/risk-on conditions. "
    "You speak in measured, complete sentences and always close with 2 macro risks the "
    "fund should be aware of."
)


class ElenaAgent(BaseAgent):
    def __init__(self, broadcast: Optional[Callable] = None):
        super().__init__("Elena", PERSONALITY, broadcast)

    async def analyze(self) -> dict:
        await self._broadcast("agent_status", {
            "status": "working",
            "message": "Running macro analysis...",
        })

        queries = [
            "Federal Reserve interest rate decision outlook 2024 2025",
            "VIX volatility index current market fear level",
            "S&P 500 sector rotation analysis today",
            "global market risk-on risk-off sentiment indicators",
            "US GDP inflation recession probability outlook",
        ]
        results = await self.search_multiple(queries)
        search_text = self._format_search_results(results)

        system_prompt = (
            "Analyze the current macro environment. Output ONLY valid JSON:\n"
            '{"market_regime":"Risk-On|Risk-Off|Transitional",'
            '"macro_tailwinds":["3 items"],'
            '"macro_headwinds":["3 items"],'
            '"sector_outlook":{"technology":"positive|neutral|negative","energy":"...","financials":"...","healthcare":"...","consumer":"..."},'
            '"fed_stance":"hawkish|neutral|dovish",'
            '"key_risk_1":"description",'
            '"key_risk_2":"description",'
            '"summary":"2-3 sentence macro overview"}'
        )

        response = await self.call_llm(
            system_prompt,
            f"Latest macro data:\n\n{search_text}\n\nProvide your macro analysis."
        )

        default = {
            "market_regime": "Transitional",
            "macro_tailwinds": ["AI investment cycle", "Consumer resilience", "Labor market stability"],
            "macro_headwinds": ["Elevated rates", "Geopolitical risk", "Credit tightening"],
            "sector_outlook": {
                "technology": "positive", "energy": "neutral",
                "financials": "neutral", "healthcare": "positive", "consumer": "neutral",
            },
            "fed_stance": "neutral",
            "key_risk_1": "Higher-for-longer rates pressure on valuations",
            "key_risk_2": "Geopolitical escalation triggering risk-off selloff",
            "summary": "Markets in a transitional regime with mixed macro signals.",
        }

        report = self._parse_json(response, default)
        await self._broadcast("agent_done", {
            "status": "done",
            "report": report,
            "message": "Macro analysis complete",
        })
        return report
