import httpx


async def fetch_stocktwits_sentiment(ticker: str) -> dict:
    url = f"https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers={"User-Agent": "ApexCapital/1.0"})
            if resp.status_code != 200:
                return _empty(error=f"HTTP {resp.status_code}")

            data = resp.json()
            messages = data.get("messages", [])[:30]

            if not messages:
                return _empty()

            bull = bear = neutral = 0
            recent = []
            top_msg = None
            max_likes = -1

            for msg in messages:
                sentiment_obj = msg.get("entities", {}).get("sentiment") or {}
                basic = sentiment_obj.get("basic", "")
                if basic == "Bullish":
                    bull += 1
                elif basic == "Bearish":
                    bear += 1
                else:
                    neutral += 1

                likes = (msg.get("likes") or {}).get("total", 0)
                if likes > max_likes:
                    max_likes = likes
                    top_msg = {
                        "body": msg.get("body", "")[:300],
                        "likes": likes,
                        "sentiment": basic or "Neutral",
                        "created_at": msg.get("created_at", ""),
                    }

                recent.append({
                    "body": msg.get("body", "")[:200],
                    "sentiment": basic or "Neutral",
                    "created_at": msg.get("created_at", ""),
                })

            total = len(messages)
            return {
                "bull_pct": round(bull / total * 100, 1),
                "bear_pct": round(bear / total * 100, 1),
                "neutral_pct": round(neutral / total * 100, 1),
                "message_count": total,
                "top_message": top_msg,
                "recent_messages": recent[:10],
            }

    except Exception as e:
        return _empty(error=str(e))


def _empty(error: str = None) -> dict:
    r = {
        "bull_pct": 33.3,
        "bear_pct": 33.3,
        "neutral_pct": 33.4,
        "message_count": 0,
        "top_message": None,
        "recent_messages": [],
    }
    if error:
        r["error"] = error
    return r
