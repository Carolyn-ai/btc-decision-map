"""Kraken public spot data and an explicit paper-trade decision gate."""

from __future__ import annotations

import json
import math
import statistics
import threading
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

import os

os.environ.setdefault("HF_HUB_OFFLINE", "1")


ROOT = Path(__file__).resolve().parent


PAIR = "XBTUSD"
BASE = "https://api.kraken.com/0/public/"
TICKER_PAIRS = "XBTUSD"
PUBLIC_REST_INTERVAL = 1.10
_PUBLIC_REST_LOCK = threading.Lock()
_LAST_PUBLIC_REST_START = 0.0


def fetch_with_timing(endpoint: str, **params) -> tuple[dict, dict]:
    """One shared public REST lane, including prioritized paper quote requests."""
    global _LAST_PUBLIC_REST_START
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        BASE + endpoint + ("?" + query if query else ""),
        headers={"User-Agent": "MarketSentryResearch/1.0", "Accept": "application/json"},
    )
    queued_at = time.time()
    with _PUBLIC_REST_LOCK:
        wait_s = max(0.0, PUBLIC_REST_INTERVAL - (time.monotonic() - _LAST_PUBLIC_REST_START))
        if wait_s:
            time.sleep(wait_s)
        started_at = time.time()
        _LAST_PUBLIC_REST_START = time.monotonic()
        with urllib.request.urlopen(request, timeout=8) as response:
            data = json.load(response)
        received_at = time.time()
    if data.get("error"):
        raise RuntimeError("Kraken: " + ", ".join(data["error"]))
    return data["result"], {"queued_at": queued_at, "request_started_at": started_at,
                            "response_received_at": received_at}


def fetch(endpoint: str, **params) -> dict:
    result, _ = fetch_with_timing(endpoint, **params)
    return result


def _pair_value(result: dict):
    return result[next(key for key in result if key != "last")]


