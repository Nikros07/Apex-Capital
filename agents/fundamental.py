import asyncio
from typing import Callable, Optional

from agents.base import BaseAgent
from data.market import fetch_current_price, fetch_info

PERSONALITY = (
    "You are Sophie, fundamental analyst at Apex Capital. You are a devoted student of "
    "Buffett and Munger. You love durable moats, honest management, and free cash flow. "
    "You are deeply skeptical of hype, loss-making companies, and anyone who says "
    "'this time is different.' You always anchor to intrinsic value."
)


class SophieAgent(BaseAgent):
    def __init__(self, broadcast: Optional[Callable] = None):
        super().__init__("Sophie", PERSONALITY, broadcast)

    async def analyze(self, ticker: str, macro_context: dict = None) -> dict:
        await self._broadcast("agent_status", {
            "status": "working",
            "ticker": ticker,
            "message": f"Analyzing fundamentals for {ticker}...",
        })

        info, current_price = await asyncio.gather(
            fetch_info(ticker),
            fetch_current_price(ticker),
        )

        financials = self._extract_financials(info, current_price)

        search_results = await self.search_multiple([
            f"{ticker} earnings report latest quarterly results",
            f"{ticker} analyst price target consensus Wall Street",
            f"{ticker} competitive moat durable advantage",
            f"{ticker} management insider ownership buybacks",
        ])
        search_text = self._format_search_results(search_results)

        macro_text = ""
        if macro_context:
            macro_text = f"\nMacro: {macro_context.get('summary', '')}"

        system_prompt = (
            "Analyze fundamental value. Output ONLY valid JSON:\n"
            '{"signal":"STRONG_BUY|BUY|NEUTRAL|SELL|STRONG_SELL",'
            '"conviction":5,'
            '"fair_value_eur":0.0,'
            '"upside_pct":0.0,'
            '"thesis":"4-5 sentence fundamental thesis",'
            '"moat_strength":"wide|narrow|none",'
            '"valuation":"cheap|fair|expensive|very_expensive",'
            '"quality_score":5,'
            '"key_risk":"primary fundamental risk"}'
        )

        user_msg = (
            f"Ticker: {ticker}\nCurrent Price: {current_price:.4f}\n"
            f"Financials: {financials}\n\n"
            f"Research:\n{search_text}{macro_text}\n\nProvide fundamental analysis."
        )

        response = await self.call_llm(system_prompt, user_msg)
        default = {
            "signal": "NEUTRAL", "conviction": 5,
            "fair_value_eur": current_price, "upside_pct": 0.0,
            "thesis": "Limited data available for complete fundamental analysis.",
            "moat_strength": "narrow", "valuation": "fair",
            "quality_score": 5, "key_risk": "Limited financial data",
        }
        result = self._parse_json(response, default)
        result["financials"] = financials
        result["current_price"] = current_price
        result["ticker"] = ticker

        await self._broadcast("agent_done", {
            "status": "done",
            "ticker": ticker,
            "signal": result.get("signal"),
            "report": result,
        })
        return result

    def _extract_financials(self, info: dict, price: float) -> dict:
        return {
            "pe_ratio": info.get("trailingPE") or info.get("forwardPE"),
            "pb_ratio": info.get("priceToBook"),
            "eps": info.get("trailingEps"),
            "revenue_growth": info.get("revenueGrowth"),
            "debt_to_equity": info.get("debtToEquity"),
            "profit_margin": info.get("profitMargins"),
            "free_cash_flow": info.get("freeCashflow"),
            "dividend_yield": info.get("dividendYield"),
            "market_cap": info.get("marketCap"),
            "sector": info.get("sector", "Unknown"),
            "industry": info.get("industry", "Unknown"),
            "beta": info.get("beta"),
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
            "analyst_target": info.get("targetMeanPrice"),
            "recommendation": info.get("recommendationKey"),
        }
