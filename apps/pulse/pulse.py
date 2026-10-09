"""Auditable short-cycle BTC/USD paper prediction rounds using Kraken trades."""

from __future__ import annotations

import bisect
from collections import deque
import json
import math
import os
import statistics
import threading
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")

from runtime_config import MODEL_DIR
MODEL = str(MODEL_DIR)
ROOT = Path(__file__).resolve().parents[2]
PERIOD = 5



VERSION = "teacher-harness-v2-spot-v2"
MODEL_LOCK = threading.RLock()
AGENT = None


def get_agent():
    global AGENT
    with MODEL_LOCK:
        if AGENT is None:
            import laya_mlx as laya
            AGENT = laya.load(MODEL, dtype="float16", batch_size=16)
        return AGENT


def parse_trades(raw):
    rows = []
    for x in raw or []:
        try:
            rows.append({"price": float(x[0]), "volume": float(x[1]), "time": float(x[2]),
                         "side": "buy" if x[3] == "b" else "sell", "id": str(x[6]) if len(x) > 6 else str(x[2])})
        except (TypeError, ValueError, IndexError):
            continue
    return sorted(rows, key=lambda x: x["time"])


def reference(trades, boundary):
    before = [x for x in trades if x["time"] <= boundary]
    # A last-trade price remains the market's published last price until another trade.
    if not before or boundary - before[-1]["time"] > 10:
        return None
    return {"price": before[-1]["price"], "trade_time": before[-1]["time"], "age_s": round(boundary - before[-1]["time"], 3)}


def features(trades, cutoff):
    seen = [x for x in trades if x["time"] <= cutoff]
    if not seen or cutoff - seen[-1]["time"] > 10:
        return None
    last = seen[-1]["price"]
    def past(seconds):
        r = reference(seen, cutoff - seconds)
        return None if r is None else round((last / r["price"] - 1) * 10000, 3)
    window = [x for x in seen if cutoff - x["time"] <= 30]
    buy = sum(x["price"] * x["volume"] for x in window if x["side"] == "buy")
    sell = sum(x["price"] * x["volume"] for x in window if x["side"] == "sell")
    points = []
    for offset in (60, 45, 30, 20, 15, 10, 5, 0):
        r = reference(seen, cutoff - offset)
        points.append(r["price"] if r else None)
    if any(v is None for v in points) or not window:
        return None
    return {"price": last, "mom_5s_bps": past(5), "mom_15s_bps": past(15),
            "mom_30s_bps": past(30), "mom_60s_bps": past(60),
            "buy_share_30s": round(buy / (buy + sell), 4) if buy + sell else None,
            "trade_count_30s": len(window), "points": points,
            "cutoff": cutoff, "last_trade_time": seen[-1]["time"]}


def _predict(state, instructions):
    question = {"direction": {"type": "choice", "instructions": instructions,
                              "criteria": ["higher", "lower"]},
                "size": {"type": "choice", "criteria": ["hold", "small", "medium", "large"],
                         "instructions": "Choose spot paper-trade size for your direction: hold=0%, small=25%, medium=50%, large=100% of available cash if higher or held BTC if lower. Consider the noisy five-second horizon and transaction costs. No shorting or leverage."}}
    with MODEL_LOCK:
        agent = get_agent()
        start = time.perf_counter()
        answers = agent.predict(state, question)["answers"]
        raw = answers["direction"]
        size = answers["size"]
        ms = (time.perf_counter() - start) * 1000
    choice = raw["choice"]
    probs = raw.get("probabilities") or {}
    return {"choice": choice, "probabilities": probs, "confidence": raw.get("confidence"),
            "size": size["choice"], "size_probabilities": size.get("probabilities") or {},
            "model_ms": round(ms, 2)}


def predict_pair(f, progress=None, accounts=None):
    accounts = accounts or {}
    def account_text(key):
        a = accounts.get(key)
        if not a:
            return ""
        return (f" Independent paper account: USD cash {a['cash']:.2f}, BTC held {a['btc']:.8f}, "
                f"equity USD {a['equity']:.2f}. Assumed taker fee 80 bps each trade. "
                "Choose size with this available inventory in mind; orders below USD 10 will not execute.")
    pts = ", ".join(f"{p:.1f}" for p in f["points"])
    baseline = _predict(
        f"BTC/USD Kraken spot trade prices at 60,45,30,20,15,10,5,0 seconds ago: {pts}. "
        f"Last 30 seconds: {f['trade_count_30s']} trades, buyer share {f['buy_share_30s']:.1%}."
        + account_text("baseline"),
        f"Will the BTC/USD spot price be higher or lower in the next {PERIOD} seconds? Pick one direction.")
    if progress:
        progress("baseline", baseline)
    state = (f"BTC/USD spot at USD {f['price']:.2f}. Short returns in basis points: "
             f"5s {f['mom_5s_bps']:+.2f}, 15s {f['mom_15s_bps']:+.2f}, "
             f"30s {f['mom_30s_bps']:+.2f}, 60s {f['mom_60s_bps']:+.2f}. "
             f"Aggressive buy share over 30s {f['buy_share_30s']:.1%}; "
             f"trade count {f['trade_count_30s']}. Horizon exactly {PERIOD} seconds. "
             "These are noisy microstructure observations, not certain forecasts."
             + account_text("optimized"))
    model = _predict(state,
                     f"Choose higher or lower for the next {PERIOD}-second spot return, considering recent momentum and buyer flow. "
                     "Return your best directional estimate; the harness may abstain afterward.")
    if progress:
        progress("optimized_raw", model)
    return baseline, model


def harness(model, f, params):
    momentum = f["mom_15s_bps"]
    if abs(momentum) >= params["momentum_bps_15s"]:
        side = "higher" if momentum >= 0 else "lower"
        return {"choice": side, "size": model["size"], "reason": "15 秒动量超过训练段选定门槛，规则给出方向",
                "model_choice": model["choice"], "route": "rule"}
    return {"choice": model["choice"], "size": model["size"], "reason": "动量较弱，由 Laya 给出方向",
            "model_choice": model["choice"], "route": "laya"}


DEFAULT_PARAMS = {"momentum_bps_15s": 1.5}


def score(rows, key):
    valid = [r for r in rows if r.get("truth") in ("higher", "lower")]
    picks = [r for r in valid if r[key]["choice"] in ("higher", "lower")]
    wins = sum(r[key]["choice"] == r["truth"] for r in picks)
    return {"eligible": len(valid), "picks": len(picks), "wins": wins,
            "accuracy": round(wins / len(picks), 4) if picks else None,
            "coverage": round(len(picks) / len(valid), 4) if valid else None,
            "wins_per_round": round(wins / len(valid), 4) if valid else None,
            "higher_picks": sum(r[key]["choice"] == "higher" for r in picks),
            "lower_picks": sum(r[key]["choice"] == "lower" for r in picks)}