class MarketCache:
    def __init__(self):
        self.lock = threading.Lock()
        self.ticker = None
        self.book = None
        self.trades = None
        self.candles = None
        self.watchlist = {}
        self.asset_rules = None
        self.times = {}
        self.source_errors = {}
        self.last_error = None
        self.sequence = 0

    def _put(self, field, value):
        with self.lock:
            setattr(self, field, value)
            self.times[field] = time.time()
            self.sequence += 1
            self.source_errors.pop(field, None)
            self.last_error = next(iter(self.source_errors.values()), None)

    def fresh_depth_after(self, intent_at: float, deadline_at: float):
        """Observe a new order book after a paper intent; never supply cached data."""
        if time.time() >= deadline_at:
            return None
        try:
            result, timing = fetch_with_timing("Depth", pair=PAIR, count=25)
            raw = _pair_value(result)
            received_at = timing["response_received_at"]
            self._put("book", raw)
            bids = [[float(x[0]), float(x[1])] for x in raw.get("bids", [])[:25]]
            asks = [[float(x[0]), float(x[1])] for x in raw.get("asks", [])[:25]]
            return {**timing, "received_at": received_at, "bids": bids, "asks": asks,
                    "valid_time": intent_at < timing["request_started_at"] <= received_at <= deadline_at}
        except Exception as exc:
            with self.lock:
                self.source_errors["book"] = f"depth_after_intent: {exc}"
                self.last_error = self.source_errors["book"]
            return None

    def refresh_once(self):
        jobs = [
            ("trades", "Trades", {"pair": PAIR, "count": 1000}),
            ("ticker", "Ticker", {"pair": TICKER_PAIRS}),
            ("trades", "Trades", {"pair": PAIR, "count": 1000}),
            ("book", "Depth", {"pair": PAIR, "count": 25}),
            ("trades", "Trades", {"pair": PAIR, "count": 1000}),
        ]
        if time.time() - self.times.get("asset_rules", 0) >= 24 * 60 * 60:
            jobs.insert(0, ("asset_rules", "AssetPairs", {"pair": PAIR}))
        if time.time() - self.times.get("candles", 0) >= 25:
            jobs.append(("candles", "OHLC", {"pair": PAIR, "interval": 1}))
        for index, (field, endpoint, params) in enumerate(jobs):
            call_started = time.monotonic()
            try:
                result = fetch(endpoint, **params)
                if field == "asset_rules":
                    pair = _pair_value(result)
                    value = {"min_order_btc": float(pair["ordermin"]),
                             "min_order_usd": float(pair["costmin"]),
                             "lot_decimals": int(pair["lot_decimals"]),
                             "pair_decimals": int(pair["pair_decimals"]),
                             "status": pair.get("status", "unknown")}
                elif field == "ticker":
                    aliases = {"XXBTZUSD": "BTC", "XETHZUSD": "ETH", "SOLUSD": "SOL", "XXRPZUSD": "XRP"}
                    watch = {}
                    for key, row in result.items():
                        symbol = aliases.get(key)
                        if symbol:
                            last = float(row["c"][0])
                            opening = float(row["o"])
                            watch[symbol] = {
                                "price": last,
                                "change_today_pct": round((last / opening - 1) * 100, 3) if opening else None,
                                "volume_24h": float(row["v"][1]),
                            }
                    with self.lock:
                        self.watchlist = watch
                    value = result.get("XXBTZUSD") or _pair_value(result)
                else:
                    value = _pair_value(result)
                self._put(field, value)
            except Exception as exc:
                with self.lock:
                    self.source_errors[field] = f"{field}: {exc}"
                    self.last_error = self.source_errors[field]
            # Kraken recommends no more than one public REST call per second.
            time.sleep(max(0, 1.15 - (time.monotonic() - call_started)))

    def poll_forever(self):
        while True:
            self.refresh_once()

    def snapshot(self):
        with self.lock:
            ticker = self.ticker
            book = self.book
            trades = self.trades
            candles = self.candles
            watchlist = dict(self.watchlist)
            asset_rules = dict(self.asset_rules) if self.asset_rules else None
            times = dict(self.times)
            sequence = self.sequence
            last_error = self.last_error
            source_errors = dict(self.source_errors)
        now = time.time()
        if not all((ticker, book, trades, candles)):
            return {"ready": False, "source": "Kraken Spot REST", "sequence": sequence,
                    "loaded": list(times), "error": last_error, "server_time": now,
                    "source_errors": source_errors, "asset_rules": asset_rules}

        bids = [[float(x[0]), float(x[1])] for x in book["bids"][:25]]
        asks = [[float(x[0]), float(x[1])] for x in book["asks"][:25]]
        parsed_trades = [
            {"price": float(x[0]), "volume": float(x[1]), "time": float(x[2]),
             "side": "buy" if x[3] == "b" else "sell", "id": str(x[6]) if len(x) > 6 else str(x[2])}
            for x in trades[-1000:]
        ]
        last_trade_at = parsed_trades[-1]["time"] if parsed_trades else None
        try:
            book_level_at = min(float(book["bids"][0][2]), float(book["asks"][0][2]))
        except (IndexError, KeyError, TypeError, ValueError):
            book_level_at = None
        parsed_candles = [
            {"time": int(x[0]), "open": float(x[1]), "high": float(x[2]),
             "low": float(x[3]), "close": float(x[4]), "volume": float(x[6]),
             "complete": index < len(candles) - 1}
            for index, x in enumerate(candles[-120:])
        ]
        complete = [x for x in parsed_candles if x["complete"]]
        mid = (bids[0][0] + asks[0][0]) / 2 if bids and asks else 0
        spread_bps = (asks[0][0] - bids[0][0]) / mid * 10000 if mid else None
        bid_depth = sum(price * qty for price, qty in bids[:10])
        ask_depth = sum(price * qty for price, qty in asks[:10])
        imbalance = (bid_depth - ask_depth) / (bid_depth + ask_depth) if bid_depth + ask_depth else 0
        recent = [x for x in parsed_trades if now - x["time"] <= 90]
        buy_notional = sum(x["price"] * x["volume"] for x in recent if x["side"] == "buy")
        sell_notional = sum(x["price"] * x["volume"] for x in recent if x["side"] == "sell")
        buy_share = buy_notional / (buy_notional + sell_notional) if buy_notional + sell_notional else None
        closes = [x["close"] for x in complete]
        mom5_bps = (closes[-1] / closes[-6] - 1) * 10000 if len(closes) >= 6 else None
        mom15_bps = (closes[-1] / closes[-16] - 1) * 10000 if len(closes) >= 16 else None
        returns = [math.log(closes[i] / closes[i - 1]) * 10000 for i in range(max(1, len(closes) - 20), len(closes))]
        vol_bps = statistics.stdev(returns) if len(returns) >= 3 else None
        buy_slippage = _slippage(asks, 5000, mid)
        sell_slippage = _slippage(bids, 5000, mid)
        features = {
            "mid": mid, "spread_bps": spread_bps,
            "bid_depth_10_usd": bid_depth, "ask_depth_10_usd": ask_depth,
            "book_imbalance": imbalance, "taker_buy_share_90s": buy_share,
            "recent_trade_count_90s": len(recent),
            "trade_window_coverage_s": min(90, max(0, now - parsed_trades[0]["time"])) if parsed_trades else 0,
            "momentum_5m_bps": mom5_bps,
            "momentum_15m_bps": mom15_bps, "volatility_1m_bps": vol_bps,
            "buy_slippage_5k_bps": buy_slippage, "sell_slippage_5k_bps": sell_slippage,
        }
        quality = _quality(features, times, now, bids, asks, len(complete))
        candidate = _candidate(features, quality)
        return {
            "ready": True, "source": "Kraken Spot REST", "pair": "BTC/USD", "sequence": sequence,
            "server_time": now, "source_times": times, "source_age_s": {k: round(now - v, 1) for k, v in times.items()},
            "last_trade_at": last_trade_at,
            "last_trade_age_s": round(now - last_trade_at, 2) if last_trade_at else None,
            "book_level_at": book_level_at,
            "book_level_age_s": round(now - book_level_at, 2) if book_level_at else None,
            "last_error": last_error, "watchlist": watchlist,
            "source_errors": source_errors,
            "asset_rules": asset_rules,
            "ticker": {"last": float(ticker["c"][0]), "bid": float(ticker["b"][0]),
                       "ask": float(ticker["a"][0]), "open_utc": float(ticker["o"]),
                       "high_24h": float(ticker["h"][1]), "low_24h": float(ticker["l"][1]),
                       "volume_24h": float(ticker["v"][1])},
            "bids": bids[:16], "asks": asks[:16], "trades": parsed_trades[-35:],
            "candles": parsed_candles[-90:], "features": features,
            "quality": quality, "candidate": candidate,
        }


