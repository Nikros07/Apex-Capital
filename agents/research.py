from typing import Callable, Optional

from agents.base import BaseAgent

PERSONALITY = (
    "You are Alex, research analyst at Apex Capital. You are hyperactive, always online, "
    "and you find what everyone else misses — the obscure filing, the unusual options flow, "
    "the thing buried on page 12. You write with energy and informality. You always say "
    "'okay but check this out' when you find something important. You never sleep."
)


class AlexAgent(BaseAgent):
    def __init__(self, broadcast: Optional[Callable] = None):
        super().__init__("Alex", PERSONALITY, broadcast)

    async def analyze(self, ticker: str, macro_context: dict = None) -> dict:
        await self._broadcast("agent_status", {
            "status": "working",
            "ticker": ticker,
            "message": f"Digging for intel on {ticker}...",
        })

        search_results = await self.search_multiple([
            f"{ticker} news today breaking latest",
            f"{ticker} short interest float short squeeze data",
            f"{ticker} SEC filing insider trading 13D 13G Form 4",
            f"{ticker} unusual options activity dark pool flow",
            f"{ticker} CEO interview earnings guidance outlook",
        ])
        search_text = self._format_search_results(search_results)

        macro_text = ""
        if macro_context:
            macro_text = f"\nMacro backdrop: {macro_context.get('market_regime', 'unknown')} regime."

        system_prompt = (
            "Analyze this research data. Output ONLY valid JSON:\n"
            '{"summary":"2-3 sentence summary of key findings",'
            '"catalysts":["3-5 catalysts"],'
            '"risks":["3-5 risks"],'
            '"red_flags":["any red flags, empty if none"],'
            '"sentiment_score":5,'
            '"sources":["key headlines"],'
            '"signal":"STRONG_BUY|BUY|NEUTRAL|SELL|STRONG_SELL",'
            '"conviction":5,'
            '"insider_activity":"buying|selling|neutral|unknown",'
            '"short_interest":"high|moderate|low|unknown"}'
        )

        user_msg = (
            f"Ticker: {ticker}\nResearch Data:\n{search_text}"
            f"{macro_text}\n\nWhat have you found?"
        )

        response = await self.call_llm(system_prompt, user_msg)
        default = {
            "summary": "Research data is limited. Standard analysis applies.",
            "catalysts": ["Earnings announcement", "Industry tailwinds", "Market catalyst"],
            "risks": ["Market volatility", "Regulatory changes", "Competition"],
            "red_flags": [],
            "sentiment_score": 5,
            "sources": [],
            "signal": "NEUTRAL",
            "conviction": 4,
            "insider_activity": "unknown",
            "short_interest": "unknown",
        }
        result = self._parse_json(response, default)
        result["ticker"] = ticker
        result["raw_sources"] = search_results[:5]

        await self._broadcast("agent_done", {
            "status": "done",
            "ticker": ticker,
            "signal": result.get("signal"),
            "report": result,
        })
        return result
