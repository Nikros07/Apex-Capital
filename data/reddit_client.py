import asyncio
import os
from functools import partial

BULLISH_KEYWORDS = [
    "buy", "bull", "long", "calls", "moon", "rocket", "pump", "breakout",
    "support", "undervalued", "cheap", "strong", "bullish", "gain", "up",
    "hold", "squeeze", "yolo", "green", "rally", "run"
]
BEARISH_KEYWORDS = [
    "sell", "bear", "short", "puts", "crash", "dump", "overvalued",
    "expensive", "weak", "bearish", "loss", "risk", "avoid", "drop",
    "red", "decline", "fall", "tank", "down"
]


def _score_text(text: str) -> tuple[int, int]:
    t = text.lower()
    bull = sum(1 for w in BULLISH_KEYWORDS if w in t)
    bear = sum(1 for w in BEARISH_KEYWORDS if w in t)
    return bull, bear


def _fetch_reddit_sync(ticker: str) -> dict:
    try:
        import praw

        reddit = praw.Reddit(
            client_id=os.getenv("REDDIT_CLIENT_ID", ""),
            client_secret=os.getenv("REDDIT_CLIENT_SECRET", ""),
            user_agent=os.getenv("REDDIT_USER_AGENT", "ApexCapital/1.0"),
            read_only=True,
        )

        subreddits_config = [
            ("wallstreetbets", 10),
            ("stocks", 5),
            ("investing", 5),
        ]

        all_posts = []
        total_bull = 0
        total_bear = 0

        for sub_name, limit in subreddits_config:
            sub = reddit.subreddit(sub_name)
            try:
                results = list(sub.search(ticker, time_filter="week", sort="top", limit=limit * 2))[:limit]
            except Exception:
                results = []

            for post in results:
                comments = []
                try:
                    post.comments.replace_more(limit=0)
                    for comment in list(post.comments)[:3]:
                        if hasattr(comment, "body"):
                            comments.append(comment.body[:200])
                except Exception:
                    pass

                combined = post.title + " " + " ".join(comments)
                b, bear = _score_text(combined)
                total_bull += b
                total_bear += bear

                all_posts.append({
                    "subreddit": sub_name,
                    "title": post.title,
                    "score": post.score,
                    "upvote_ratio": getattr(post, "upvote_ratio", 0.5),
                    "comments": comments,
                })

        all_posts.sort(key=lambda x: x["score"], reverse=True)
        total = total_bull + total_bear
        raw_sentiment = total_bull / total if total > 0 else 0.5

        return {
            "posts": all_posts[:20],
            "bull_count": total_bull,
            "bear_count": total_bear,
            "total_mentions": len(all_posts),
            "raw_sentiment_score": round(raw_sentiment, 2),
            "top_post": all_posts[0] if all_posts else None,
        }

    except Exception as e:
        return {
            "posts": [],
            "bull_count": 0,
            "bear_count": 0,
            "total_mentions": 0,
            "raw_sentiment_score": 0.5,
            "top_post": None,
            "error": str(e),
        }


async def fetch_reddit_sentiment(ticker: str) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(_fetch_reddit_sync, ticker))
