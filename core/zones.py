"""
Vung ho tro / khang cu.

Nguyen tac: vung KHONG manh len khi bi cham nhieu lan. Moi lan cham la mot lan
thanh khoan bi an bot. 2-3 lan cham la diem toi da, tu lan 4 tro di bi tru diem.
"""
from dataclasses import dataclass, field
from typing import List
import numpy as np
import pandas as pd

from .structure import find_pivots


@dataclass
class Zone:
    lo: float
    hi: float
    kind: str                 # 'support' | 'resistance' | 'flip'
    score: float
    touches: int
    has_h4: bool
    impulse: float            # luc roi vung, tinh bang boi so ATR
    age_days: float
    flipped: bool
    parts: List[str] = field(default_factory=list)

    @property
    def mid(self) -> float:
        return (self.lo + self.hi) / 2.0

    def contains(self, price: float, pad: float = 0.0) -> bool:
        return (self.lo - pad) <= price <= (self.hi + pad)

    def overlaps(self, a: float, b: float) -> bool:
        lo, hi = min(a, b), max(a, b)
        return not (self.hi < lo or self.lo > hi)


def _impulse_strength(df: pd.DataFrame, idx: int, kind: str, atr_val: float, bars: int) -> float:
    """Gia roi khoi pivot manh den dau, do bang boi so ATR."""
    if atr_val <= 0:
        return 0.0
    end = min(len(df), idx + bars + 1)
    seg = df.iloc[idx:end]
    if len(seg) < 2:
        return 0.0
    if kind == "low":
        move = float(seg["high"].max()) - float(df["low"].iloc[idx])
    else:
        move = float(df["high"].iloc[idx]) - float(seg["low"].min())
    return max(0.0, move / atr_val)


def _count_touches(h1: pd.DataFrame, lo: float, hi: float, gap: int) -> tuple:
    """Dem so lan cham, 2 lan phai cach nhau it nhat `gap` nen."""
    touches, last = 0, -10 ** 9
    last_time = None
    highs, lows = h1["high"].values, h1["low"].values
    for i in range(len(h1)):
        if lows[i] <= hi and highs[i] >= lo:
            if i - last >= gap:
                touches += 1
                last_time = h1.index[i]
            last = i
    return touches, last_time


def _touch_score(t: int) -> float:
    table = {0: 4.0, 1: 8.0, 2: 15.0, 3: 15.0, 4: 10.0, 5: 6.0}
    return table.get(t, 3.0)


def build_zones(h4: pd.DataFrame, h1: pd.DataFrame, cfg) -> List[Zone]:
    """Gom pivot H4 + H1 thanh cac vung co bien tren/duoi, roi cham diem 0-100."""
    if len(h4) < 20 or len(h1) < 20:
        return []

    atr_h4 = float(h4["atr"].iloc[-1])
    if not np.isfinite(atr_h4) or atr_h4 <= 0:
        return []
    now = h1.index[-1]
    price = float(h1["close"].iloc[-1])

    raw = []
    for src, df, is_h4 in (("H4", h4, True), ("H1", h1, False)):
        pivots = find_pivots(df, cfg.pivot_left, cfg.pivot_right)
        a = df["atr"].values
        for p in pivots:
            age = (now - p.time).total_seconds() / 86400.0
            if age > cfg.zone_max_age_days:
                continue
            atr_at = float(a[p.idx]) if np.isfinite(a[p.idx]) else atr_h4
            raw.append({
                "price": p.price,
                "kind": p.kind,
                "src": src,
                "is_h4": is_h4,
                "age": age,
                "impulse": _impulse_strength(df, p.idx, p.kind, atr_at, cfg.zone_impulse_bars),
                "vol": float(df["tick_volume"].iloc[p.idx]) if "tick_volume" in df else 0.0,
                "vol_med": float(df["tick_volume"].tail(200).median()) if "tick_volume" in df else 1.0,
            })

    if not raw:
        return []

    # --- Gom cum theo gia ---
    raw.sort(key=lambda r: r["price"])
    merge_dist = cfg.zone_merge_atr * atr_h4
    clusters, cur = [], [raw[0]]
    for r in raw[1:]:
        if r["price"] - cur[-1]["price"] <= merge_dist:
            cur.append(r)
        else:
            clusters.append(cur)
            cur = [r]
    clusters.append(cur)

    zones: List[Zone] = []
    for c in clusters:
        lo = min(x["price"] for x in c)
        hi = max(x["price"] for x in c)
        if hi - lo < merge_dist * 0.15:          # noi mong cho vung qua hep
            mid = (lo + hi) / 2
            lo, hi = mid - merge_dist * 0.15, mid + merge_dist * 0.15

        has_h4 = any(x["is_h4"] for x in c)
        imps = sorted((x["impulse"] for x in c), reverse=True)
        impulse = float(np.mean(imps[:2])) if imps else 0.0
        age = min(x["age"] for x in c)
        volr = np.mean([x["vol"] / x["vol_med"] if x["vol_med"] else 1.0 for x in c])

        touches, last_touch = _count_touches(h1, lo, hi, cfg.zone_touch_gap)

        # Vung bi than nen H4 xuyen qua -> chuyen sang flip
        body_lo = h4[["open", "close"]].min(axis=1)
        body_hi = h4[["open", "close"]].max(axis=1)
        broken_up = bool(((body_lo > hi)).any() and ((body_hi < lo)).any())
        recent = h4.tail(60)
        rb_lo = recent[["open", "close"]].min(axis=1)
        rb_hi = recent[["open", "close"]].max(axis=1)
        flipped = broken_up or (bool((rb_lo > hi).any()) and bool((rb_hi < lo).any()))

        # --- Cham diem ---
        s_imp = min(1.0, impulse / 2.5) * 30.0
        s_tf = 20.0 if has_h4 else 12.0
        s_touch = _touch_score(touches)
        s_fresh = 15.0 * float(np.exp(-max(0.0, age) / 45.0))
        s_vol = min(1.0, max(0.0, (volr - 0.7) / 0.8)) * 10.0
        s_flip = 10.0 if flipped else 0.0
        score = s_imp + s_tf + s_touch + s_fresh + s_vol + s_flip

        if flipped:
            kind = "flip"
        elif hi < price:
            kind = "support"
        elif lo > price:
            kind = "resistance"
        else:
            kind = "flip"

        zones.append(Zone(
            lo=lo, hi=hi, kind=kind, score=round(score, 1), touches=touches,
            has_h4=has_h4, impulse=round(impulse, 2), age_days=round(age, 1),
            flipped=flipped,
            parts=[f"lực rời {impulse:.2f}×ATR", f"{touches} lần chạm",
                   f"{'có H4' if has_h4 else 'chỉ H1'}", f"{age:.0f} ngày tuổi"],
        ))

    zones.sort(key=lambda z: -z.score)
    return zones


def nearest_zone(zones: List[Zone], price: float, want: str, pad: float):
    """Vung dang chua gia (dung lam vung vao lenh)."""
    cands = [z for z in zones if z.contains(price, pad) and (z.kind == want or z.kind == "flip")]
    if not cands:
        return None
    return max(cands, key=lambda z: z.score)


def blocking_zone(zones: List[Zone], entry: float, tp: float, min_score: float, exclude_pad: float):
    """Vung can nam giua entry va TP."""
    lo, hi = min(entry, tp), max(entry, tp)
    cands = [
        z for z in zones
        if z.score >= min_score and z.overlaps(lo, hi) and not z.contains(entry, exclude_pad)
    ]
    if not cands:
        return None
    # vung gan entry nhat
    return min(cands, key=lambda z: abs(z.mid - entry))
