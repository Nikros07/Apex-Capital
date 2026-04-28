import asyncio
from typing import Callable, Optional

from agents.base import BaseAgent
from data.reddit_client import fetch_reddit_sentiment
from data.stocktwits_client import fetch_stocktwits_sentiment

PERSONALITY = (
    "You are Jordan, the social sentiment analyst at Apex Capital. You live on Reddit and "
    "StockTwits. You know that retail sentiment often leads institutional moves by 24-48 hours. "
    "You are not a permabull or permabear — you read the crowd and report what you see without "
    "judgment. You speak plainly and always give a crowd sentiment score."
)


class JordanAgent(BaseAgent):
    def __init__(self, broadcast: Optional[Callable] = None):
        super().__init__("Jordan", PERSONALITY, broadcast)

    async def analyze(self, ticker: str, technical_signal: str = "NEUTRAL",
                      macro_context: dict = None) -> dict:
        await self._broadcast("agent_status", {
            "status": "working",
            "ticker": ticker,
            "message": f"Scanning social channels for {ticker}...",
        })

        reddit_data, st_data = await asyncio.gather(
            fetch_reddit_sentiment(ticker),
            fetch_stocktwits_sentiment(ticker),
        )

        meme_risk = reddit_data.get("total_mentions", 0) > 50
        top_post_title = (
            reddit_data.get("top_post", {}).get("title", "N/A")
            if reddit_data.get("top_post") else "N/A"
        )
        top_msg_body = (
            st_data.get("top_message", {}).get("body", "N/A")
            if st_data.get("top_message") else "N/A"
        )

        system_prompt = (
            "Synthesize social sentiment. Output ONLY valid JSON:\n"
            '{"crowd_sentiment":"VERY_BULLISH|BULLISH|NEUTRAL|BEARISH|VERY_BEARISH",'
            '"crowd_conviction":5,'
            '"narrative":"2-3 sentences on what retail is saying and why",'
            '"contrarian_flag":false,'
            '"contrarian_note":null,'
            '"meme_risk":false,'
            '"meme_risk_note":null,'
            '"signal":"STRONG_BUY|BUY|NEUTRAL|SELL|STRONG_SELL",'
            '"conviction":5}'
        )

        user_msg = (
            f"Ticker: {ticker}\nTechnical Signal (Kai): {technical_signal}\n\n"
            f"Reddit: {reddit_data.get('total_mentions',0)} posts, "
            f"bull={reddit_data.get('bull_count',0)}, bear={reddit_data.get('bear_count',0)}, "
            f"raw_score={reddit_data.get('raw_sentiment_score',0.5)}\n"
            f"Top post: {top_post_title}\n\n"
            f"StockTwits: bullish={st_data.get('bull_pct',0)}%, "
            f"bearish={st_data.get('bear_pct',0)}%, neutral={st_data.get('neutral_pct',0)}%, "
            f"count={st_data.get('message_count',0)}\n"
            f"Top msg: {top_msg_body}\n\n"
            f"{'WSB mentions >50 — MEME RISK ACTIVE' if meme_risk else 'No meme risk'}\n\n"
            "What does the crowd say?"
        )

        response = await self.call_llm(system_prompt, user_msg)
        default = {
            "crowd_sentiment": "NEUTRAL", "crowd_conviction": 5,
            "narrative": "Social sentiment data is limited. No strong crowd signal detected.",
            "contrarian_flag": False, "contrarian_note": None,
            "meme_risk": False, "meme_risk_note": None,
            "signal": "NEUTRAL", "conviction": 3,
        }
        result = self._parse_json(response, default)

        if meme_risk and not result.get("meme_risk"):
            result["meme_risk"] = True

        crowd = result.get("crowd_sentiment", "NEUTRAL")
        if (crowd in ("VERY_BULLISH", "BULLISH") and technical_signal in ("SELL", "STRONG_SELL")) or \
           (crowd in ("VERY_BEARISH", "BEARISH") and technical_signal in ("BUY", "STRONG_BUY")):
            result["contrarian_flag"] = True
            if not result.get("contrarian_note"):
                result["contrarian_note"] = (
                    f"Crowd {crowd} conflicts with technical signal {technical_signal}"
                )

        result["ticker"] = ticker
        result["reddit_data"] = reddit_data
        result["stocktwits_data"] = st_data

        await self._broadcast("agent_done", {
            "status": "done",
            "ticker": ticker,
            "signal": result.get("signal"),
            "report": result,
        })
        return result
