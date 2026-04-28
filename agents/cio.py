import asyncio
from typing import Callable, Optional

from agents.committee import InvestmentCommittee
from agents.devil import DanteAgent
from agents.fundamental import SophieAgent
from agents.macro import ElenaAgent
from agents.research import AlexAgent
from agents.risk import ViktorAgent
from agents.sentiment import JordanAgent
from agents.technical import KaiAgent
from data.market import compute_indicators, fetch_current_price, fetch_ohlcv
from utils.db import insert_analysis


class MarcusCIO:
    def __init__(self, broadcast: Optional[Callable] = None):
        self._broadcast_fn = broadcast
        self.elena = ElenaAgent(broadcast)
        self.kai = KaiAgent(broadcast)
        self.sophie = SophieAgent(broadcast)
        self.alex = AlexAgent(broadcast)
        self.jordan = JordanAgent(broadcast)
        self.viktor = ViktorAgent(broadcast)
        self.committee = InvestmentCommittee(broadcast)
        self.dante = DanteAgent(broadcast)

    async def _broadcast(self, event_type: str, data: dict):
        if not self._broadcast_fn:
            return
        msg = {"type": event_type, "agent": "CIO", **data}
        try:
            if asyncio.iscoroutinefunction(self._broadcast_fn):
                await self._broadcast_fn(msg)
            else:
                self._broadcast_fn(msg)
        except Exception:
            pass

    async def run_pipeline(self, ticker: str) -> dict:
        ticker = ticker.upper().strip()
        await self._broadcast("pipeline_start", {
            "ticker": ticker,
            "message": f"Starting full analysis pipeline for {ticker}",
        })

        # Step 1: Elena macro context
        await self._broadcast("pipeline_step", {"step": "macro", "ticker": ticker,
                                                  "message": "Elena running macro analysis..."})
        macro_report = await self.elena.analyze()

        # Step 2: Fetch market data
        await self._broadcast("pipeline_step", {"step": "market_data", "ticker": ticker,
                                                  "message": f"Fetching 6-month OHLCV for {ticker}..."})
        df = await fetch_ohlcv(ticker, period="6mo")
        indicators = compute_indicators(df) if (df is not None and not df.empty) else {}
        current_price = indicators.get("current_price") or await fetch_current_price(ticker)
        atr = indicators.get("atr") or max(current_price * 0.02, 0.01)

        # Step 3: Parallel analysis
        await self._broadcast("pipeline_step", {
            "step": "parallel_analysis", "ticker": ticker,
            "message": "Kai + Sophie + Alex running in parallel...",
        })
        tech_report, fund_report, research_report = await asyncio.gather(
            self.kai.analyze(ticker, macro_report),
            self.sophie.analyze(ticker, macro_report),
            self.alex.analyze(ticker, macro_report),
        )

        # Step 4: Jordan uses technical signal
        await self._broadcast("pipeline_step", {"step": "sentiment", "ticker": ticker,
                                                  "message": "Jordan scanning social sentiment..."})
        sentiment_report = await self.jordan.analyze(
            ticker, tech_report.get("signal", "NEUTRAL"), macro_report
        )

        all_reports = {
            "macro": macro_report,
            "technical": tech_report,
            "fundamental": fund_report,
            "research": research_report,
            "sentiment": sentiment_report,
        }

        # Step 5: Viktor risk
        await self._broadcast("pipeline_step", {"step": "risk", "ticker": ticker,
                                                  "message": "Viktor running risk assessment..."})
        risk_report = await self.viktor.assess(ticker, all_reports, current_price, atr)
        all_reports["risk"] = risk_report

        # Step 6: Committee
        await self._broadcast("pipeline_step", {"step": "committee", "ticker": ticker,
                                                  "message": "Committee deliberating..."})
        committee_result = await self.committee.deliberate(ticker, all_reports)

        # Step 7: Dante if INVEST
        dante_result = None
        if committee_result.get("verdict") == "INVEST":
            await self._broadcast("pipeline_step", {"step": "devil", "ticker": ticker,
                                                      "message": "Dante finding the fatal flaw..."})
            dante_result = await self.dante.challenge(ticker, committee_result, all_reports)

        final = {
            "ticker": ticker,
            "current_price": current_price,
            "verdict": committee_result.get("verdict"),
            "conviction": committee_result.get("conviction"),
            "position_size_eur": committee_result.get("position_size_eur"),
            "entry": committee_result.get("entry"),
            "stop_loss": committee_result.get("stop_loss"),
            "take_profit": committee_result.get("take_profit"),
            "investment_principle": committee_result.get("investment_principle"),
            "reasoning": committee_result.get("reasoning"),
            "override_reason": committee_result.get("override_reason"),
            "high_uncertainty": committee_result.get("high_uncertainty"),
            "reports": {
                "macro": macro_report,
                "technical": tech_report,
                "fundamental": fund_report,
                "research": research_report,
                "sentiment": sentiment_report,
                "risk": risk_report,
                "committee": committee_result,
                "dante": dante_result,
            },
        }

        try:
            insert_analysis({
                "ticker": ticker,
                "full_report": final,
                "verdict": committee_result.get("verdict"),
                "conviction": committee_result.get("conviction", 0),
                "entry_price": current_price,
            })
        except Exception:
            pass

        await self._broadcast("pipeline_done", {
            "ticker": ticker,
            "verdict": committee_result.get("verdict"),
            "conviction": committee_result.get("conviction"),
            "result": final,
        })
        return final
