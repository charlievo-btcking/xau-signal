"""Tinh SL / TP / khoi luong lenh."""
from dataclasses import dataclass
from typing import Optional
import math
import pandas as pd

from .zones import blocking_zone


@dataclass
class RiskPlan:
    entry: float
    sl: float
    tp: float
    rr: float
    sl_dist: float
    lot: float
    tp_moved: bool
    block_note: str
    reject: Optional[str] = None


def swing_sl(m15: pd.DataFrame, i: int, direction: str, atr15: float, cfg) -> float:
    lb = cfg.swing_lookback_m15
    w = m15.iloc[max(0, i - lb):i + 1]
    buf = cfg.sl_buffer_atr_m15 * atr15
    if direction == "BUY":
        return float(w["low"].min()) - buf
    return float(w["high"].max()) + buf


def compute_lot(sl_dist: float, balance: float, risk_pct: float, spec) -> float:
    """spec: dict co contract_size, volume_step, volume_min, volume_max."""
    if sl_dist <= 0:
        return 0.0
    risk_amt = balance * risk_pct / 100.0
    loss_per_lot = sl_dist * spec["contract_size"]
    if loss_per_lot <= 0:
        return 0.0
    raw = risk_amt / loss_per_lot
    step = spec["volume_step"] or 0.01
    lot = math.floor(raw / step) * step
    lot = max(0.0, min(lot, spec["volume_max"]))
    if lot < spec["volume_min"]:
        return 0.0
    return round(lot, 2)


def build_plan(direction, entry, m15, i, atr15, atr_h1, zones, spec, cfg) -> RiskPlan:
    sl = swing_sl(m15, i, direction, atr15, cfg)
    sl_dist = abs(entry - sl)

    if sl_dist < cfg.sl_min_atr_m15 * atr15:
        sl_dist = cfg.sl_min_atr_m15 * atr15
        sl = entry - sl_dist if direction == "BUY" else entry + sl_dist

    if sl_dist > cfg.sl_max_atr_h1 * atr_h1:
        return RiskPlan(entry, sl, 0, 0, sl_dist, 0, False, "",
                        reject=f"SL {sl_dist:.2f} vượt trần {cfg.sl_max_atr_h1}×ATR(H1) "
                               f"= {cfg.sl_max_atr_h1*atr_h1:.2f}")

    tp = entry + cfg.min_rr * sl_dist if direction == "BUY" else entry - cfg.min_rr * sl_dist
    tp_moved, note = False, ""

    z = blocking_zone(zones, entry, tp, cfg.zone_block_score, exclude_pad=0.3 * atr15)
    if z is not None:
        buf = 0.25 * atr15
        new_tp = (z.lo - buf) if direction == "BUY" else (z.hi + buf)
        rr_new = abs(new_tp - entry) / sl_dist if sl_dist else 0
        tp_moved = True
        note = (f"Vùng {z.kind} {z.lo:.2f}–{z.hi:.2f} (điểm {z.score}) chắn đường tới TP. "
                f"TP kéo về {new_tp:.2f}, RR còn {rr_new:.2f}")
        tp = new_tp
        if rr_new < cfg.min_rr:
            return RiskPlan(entry, sl, tp, rr_new, sl_dist, 0, True, note,
                            reject=f"RR sau khi tránh vùng cản chỉ còn {rr_new:.2f}")

    rr = abs(tp - entry) / sl_dist if sl_dist else 0.0
    if rr < cfg.min_rr:
        return RiskPlan(entry, sl, tp, rr, sl_dist, 0, tp_moved, note,
                        reject=f"RR {rr:.2f} < {cfg.min_rr}")

    lot = compute_lot(sl_dist, cfg.balance, cfg.risk_pct, spec)
    return RiskPlan(entry, sl, tp, rr, sl_dist, lot, tp_moved, note)
