"""
Mau price action tren M15 — noi bang OR, chi can 1 mau xuat hien la du kich hoat.
Moi mau tra ve chat luong 0..1 de dua vao diem tong.
"""
from dataclasses import dataclass
from typing import Optional
import numpy as np
import pandas as pd


@dataclass
class Pattern:
    name: str
    quality: float   # 0..1
    detail: str


def _bar(df: pd.DataFrame, i: int):
    o = float(df["open"].iloc[i]); h = float(df["high"].iloc[i])
    l = float(df["low"].iloc[i]);  c = float(df["close"].iloc[i])
    rng = max(h - l, 1e-9)
    body = abs(c - o)
    return o, h, l, c, rng, body


def engulfing(df: pd.DataFrame, i: int, direction: str, atr15: float, cfg) -> Optional[Pattern]:
    if i < 1:
        return None
    o, h, l, c, rng, body = _bar(df, i)
    po, ph, pl, pc, prng, pbody = _bar(df, i - 1)
    if body < cfg.engulf_min_body_atr * atr15:
        return None
    if direction == "BUY":
        ok = c > o and pc < po and c >= po and o <= pc
    else:
        ok = c < o and pc > po and c <= po and o >= pc
    if not ok:
        return None
    q_body = min(1.0, body / rng / 0.75)
    q_size = min(1.0, body / max(atr15, 1e-9) / 1.1)
    q_eng = min(1.0, body / max(pbody, 1e-9) / 1.8)
    q = float(np.clip(0.4 * q_body + 0.35 * q_size + 0.25 * q_eng, 0, 1))
    return Pattern("Engulfing", q, f"thân {body:.2f} = {body/max(atr15,1e-9):.2f}×ATR")


def pin_bar(df: pd.DataFrame, i: int, direction: str, atr15: float, cfg) -> Optional[Pattern]:
    o, h, l, c, rng, body = _bar(df, i)
    if rng < 0.5 * atr15:
        return None
    up_wick = h - max(o, c)
    dn_wick = min(o, c) - l
    if direction == "BUY":
        wick = dn_wick
        close_ok = c >= l + rng * 2 / 3
    else:
        wick = up_wick
        close_ok = c <= h - rng * 2 / 3
    if wick / rng < cfg.pin_wick_ratio or body / rng > cfg.pin_body_ratio or not close_ok:
        return None
    q_wick = min(1.0, (wick / rng - cfg.pin_wick_ratio) / 0.30 * 0.6 + 0.4)
    q_size = min(1.0, rng / max(atr15, 1e-9) / 1.3)
    q = float(np.clip(0.6 * q_wick + 0.4 * q_size, 0, 1))
    return Pattern("Pin bar", q, f"đuôi chiếm {wick/rng*100:.0f}% biên độ")


def micro_bos(df: pd.DataFrame, i: int, direction: str, atr15: float, cfg) -> Optional[Pattern]:
    """Gia tao day/dinh nguoc chieu roi dong cua vuot swing M15 gan nhat."""
    lb = cfg.bos_lookback_m15
    if i < lb + 3:
        return None
    w = df.iloc[i - lb:i + 1]
    o, h, l, c, rng, body = _bar(df, i)

    if direction == "BUY":
        trough_i = int(np.argmin(w["low"].values))
        if trough_i >= len(w) - 2:
            return None
        after = w.iloc[trough_i:len(w) - 1]
        ref = float(after["high"].max())
        if not (c > ref and float(df["close"].iloc[i - 1]) <= ref):
            return None
        leg = ref - float(w["low"].min())
    else:
        peak_i = int(np.argmax(w["high"].values))
        if peak_i >= len(w) - 2:
            return None
        after = w.iloc[peak_i:len(w) - 1]
        ref = float(after["low"].min())
        if not (c < ref and float(df["close"].iloc[i - 1]) >= ref):
            return None
        leg = float(w["high"].max()) - ref

    q_leg = min(1.0, leg / max(atr15, 1e-9) / 2.0)
    q_body = min(1.0, body / rng / 0.6)
    q = float(np.clip(0.6 * q_leg + 0.4 * q_body, 0, 1))
    return Pattern("Micro-BOS", q, f"phá swing {ref:.2f}")


def detect(df: pd.DataFrame, i: int, direction: str, atr15: float, cfg) -> Optional[Pattern]:
    """Lay mau co chat luong cao nhat trong 3 mau."""
    found = [
        p for p in (
            engulfing(df, i, direction, atr15, cfg),
            pin_bar(df, i, direction, atr15, cfg),
            micro_bos(df, i, direction, atr15, cfg),
        ) if p is not None
    ]
    if not found:
        return None
    return max(found, key=lambda p: p.quality)
