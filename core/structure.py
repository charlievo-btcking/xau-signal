"""Cau truc thi truong theo price action: pivot, swing, BOS."""
from dataclasses import dataclass
from typing import List, Optional
import pandas as pd


@dataclass
class Pivot:
    idx: int
    time: pd.Timestamp
    price: float
    kind: str  # 'high' | 'low'


def find_pivots(df: pd.DataFrame, left: int = 2, right: int = 2) -> List[Pivot]:
    """Fractal: dinh/day duoc xac nhan sau `right` nen. Dung ca bong nen."""
    highs = df["high"].values
    lows = df["low"].values
    n = len(df)
    out: List[Pivot] = []
    for i in range(left, n - right):
        hw = highs[i - left:i + right + 1]
        lw = lows[i - left:i + right + 1]
        if highs[i] == hw.max() and (hw.argmax() == left):
            out.append(Pivot(i, df.index[i], float(highs[i]), "high"))
        if lows[i] == lw.min() and (lw.argmin() == left):
            out.append(Pivot(i, df.index[i], float(lows[i]), "low"))
    return out


@dataclass
class Structure:
    bias: str                      # 'UP' | 'DOWN' | 'NEUTRAL'
    detail: str
    swing_highs: List[Pivot]
    swing_lows: List[Pivot]
    bars_since_bos: Optional[int]  # so nen ke tu lan pha cau truc gan nhat


def market_structure(df: pd.DataFrame, left=2, right=2) -> Structure:
    """UP khi dinh sau cao hon dinh truoc VA day sau cao hon day truoc."""
    pv = find_pivots(df, left, right)
    sh = [p for p in pv if p.kind == "high"]
    sl = [p for p in pv if p.kind == "low"]

    if len(sh) < 2 or len(sl) < 2:
        return Structure("NEUTRAL", "chưa đủ swing để đọc cấu trúc", sh, sl, None)

    h1, h2 = sh[-2].price, sh[-1].price
    l1, l2 = sl[-2].price, sl[-1].price

    if h2 > h1 and l2 > l1:
        bias, detail = "UP", "HH + HL"
    elif h2 < h1 and l2 < l1:
        bias, detail = "DOWN", "LH + LL"
    else:
        hi_txt = "HH" if h2 > h1 else "LH"
        lo_txt = "HL" if l2 > l1 else "LL"
        return Structure("NEUTRAL", f"cấu trúc lệch ({hi_txt} + {lo_txt})", sh, sl, None)

    # BOS gan nhat: nen dong cua vuot qua dinh/day swing truoc do
    bars_since = None
    closes = df["close"].values
    if bias == "UP":
        ref, ref_i = sh[-2].price, sh[-2].idx
        for i in range(ref_i + 1, len(df)):
            if closes[i] > ref:
                bars_since = len(df) - 1 - i
                break
    else:
        ref, ref_i = sl[-2].price, sl[-2].idx
        for i in range(ref_i + 1, len(df)):
            if closes[i] < ref:
                bars_since = len(df) - 1 - i
                break

    return Structure(bias, detail, sh, sl, bars_since)


def last_impulse(df: pd.DataFrame, bias: str, lookback: int = 40):
    """Chan song day gan nhat -> tra ve (start_price, end_price) de tinh fibo hoi."""
    w = df.tail(lookback)
    if len(w) < 5:
        return None
    if bias == "UP":
        lo_i = w["low"].idxmin()
        after = w.loc[lo_i:]
        if len(after) < 2:
            return None
        return float(w["low"].min()), float(after["high"].max())
    else:
        hi_i = w["high"].idxmax()
        after = w.loc[hi_i:]
        if len(after) < 2:
            return None
        return float(w["high"].max()), float(after["low"].min())


def fib_zone(impulse, fib_min: float, fib_max: float):
    """Vung hoi giua fib_min va fib_max cua song day."""
    if impulse is None:
        return None
    a, b = impulse
    lo = b - (b - a) * fib_max
    hi = b - (b - a) * fib_min
    return (min(lo, hi), max(lo, hi))
