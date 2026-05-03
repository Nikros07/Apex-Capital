import asyncio
import json
import os
from contextlib import asynccontextmanager
from typing import List

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from utils.db import (
    add_to_watchlist, get_monthly_reports, get_portfolio,
    get_portfolio_snapshots, get_recent_trades, get_watchlist,
    init_db, remove_from_watchlist,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    init_db()

    # Default watchlist — 58 diversified tickers across sectors
    _DEFAULT_WATCHLIST = (
        # Tech mega-cap
        "AAPL,MSFT,NVDA,GOOGL,META,AMZN,TSLA,AMD,AVGO,QCOM,ORCL,CRM,ADBE,NFLX,INTC,"
        # Finance
        "JPM,BAC,V,MA,GS,MS,BRK-B,AXP,"
        # Healthcare
        "UNH,LLY,JNJ,ABBV,MRK,PFE,"
        # Energy
        "XOM,CVX,COP,SLB,"
        # Consumer & Retail
        "WMT,COST,HD,MCD,PG,"
        # ETFs
        "SPY,QQQ,IWM,XLK,XLF,GLD,"
        # High-growth / momentum
        "PLTR,COIN,UBER,SNOW,CRWD,DDOG,RBLX,ZS,"
        # Semis & Global
        "TSM,ASML,MU,NVO,SHOP,SPOT"
    )
    for ticker in os.getenv("WATCHLIST", _DEFAULT_WATCHLIST).split(","):
        t = ticker.strip().upper()
        if t:
            add_to_watchlist(t)

    from utils.key_manager import KeyManager
    KeyManager.get_instance()  # pre-warm singleton (never raises now)

    try:
        from core.scheduler import setup_scheduler
        setup_scheduler(get_pm(), get_cio(), broadcast)
    except Exception as e:
        print(f"[WARNING] Scheduler/agent setup failed: {e}")

    # Startup scan: run once 90s after boot so the fund isn't idle on fresh deploy
    asyncio.create_task(_delayed_startup_scan())

    print("=" * 50)
    print("  APEX CAPITAL MANAGEMENT — ONLINE")
    print(f"  Portfolio: {get_portfolio().get('total_value', 10000):.2f} EUR")
    print("=" * 50)

    yield  # app runs here

    # ── Shutdown ─────────────────────────────────────────────────────────────
    from core.scheduler import get_scheduler
    sched = get_scheduler()
    if sched and sched.running:
        sched.shutdown(wait=False)
    print("[Apex] Shutdown complete.")


app = FastAPI(title="Apex Capital Management", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


# ─── WebSocket Manager ───────────────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self._connections: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self._connections:
            self._connections.remove(ws)

    async def broadcast(self, message: dict):
        if not self._connections:
            return
        text = json.dumps(message, default=str)
        dead = []
        for ws in self._connections:
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


ws_manager = ConnectionManager()


async def broadcast(msg: dict):
    await ws_manager.broadcast(msg)


# ─── Lazy-import heavy objects so startup is fast ────────────────────────────

_cio = None
_portfolio_manager = None


def get_cio():
    global _cio
    if _cio is None:
        from agents.cio import MarcusCIO
        _cio = MarcusCIO(broadcast)
    return _cio


def get_pm():
    global _portfolio_manager
    if _portfolio_manager is None:
        from core.portfolio import PortfolioManager
        _portfolio_manager = PortfolioManager(broadcast)
    return _portfolio_manager


# ─── WebSocket ───────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        await ws.send_json({"type": "portfolio_update", "portfolio": get_portfolio()})
        while True:
            try:
                raw = await asyncio.wait_for(ws.receive_text(), timeout=30.0)
                msg = json.loads(raw)
                if msg.get("type") == "ping":
                    await ws.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                try:
                    await ws.send_json({"type": "heartbeat"})
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect(ws)


# ─── Health check (Railway requires this) ────────────────────────────────────

from datetime import datetime as _dt
from fastapi.responses import JSONResponse

@app.get("/health")
async def health():
    portfolio = get_portfolio()
    return JSONResponse({
        "status": "ok",
        "version": "1.0.0",
        "ts": _dt.utcnow().isoformat(),
        "portfolio_value": portfolio.get("total_value", 0),
        "cash": portfolio.get("cash_eur", 0),
        "positions": len(portfolio.get("positions", {})),
    })


# ─── Static ──────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return FileResponse("static/index.html")


# ─── Analysis ────────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    ticker: str


@app.post("/api/analyze")
async def analyze_ticker(req: AnalyzeRequest):
    ticker = req.ticker.upper().strip()
    if not ticker:
        raise HTTPException(400, "Ticker required")
    asyncio.create_task(_run_analysis(ticker))
    return {"status": "started", "ticker": ticker}


async def _delayed_startup_scan():
    """Run one watchlist scan 90s after startup so the fund isn't idle on fresh deploy."""
    await asyncio.sleep(90)
    try:
        from core.scheduler import run_watchlist_scan
        await run_watchlist_scan(get_cio(), get_pm(), broadcast)
    except Exception as e:
        print(f"[Startup scan] Error: {e}")


async def _run_analysis(ticker: str):
    try:
        result = await get_cio().run_pipeline(ticker)
        if result.get("verdict") == "INVEST":
            risk_verdict = result.get("reports", {}).get("risk", {}).get("risk_verdict", "")
            if risk_verdict != "CRITICAL":
                trade = await get_pm().execute_buy(ticker, result)
                await broadcast({"type": "auto_trade", "ticker": ticker, "trade": trade})
    except Exception as e:
        await broadcast({"type": "pipeline_error", "ticker": ticker, "error": str(e)})


# ─── Portfolio ───────────────────────────────────────────────────────────────

@app.get("/api/portfolio")
async def api_portfolio():
    return get_portfolio()


@app.get("/api/trades")
async def api_trades(limit: int = 100):
    return {"trades": get_recent_trades(limit)}


@app.get("/api/portfolio/snapshots")
async def api_snapshots():
    return {"snapshots": get_portfolio_snapshots()}


@app.post("/api/sell/{ticker}")
async def api_sell(ticker: str):
    from data.market import fetch_current_price
    price = await fetch_current_price(ticker.upper())
    if price <= 0:
        raise HTTPException(400, "Could not fetch current price")
    result = await get_pm().execute_sell(ticker.upper(), price, "MANUAL")
    return result


# ─── Watchlist ───────────────────────────────────────────────────────────────

class WatchlistReq(BaseModel):
    ticker: str


@app.get("/api/watchlist")
async def api_watchlist():
    return {"watchlist": get_watchlist()}


@app.post("/api/watchlist")
async def api_watchlist_add(req: WatchlistReq):
    add_to_watchlist(req.ticker.upper())
    return {"status": "added", "ticker": req.ticker.upper()}


@app.delete("/api/watchlist/{ticker}")
async def api_watchlist_remove(ticker: str):
    remove_from_watchlist(ticker.upper())
    return {"status": "removed", "ticker": ticker.upper()}


# ─── Manual Scan ─────────────────────────────────────────────────────────────

@app.post("/api/scan")
async def api_scan():
    """Trigger a full watchlist scan immediately (same logic as scheduled scan)."""
    asyncio.create_task(_run_scan())
    return {"status": "started", "message": "Watchlist scan triggered"}


async def _run_scan():
    try:
        from core.scheduler import run_watchlist_scan
        await run_watchlist_scan(get_cio(), get_pm(), broadcast)
    except Exception as e:
        await broadcast({"type": "pipeline_error", "ticker": "SCAN", "error": str(e)})


# ─── Reports ─────────────────────────────────────────────────────────────────

@app.get("/api/reports")
async def api_reports():
    return {"reports": get_monthly_reports()}


@app.post("/api/reports/generate")
async def api_generate_report():
    from core.reporter import generate_monthly_report
    asyncio.create_task(generate_monthly_report(broadcast))
    return {"status": "generating"}


# ─── Market Data ─────────────────────────────────────────────────────────────

@app.get("/api/price/{ticker}")
async def api_price(ticker: str):
    from data.market import fetch_current_price, fetch_indicators
    t = ticker.upper()
    price, ind = await asyncio.gather(fetch_current_price(t), fetch_indicators(t))
    return {"ticker": t, "price": price, "indicators": ind}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
