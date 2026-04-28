import json
from typing import Callable, Optional

from agents.base import BaseAgent
from data.market import compute_indicators, fetch_ohlcv

PERSONALITY = (
    "You are Kai, the technical analyst at Apex Capital. You are obsessed with price action. "
    "You speak in numbers, levels, and patterns. You are slightly arrogant and often say "
    "'the tape never lies' and 'price is truth.' You distrust fundamentals. "
    "Everything is already in the chart."
)


class KaiAgent(BaseAgent):
    def __init__(self, broadcast: Optional[Callable] = None):
        super().__init__("Kai", PERSONALITY, broadcast)

    async def analyze(self, ticker: str, macro_context: dict = None) -> dict:
        await self._broadcast("agent_status", {
            "status": "working",
            "ticker": ticker,
            "message": f"Computing indicators for {ticker}...",
        })

        df = await fetch_ohlcv(ticker, period="6mo")
        if df is None or df.empty:
            await self._broadcast("agent_done", {"status": "error", "ticker": ticker, "message": "No price data"})
            return self._empty(ticker)

        indicators = compute_indicators(df)
        macro_text = ""
        if macro_context:
            macro_text = (
                f"\nMacro: {macro_context.get('market_regime', 'Unknown')} regime. "
                f"Fed: {macro_context.get('fed_stance', 'unknown')}."
            )

        system_prompt = (
            "Analyze these technical indicators. Output ONLY valid JSON:\n"
            '{"signal":"STRONG_BUY|BUY|NEUTRAL|SELL|STRONG_SELL",'
            '"conviction":5,'
            '"key_levels":{"support":0,"resistance":0,"entry_zone":0,"stop_zone":0},'
            '"thesis":"4-5 sentence technical thesis",'
            '"pattern":"chart pattern description",'
            '"momentum":"strong_bullish|bullish|neutral|bearish|strong_bearish"}'
        )

        user_msg = (
            f"Ticker: {ticker}\n"
            f"Indicators:\n{json.dumps(indicators, indent=2)}"
            f"{macro_text}\n\nAnalyze the technical picture."
        )

        response = await self.call_llm(system_prompt, user_msg)

        default = self._default(indicators)
        result = self._parse_json(response, default)
        result["indicators"] = indicators
        result["ticker"] = ticker

        await self._broadcast("agent_done", {
            "status": "done",
            "ticker": ticker,
            "signal": result.get("signal"),
            "report": result,
        })
        return result

    def _default(self, indicators: dict) -> dict:
        rsi = indicators.get("rsi", 50)
        if rsi < 35:
            sig = "BUY"
        elif rsi > 65:
            sig = "SELL"
        else:
            sig = "NEUTRAL"
        return {
            "signal": sig,
            "conviction": 5,
            "key_levels": {
                "support": indicators.get("support"),
                "resistance": indicators.get("resistance"),
                "entry_zone": indicators.get("current_price"),
                "stop_zone": indicators.get("bb_lower"),
            },
            "thesis": (
                f"RSI at {rsi:.1f} with {indicators.get('trend','unknown')} trend. "
                "Price action requires careful observation before committing capital."
            ),
            "pattern": "No clear pattern identified",
            "momentum": "neutral",
        }

    def _empty(self, ticker: str) -> dict:
        return {
            "ticker": ticker,
            "signal": "NEUTRAL",
            "conviction": 0,
            "key_levels": {},
            "thesis": "Insufficient data for technical analysis.",
            "indicators": {},
        }
