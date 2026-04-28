import sqlite3
import json
import os
from datetime import datetime
from contextlib import contextmanager

DB_PATH = os.getenv("DB_PATH", "apex.db")


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS portfolio (
                id INTEGER PRIMARY KEY DEFAULT 1,
                cash_eur REAL DEFAULT 10000.0,
                total_value REAL DEFAULT 10000.0,
                positions TEXT DEFAULT '{}',
                total_pnl_eur REAL DEFAULT 0.0,
                total_pnl_pct REAL DEFAULT 0.0,
                peak_value REAL DEFAULT 10000.0,
                max_drawdown_pct REAL DEFAULT 0.0,
                monthly_start_value REAL DEFAULT 10000.0
            );

            INSERT OR IGNORE INTO portfolio (id) VALUES (1);

            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                ticker TEXT,
                action TEXT,
                shares REAL,
                price_eur REAL,
                total_eur REAL,
                stop_loss REAL,
                take_profit REAL,
                rr_ratio REAL,
                conviction INTEGER,
                close_reason TEXT,
                pnl_eur REAL DEFAULT 0.0,
                all_agent_signals TEXT
            );

            CREATE TABLE IF NOT EXISTS analysis_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                ticker TEXT,
                full_report TEXT,
                verdict TEXT,
                conviction INTEGER,
                entry_price REAL
            );

            CREATE TABLE IF NOT EXISTS monthly_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                month TEXT UNIQUE,
                report_json TEXT,
                narrative TEXT
            );

            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT UNIQUE,
                last_signal TEXT,
                last_scan TEXT,
                added_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                total_value REAL
            );
        """)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_portfolio():
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM portfolio WHERE id=1").fetchone()
        if row:
            d = dict(row)
            d["positions"] = json.loads(d["positions"] or "{}")
            return d
        return {
            "cash_eur": 10000.0, "total_value": 10000.0, "positions": {},
            "total_pnl_eur": 0.0, "total_pnl_pct": 0.0,
            "peak_value": 10000.0, "max_drawdown_pct": 0.0,
            "monthly_start_value": 10000.0
        }


def update_portfolio(cash_eur, positions, total_value, total_pnl_eur,
                     total_pnl_pct, peak_value, max_drawdown_pct):
    with get_conn() as conn:
        conn.execute(
            """UPDATE portfolio SET cash_eur=?, total_value=?, positions=?,
               total_pnl_eur=?, total_pnl_pct=?, peak_value=?, max_drawdown_pct=?
               WHERE id=1""",
            (cash_eur, total_value, json.dumps(positions),
             total_pnl_eur, total_pnl_pct, peak_value, max_drawdown_pct)
        )
        conn.execute(
            "INSERT INTO portfolio_snapshots (timestamp, total_value) VALUES (?,?)",
            (datetime.utcnow().isoformat(), total_value)
        )


def insert_trade(trade: dict):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO trades (timestamp, ticker, action, shares, price_eur, total_eur,
               stop_loss, take_profit, rr_ratio, conviction, close_reason, pnl_eur, all_agent_signals)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                trade.get("timestamp", datetime.utcnow().isoformat()),
                trade["ticker"], trade["action"], trade["shares"],
                trade["price_eur"], trade["total_eur"],
                trade.get("stop_loss"), trade.get("take_profit"),
                trade.get("rr_ratio"), trade.get("conviction"),
                trade.get("close_reason"), trade.get("pnl_eur", 0),
                json.dumps(trade.get("all_agent_signals", {}))
            )
        )


def insert_analysis(analysis: dict):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO analysis_history (timestamp, ticker, full_report, verdict, conviction, entry_price)
               VALUES (?,?,?,?,?,?)""",
            (
                datetime.utcnow().isoformat(),
                analysis["ticker"], json.dumps(analysis["full_report"]),
                analysis["verdict"], analysis["conviction"], analysis["entry_price"]
            )
        )


def get_recent_trades(limit: int = 50):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_trades_this_month():
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0).isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM trades WHERE timestamp >= ? ORDER BY timestamp", (month_start,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_watchlist():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM watchlist ORDER BY ticker").fetchall()
        return [dict(r) for r in rows]


def add_to_watchlist(ticker: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO watchlist (ticker, added_at) VALUES (?,?)",
            (ticker.upper(), datetime.utcnow().isoformat())
        )


def remove_from_watchlist(ticker: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM watchlist WHERE ticker=?", (ticker.upper(),))


def update_watchlist_signal(ticker: str, signal: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE watchlist SET last_signal=?, last_scan=? WHERE ticker=?",
            (signal, datetime.utcnow().isoformat(), ticker.upper())
        )


def get_monthly_reports():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM monthly_reports ORDER BY month DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def save_monthly_report(month: str, report_json: dict, narrative: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO monthly_reports (month, report_json, narrative) VALUES (?,?,?)",
            (month, json.dumps(report_json), narrative)
        )


def get_portfolio_snapshots():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT timestamp, total_value FROM portfolio_snapshots ORDER BY timestamp"
        ).fetchall()
        return [dict(r) for r in rows]