def _slippage(levels, notional, mid):
    if not mid:
        return None
    target_qty = notional / mid
    remaining = target_qty
    cost = 0.0
    for price, qty in levels:
        taken = min(remaining, qty)
        cost += taken * price
        remaining -= taken
        if remaining <= 1e-10:
            break
    if remaining > 1e-10:
        return None
    vwap = cost / target_qty
    return abs(vwap / mid - 1) * 10000


def _quality(features, times, now, bids, asks, complete_count):
    checks = {
        "行情新鲜": all(now - times.get(k, 0) <= (65 if k == "candles" else 20) for k in ("ticker", "book", "trades", "candles")),
        "盘口有效": bool(bids and asks and bids[0][0] < asks[0][0]),
        "样本充分": complete_count >= 25 and features["recent_trade_count_90s"] >= 10 and features["trade_window_coverage_s"] >= 60,
        "点差可接受": features["spread_bps"] is not None and features["spread_bps"] <= 4,
        "波动可控": features["volatility_1m_bps"] is not None and features["volatility_1m_bps"] <= 45,
        "深度可估": features["buy_slippage_5k_bps"] is not None and features["sell_slippage_5k_bps"] is not None,
    }
    return {"checks": checks, "passed": all(checks.values())}


def _candidate(f, quality):
    if not quality["passed"]:
        return {"side": "wait", "reason": "数据质量或执行条件未通过", "aligned": 0}
    mom = f["momentum_5m_bps"] or 0
    flow = f["taker_buy_share_90s"]
    book = f["book_imbalance"]
    if flow is None:
        return {"side": "wait", "reason": "最近成交不足", "aligned": 0}
    long_hits = [mom >= 10, flow >= .56, book >= .08]
    short_hits = [mom <= -10, flow <= .44, book <= -.08]
    if all(long_hits):
        if f["buy_slippage_5k_bps"] <= 8:
            return {"side": "enter_long", "reason": "5 分钟动量、主动买盘和买侧深度同向", "aligned": 3}
        return {"side": "wait", "reason": "买入方向信号共振，但预估滑点超过 8 bps", "aligned": 3}
    if all(short_hits):
        if f["sell_slippage_5k_bps"] <= 8:
            return {"side": "enter_short", "reason": "5 分钟动量、主动卖盘和卖侧深度同向", "aligned": 3}
        return {"side": "wait", "reason": "卖出方向信号共振，但预估滑点超过 8 bps", "aligned": 3}
    return {"side": "wait", "reason": "动量、逐笔成交与盘口未形成三项共振", "aligned": max(sum(long_hits), sum(short_hits))}





CACHE = MarketCache()
