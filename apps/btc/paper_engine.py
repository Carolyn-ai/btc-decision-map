"""Causal, unlevered BTC/USD paper accounts for the 30-second exploration lane.

This module has no network, database, clock or model side effects. The caller
supplies observed prices, locked signals, exchange pair rules and timestamps.
Every returned account is a new dict; the input is never mutated.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import math
from typing import Any


DEFAULT_CONFIG = {
    "initial_capital": 10_000.0,
    "fee_bps": 80.0,
    "latency_slippage_bps": 2.0,
    "max_spread_bps": 10.0,
    "max_impact_bps": 10.0,
    "max_quote_jump_bps": 25.0,
    "max_mark_age_s": 5.0,
    "quote_deadline_s": 2.0,
    "target_weight": 0.05,
    "max_order_weight": 0.01,
    "cooldown_s": 120.0,
    "daily_max_orders": 24,
    "daily_turnover_fraction": 0.50,
    "daily_fee_fraction": 0.002,
    "daily_loss_fraction": 0.01,
    # Fetch these from Kraken AssetPairs. Absent rules safely block an order.
    "min_order_btc": None,
    "min_order_usd": None,
    "lot_decimals": None,
}
LANES = ("baseline", "optimized")


def _cfg(config: dict | None) -> dict:
    supplied = dict(config or {})
    # The shared backend uses the older public names; keep the effective
    # assumptions identical when the portfolio engine is called directly.
    if "initial_capital" not in supplied and "capital" in supplied:
        supplied["initial_capital"] = supplied["capital"]
    if "latency_slippage_bps" not in supplied and "slippage_bps" in supplied:
        supplied["latency_slippage_bps"] = supplied["slippage_bps"]
    return {**DEFAULT_CONFIG, **supplied}


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def _utc_day(at: float) -> str:
    return datetime.fromtimestamp(at, timezone.utc).strftime("%Y-%m-%d")


def _round_down(value: float, decimals: int) -> float:
    factor = 10 ** decimals
    return math.floor(value * factor + 1e-10) / factor


def _pair_rules(config: dict) -> tuple[float, float, int] | None:
    minimum_btc = _number(config.get("min_order_btc"))
    minimum_usd = _number(config.get("min_order_usd"))
    decimals = config.get("lot_decimals")
    if (minimum_btc is None or minimum_btc <= 0 or minimum_usd is None
            or minimum_usd < 0 or not isinstance(decimals, int)
            or isinstance(decimals, bool) or not 0 <= decimals <= 12):
        return None
    return minimum_btc, minimum_usd, decimals


def _rules_reason(config: dict) -> str | None:
    status = config.get("asset_status", config.get("status"))
    if status is not None and status != "online":
        return "asset_pair_offline"
    return None if _pair_rules(config) is not None else "asset_rules_unavailable"


def _equity(account: dict, price: float) -> float:
    return float(account.get("cash", 0)) + float(account.get("btc", 0)) * price


def _daily(account: dict, at: float, price: float, config: dict) -> dict:
    result = dict(account)
    result["filled_order_ids"] = list(account.get("filled_order_ids") or [])
    day = _utc_day(at)
    if result.get("day") != day:
        result.update(day=day, day_orders=0, day_turnover=0.0, day_fees=0.0,
                      day_start_equity=_equity(result, price), day_loss_stopped=False)
    else:
        result.setdefault("day_orders", 0)
        result.setdefault("day_turnover", 0.0)
        result.setdefault("day_fees", 0.0)
        result.setdefault("day_start_equity", float(config["initial_capital"]))
        result.setdefault("day_loss_stopped", False)
    return result


def _hold(reason: str, higher: int = 0, lower: int = 0, valid: int = 0,
          target: float | None = None) -> dict:
    return {"side": "hold", "target_weight": target, "notional_usd": 0.0,
            "reason": reason, "counts": {"higher": higher, "lower": lower, "valid": valid}}


def mark_accounts(accounts: dict, price: dict | float, at: float,
                  config: dict | None = None) -> dict:
    """Mark both lanes at one *observed* price and expose staleness explicitly.

    ``price`` from a feed must include ``{price, received_at, event_time}``.
    A number asserts that the caller observed a current price at ``at``. A
    stale/future mark keeps the last account value and returns
    ``comparison_eligible=False``.
    """
    c = _cfg(config)
    observed = (price if isinstance(price, dict) else
                {"price": price, "received_at": at, "event_time": at})
    p = _number(observed.get("price"))
    received = _number(observed.get("received_at"))
    event_time = _number(observed.get("event_time"))
    valid = (p is not None and p > 0 and received is not None
             and received <= at and at - received <= c["max_mark_age_s"]
             and event_time is not None and event_time <= at
             and at - event_time <= c["max_mark_age_s"])
    result = {}
    for lane in LANES:
        original = dict(accounts.get(lane) or {})
        if valid:
            account = _daily(original, at, p, c)
            equity = _equity(account, p)
            peak = max(float(account.get("peak_equity", c["initial_capital"])), equity)
            drawdown = equity / peak - 1 if peak else 0
            account.update(mark_price=p, mark_at=received, equity=equity,
                           pnl=equity - c["initial_capital"],
                           unrealized=float(account.get("btc", 0)) * p - float(account.get("basis", 0)),
                           peak_equity=peak,
                           max_drawdown=min(float(account.get("max_drawdown", 0)), drawdown),
                           mark_stale=False)
            if equity <= float(account["day_start_equity"]) * (1 - c["daily_loss_fraction"]):
                account["day_loss_stopped"] = True
        else:
            account = dict(original)
            account["mark_stale"] = True
        result[lane] = account
    return {"accounts": result, "price": p, "mark_at": received,
            "event_time": event_time,
            "comparison_eligible": bool(valid),
            "reason": "ok" if valid else "stale_or_invalid_mark"}


def evaluate_exploration(locked_rounds: list[dict], accounts: dict, at: float,
                         config: dict | None = None) -> dict:
    """Produce one intention per lane from the six prior five-second slots.

    Every counted round must have both choices and ``locked_at < start``.
    ``notional_usd`` is a maximum *cash spend including fee* for buys and a
    mark-price gross target for sells. No account is mutated here.
    """
    c = _cfg(config)
    now = _number(at)
    if now is None or abs(now / 30 - round(now / 30)) > 1e-7:
        return {lane: _hold("not_30s_boundary") for lane in LANES}
    slots = {round(now - 30 + i * 5, 6) for i in range(6)}
    paired = {}
    for row in locked_rounds:
        start = _number(row.get("start"))
        locked_at = _number(row.get("locked_at", row.get("predicted_at")))
        if (start is None or round(start, 6) not in slots or locked_at is None
                or locked_at >= start or locked_at >= now
                or row.get("status") not in ("locked", "open", "settled", "tie", "void")):
            continue
        if any((row.get(lane) or {}).get("choice") not in ("higher", "lower") for lane in LANES):
            continue
        previous = paired.get(round(start, 6))
        if previous is None or locked_at < previous[0]:
            paired[round(start, 6)] = (locked_at, row)
    rows = [paired[key][1] for key in sorted(paired)]
    results = {}
    for lane in LANES:
        higher = sum(row[lane]["choice"] == "higher" for row in rows)
        valid = len(rows)
        lower = valid - higher
        counts = {"higher": higher, "lower": lower, "valid": valid}
        if valid < 4:
            results[lane] = _hold("insufficient_locked_signals", higher, lower, valid)
            continue
        target = c["target_weight"] if higher >= 4 else 0.0 if higher <= 2 else None
        if target is None:
            results[lane] = _hold("balanced_signals", higher, lower, valid)
            continue
        account = accounts.get(lane) or {}
        mark = _number(account.get("mark_price"))
        mark_at = _number(account.get("mark_at"))
        if (account.get("mark_stale") or mark is None or mark <= 0 or mark_at is None
                or mark_at > now or now - mark_at > c["max_mark_age_s"]):
            results[lane] = _hold("stale_mark", higher, lower, valid, target)
            continue
        rules_reason = _rules_reason(c)
        if rules_reason is not None:
            results[lane] = _hold(rules_reason, higher, lower, valid, target)
            continue
        a = _daily(account, now, mark, c)
        equity = _equity(a, mark)
        if not math.isfinite(equity) or equity <= 0:
            results[lane] = _hold("invalid_equity", higher, lower, valid, target)
            continue
        current_value = float(a.get("btc", 0)) * mark
        delta = target * equity - current_value
        side = "buy" if delta > 1e-8 else "sell" if delta < -1e-8 else "hold"
        if side == "hold":
            results[lane] = _hold("at_target_weight", higher, lower, valid, target)
            continue
        if a.get("day_loss_stopped") or equity <= float(a["day_start_equity"]) * (1 - c["daily_loss_fraction"]):
            results[lane] = _hold("daily_loss_limit", higher, lower, valid, target)
            continue
        if int(a["day_orders"]) >= c["daily_max_orders"]:
            results[lane] = _hold("daily_order_limit", higher, lower, valid, target)
            continue
        previous_fill = _number(a.get("last_fill_at"))
        if previous_fill is not None and now - previous_fill < c["cooldown_s"]:
            results[lane] = _hold("cooldown", higher, lower, valid, target)
            continue
        fee_rate = c["fee_bps"] / 10_000
        remaining_turnover = c["daily_turnover_fraction"] * c["initial_capital"] - float(a["day_turnover"])
        remaining_fee = c["daily_fee_fraction"] * c["initial_capital"] - float(a["day_fees"])
        fee_capacity = remaining_fee / fee_rate if fee_rate > 0 else math.inf
        notional = min(abs(delta), equity * c["max_order_weight"],
                       remaining_turnover, fee_capacity)
        if side == "buy":
            notional = min(notional, float(a.get("cash", 0)))
        else:
            notional = min(notional, current_value)
        minimum_btc, minimum_usd, decimals = _pair_rules(c)
        estimated_qty = _round_down(notional / mark, decimals)
        if notional <= 0 or estimated_qty < minimum_btc or estimated_qty * mark < minimum_usd:
            reason = "daily_budget_exhausted" if remaining_turnover <= 0 or remaining_fee <= 0 else "below_asset_minimum"
            results[lane] = _hold(reason, higher, lower, valid, target)
            continue
        policy_id = str(c.get("policy_id", "exploration-v0"))
        order_id = sha256(f"{policy_id}|{lane}|{now:.6f}".encode()).hexdigest()[:24]
        results[lane] = {"side": side, "target_weight": target,
                         "notional_usd": round(notional, 8),
                         "quantity_btc": estimated_qty if side == "sell" else None,
                         "mark_price": mark, "intent_at": now, "order_id": order_id,
                         "account_key": lane, "reason": "exploration_signal",
                         "counts": counts, "account_revision": a.get("revision", 0)}
    return results


def _levels(raw: Any) -> list[tuple[float, float]]:
    rows = []
    for level in raw or []:
        try:
            price, qty = _number(level[0]), _number(level[1])
            if price is not None and qty is not None and price > 0 and qty > 0:
                rows.append((price, qty))
        except (TypeError, IndexError):
            continue
    return rows


def _sweep(levels: list[tuple[float, float]], quantity: float) -> float | None:
    remaining = quantity
    gross = 0.0
    for price, available in levels:
        taken = min(available, remaining)
        gross += taken * price
        remaining -= taken
        if remaining <= 1e-10:
            return gross
    return None


def validate_quote(intent: dict, quote: dict, at: float,
                   config: dict | None = None) -> dict:
    """Validate a post-intent REST Depth response and compute a full-book fill.

    No historical trade price is accepted. If the requested quantity cannot be
    fully met by observed depth, the whole simulated order is unfilled.
    """
    c = _cfg(config)
    failed = lambda reason: {"valid": False, "reason": reason, "price": None,
                             "quantity_btc": 0.0, "notional_usd": 0.0}
    rules = _pair_rules(c)
    rules_reason = _rules_reason(c)
    if rules_reason is not None:
        return failed(rules_reason)
    side = intent.get("side")
    if side not in ("buy", "sell"):
        return failed("no_order_intent")
    intent_at = _number(intent.get("intent_at"))
    request_at = _number(quote.get("request_started_at"))
    received_at = _number(quote.get("response_received_at"))
    now = _number(at)
    if None in (intent_at, request_at, received_at, now):
        return failed("missing_causal_timestamp")
    if request_at <= intent_at or received_at <= intent_at or received_at < request_at:
        return failed("quote_precedes_intent")
    if quote.get("valid_time") is False:
        return failed("quote_time_invalid")
    if received_at > intent_at + c["quote_deadline_s"] or received_at > now:
        return failed("quote_timeout")
    source_age = _number(quote.get("source_age_s"))
    if source_age is not None and (source_age < 0 or source_age > c["max_mark_age_s"]):
        return failed("stale_quote_source")
    bids = sorted(_levels(quote.get("bids")), reverse=True)
    asks = sorted(_levels(quote.get("asks")))
    if not bids or not asks or bids[0][0] >= asks[0][0]:
        return failed("invalid_book")
    best_bid, best_ask = bids[0][0], asks[0][0]
    mid = (best_bid + best_ask) / 2
    spread_bps = (best_ask - best_bid) / mid * 10_000
    if spread_bps > c["max_spread_bps"]:
        return failed("spread_too_wide")
    mark = _number(intent.get("mark_price"))
    if mark is None or mark <= 0:
        return failed("missing_intent_mark")
    if abs(mid / mark - 1) * 10_000 > c["max_quote_jump_bps"]:
        return failed("quote_jump")
    budget = _number(intent.get("notional_usd"))
    if budget is None or budget <= 0:
        return failed("invalid_order_size")
    fee_rate = c["fee_bps"] / 10_000
    slip = c["latency_slippage_bps"] / 10_000
    minimum_btc, minimum_usd, decimals = rules
    if side == "buy":
        gross_budget = budget / (1 + fee_rate)
        remaining = gross_budget
        raw_quantity = 0.0
        for price, available in asks:
            taken = min(available, remaining / (price * (1 + slip)))
            raw_quantity += taken
            remaining -= taken * price * (1 + slip)
            if remaining <= 1e-7:
                break
        if remaining > 1e-5:
            return failed("insufficient_depth")
        quantity = _round_down(raw_quantity, decimals)
        gross_book = _sweep(asks, quantity)
        if gross_book is None:
            return failed("insufficient_depth")
        gross = gross_book * (1 + slip)
        impact_bps = (gross_book / quantity / best_ask - 1) * 10_000 if quantity else 0.0
    else:
        wanted = _number(intent.get("quantity_btc"))
        if wanted is None or wanted <= 0:
            wanted = budget / mark
        quantity = _round_down(wanted, decimals)
        gross_book = _sweep(bids, quantity)
        if gross_book is None:
            return failed("insufficient_depth")
        gross = gross_book * (1 - slip)
        impact_bps = (1 - gross_book / quantity / best_bid) * 10_000 if quantity else 0.0
    if quantity < minimum_btc or gross < minimum_usd:
        return failed("below_asset_minimum")
    if impact_bps > c["max_impact_bps"]:
        return failed("book_impact_too_high")
    fee = gross * fee_rate
    quote_price = best_ask if side == "buy" else best_bid
    simulated_fill_price = gross / quantity
    return {"valid": True, "reason": "ok", "side": side,
            "price": simulated_fill_price,
            "quote_price": quote_price, "simulated_fill_price": simulated_fill_price,
            "quantity_btc": quantity,
            "notional_usd": gross, "fee_usd": fee,
            "cash_debit_usd": gross + fee if side == "buy" else 0.0,
            "cash_credit_usd": gross - fee if side == "sell" else 0.0,
            "spread_bps": spread_bps, "book_impact_bps": impact_bps,
            "impact_bps": impact_bps, "latency_slippage_bps": c["latency_slippage_bps"],
            "quote_received_at": received_at,
            "best_bid": best_bid, "best_ask": best_ask}


def apply_fill(account: dict, intent: dict, quote: dict,
               config: dict | None = None) -> dict:
    """Apply one validated spot fill, safely returning duplicates unchanged.

    The durable caller must also enforce ``UNIQUE(order_id)`` in its ledger.
    """
    c = _cfg(config)
    original = dict(account)
    order_id = intent.get("order_id")
    if not isinstance(order_id, str) or not order_id:
        return {"account": original, "fill": {"status": "blocked", "reason": "missing_order_id"}}
    if order_id in (original.get("filled_order_ids") or []):
        return {"account": original, "fill": {"status": "duplicate", "order_id": order_id}}
    received = _number(quote.get("response_received_at"))
    if received is None:
        return {"account": original, "fill": {"status": "blocked", "reason": "missing_causal_timestamp"}}
    checked = validate_quote(intent, quote, received, c)
    if not checked["valid"]:
        return {"account": original, "fill": {"status": "unfilled", "reason": checked["reason"], "order_id": order_id}}
    if intent.get("account_revision", original.get("revision", 0)) != original.get("revision", 0):
        return {"account": original, "fill": {"status": "blocked", "reason": "stale_account_revision", "order_id": order_id}}
    price = checked["price"]
    a = _daily(original, received, price, c)
    quantity, gross, fee = checked["quantity_btc"], checked["notional_usd"], checked["fee_usd"]
    equity_before = _equity(a, (checked["best_bid"] + checked["best_ask"]) / 2)
    if (a.get("day_loss_stopped") or equity_before <= a["day_start_equity"] * (1 - c["daily_loss_fraction"])):
        return {"account": original, "fill": {"status": "blocked", "reason": "daily_loss_limit", "order_id": order_id}}
    if a["day_orders"] >= c["daily_max_orders"]:
        return {"account": original, "fill": {"status": "blocked", "reason": "daily_order_limit", "order_id": order_id}}
    last = _number(a.get("last_fill_at"))
    if last is not None and received - last < c["cooldown_s"]:
        return {"account": original, "fill": {"status": "blocked", "reason": "cooldown", "order_id": order_id}}
    if a["day_turnover"] + gross > c["daily_turnover_fraction"] * c["initial_capital"] + 1e-7:
        return {"account": original, "fill": {"status": "blocked", "reason": "daily_turnover_limit", "order_id": order_id}}
    if a["day_fees"] + fee > c["daily_fee_fraction"] * c["initial_capital"] + 1e-7:
        return {"account": original, "fill": {"status": "blocked", "reason": "daily_fee_limit", "order_id": order_id}}
    if gross > equity_before * c["max_order_weight"] + 1e-7:
        return {"account": original, "fill": {"status": "blocked", "reason": "order_weight_limit", "order_id": order_id}}
    before = {"cash": float(a.get("cash", 0)), "btc": float(a.get("btc", 0)),
              "equity": equity_before}
    if intent["side"] == "buy":
        spend = checked["cash_debit_usd"]
        if spend > before["cash"] + 1e-7 or spend > intent["notional_usd"] + 1e-7:
            return {"account": original, "fill": {"status": "blocked", "reason": "insufficient_cash", "order_id": order_id}}
        a["cash"] = before["cash"] - spend
        a["btc"] = before["btc"] + quantity
        a["basis"] = float(a.get("basis", 0)) + spend
    else:
        if quantity > before["btc"] + 1e-10:
            return {"account": original, "fill": {"status": "blocked", "reason": "insufficient_btc", "order_id": order_id}}
        basis_sold = float(a.get("basis", 0)) * (quantity / before["btc"])
        a["cash"] = before["cash"] + checked["cash_credit_usd"]
        a["btc"] = max(0.0, before["btc"] - quantity)
        a["basis"] = max(0.0, float(a.get("basis", 0)) - basis_sold)
        a["realized"] = float(a.get("realized", 0)) + checked["cash_credit_usd"] - basis_sold
    mid = (checked["best_bid"] + checked["best_ask"]) / 2
    after_equity = _equity(a, mid)
    if intent["side"] == "buy" and a["btc"] * mid > after_equity * c["target_weight"] + 1e-6:
        return {"account": original, "fill": {"status": "blocked", "reason": "btc_weight_limit", "order_id": order_id}}
    a["fees"] = float(a.get("fees", 0)) + fee
    a["trades"] = int(a.get("trades", 0)) + 1
    counter = "buys" if intent["side"] == "buy" else "sells"
    a[counter] = int(a.get(counter, 0)) + 1
    a["turnover"] = float(a.get("turnover", 0)) + gross
    a["day_orders"] += 1
    a["day_turnover"] += gross
    a["day_fees"] += fee
    a["last_fill_at"] = received
    a["filled_order_ids"].append(order_id)
    a["revision"] = int(a.get("revision", 0)) + 1
    a.update(mark_price=mid, mark_at=received, equity=after_equity,
             pnl=after_equity - c["initial_capital"],
             unrealized=a["btc"] * mid - float(a.get("basis", 0)), mark_stale=False)
    if after_equity <= a["day_start_equity"] * (1 - c["daily_loss_fraction"]):
        a["day_loss_stopped"] = True
    fill = {"status": "filled", "reason": "ok", "order_id": order_id,
            "side": intent["side"], "account_key": intent.get("account_key"),
            "price": price, "quote_price": checked["quote_price"],
            "simulated_fill_price": checked["simulated_fill_price"],
            "quantity_btc": quantity, "notional_usd": gross,
            "fee_usd": fee, "executed_at": received, "spread_bps": checked["spread_bps"],
            "book_impact_bps": checked["book_impact_bps"],
            "latency_slippage_bps": checked["latency_slippage_bps"], "before": before,
            "after": {"cash": a["cash"], "btc": a["btc"], "equity": after_equity}}
    return {"account": a, "fill": fill}
