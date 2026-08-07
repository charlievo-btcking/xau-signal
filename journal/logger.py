"""
Nhật ký tín hiệu + bộ phân định kết quả tự động.

Quy ước: GIỮ NGUYÊN SL/TP tới khi chạm. Không dời hòa vốn, không chốt một phần.
Nếu bạn trade khác quy ước này, số liệu sẽ lệch với tài khoản thật.
"""
import numpy as np
import pandas as pd

COLUMNS = [
    "signal_time", "symbol", "direction", "score", "grade",
    "entry", "sl", "tp", "rr", "sl_dist", "lot",
    "pattern", "session", "h4_bias", "zone_kind", "zone_score", "tp_moved",
    "status", "exit_time", "exit_price", "r_result", "mae_r", "mfe_r", "taken", "note",
]
NUMS = ["score", "entry", "sl", "tp", "rr", "sl_dist", "lot",
        "zone_score", "exit_price", "r_result", "mae_r", "mfe_r"]


def _coerce(df: pd.DataFrame) -> pd.DataFrame:
    """Google Sheets trả về toàn chuỗi, nên phải ép kiểu lại."""
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = np.nan
    for c in NUMS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ("signal_time", "exit_time"):
        df[c] = pd.to_datetime(df[c], errors="coerce", utc=True)
    for c in ("tp_moved", "taken"):
        df[c] = df[c].astype(str).str.lower().isin(["true", "1", "yes", "có"])
    for c in ("symbol", "direction", "status", "pattern", "session",
              "h4_bias", "zone_kind", "grade", "note"):
        df[c] = df[c].fillna("").astype(str)
    return df[COLUMNS]


def load(store) -> pd.DataFrame:
    raw = store.read()
    if raw is None or len(raw) == 0:
        return _coerce(pd.DataFrame(columns=COLUMNS))
    return _coerce(raw.copy())


def save(df: pd.DataFrame, store) -> None:
    store.write(df)


def append_signal(store, sig) -> bool:
    """Ghi một dòng. Trả về True nếu thật sự ghi mới."""
    df = load(store)
    ts = pd.Timestamp(sig.time).tz_convert("UTC")
    if not df.empty:
        dup = (df["signal_time"] == ts) & (df["symbol"] == sig.symbol) \
              & (df["direction"] == sig.direction)
        if bool(dup.any()):
            return False

    p = sig.plan
    row = {
        "signal_time": ts, "symbol": sig.symbol, "direction": sig.direction,
        "score": sig.score, "grade": sig.grade,
        "entry": p.entry, "sl": p.sl, "tp": p.tp, "rr": round(p.rr, 2),
        "sl_dist": round(p.sl_dist, 2), "lot": p.lot,
        "pattern": sig.pattern, "session": sig.session, "h4_bias": sig.h4_bias,
        "zone_kind": sig.zone.kind if sig.zone else "",
        "zone_score": sig.zone.score if sig.zone else np.nan,
        "tp_moved": bool(p.tp_moved), "status": "PENDING",
        "exit_time": pd.NaT, "exit_price": np.nan, "r_result": np.nan,
        "mae_r": np.nan, "mfe_r": np.nan, "taken": False, "note": p.block_note,
    }
    save(pd.concat([df, pd.DataFrame([row])], ignore_index=True), store)
    return True


def _walk(bars, direction, entry, sl, tp, sl_dist, max_bars, m1_getter):
    """Duyệt từng nến xem chạm TP hay SL trước, kèm MAE/MFE."""
    mae = mfe = 0.0
    for i, (ts, b) in enumerate(bars.iterrows()):
        if i >= max_bars:
            last = float(b["close"])
            r = (last - entry) / sl_dist if direction == "BUY" else (entry - last) / sl_dist
            return "EXPIRED", ts, last, round(r, 2), round(mae, 2), round(mfe, 2)

        hi, lo = float(b["high"]), float(b["low"])
        if direction == "BUY":
            mfe = max(mfe, (hi - entry) / sl_dist)
            mae = min(mae, (lo - entry) / sl_dist)
            hit_tp, hit_sl = hi >= tp, lo <= sl
        else:
            mfe = max(mfe, (entry - lo) / sl_dist)
            mae = min(mae, (entry - hi) / sl_dist)
            hit_tp, hit_sl = lo <= tp, hi >= sl

        if hit_tp and hit_sl:
            # Nến chạm cả hai → tải M1 của chính khoảng đó xem cái nào tới trước
            m1 = m1_getter(ts, ts + pd.Timedelta(minutes=15))
            res = None
            if m1 is not None and not m1.empty:
                for _, mb in m1.iterrows():
                    mh, ml = float(mb["high"]), float(mb["low"])
                    if direction == "BUY":
                        if ml <= sl:
                            res = "LOSS"; break
                        if mh >= tp:
                            res = "WIN"; break
                    else:
                        if mh >= sl:
                            res = "LOSS"; break
                        if ml <= tp:
                            res = "WIN"; break
            if res is None:
                res = "LOSS"        # không có M1 → ghi bất lợi, thà bi quan
            price = tp if res == "WIN" else sl
            r = (abs(tp - entry) / sl_dist) if res == "WIN" else -1.0
            return res, ts, price, round(r, 2), round(mae, 2), round(mfe, 2)

        if hit_tp:
            return "WIN", ts, tp, round(abs(tp - entry) / sl_dist, 2), round(mae, 2), round(mfe, 2)
        if hit_sl:
            return "LOSS", ts, sl, -1.0, round(mae, 2), round(mfe, 2)

    return None, None, None, None, round(mae, 2), round(mfe, 2)


def resolve_pending(store, m15_getter, m1_getter, max_bars: int = 48) -> int:
    df = load(store)
    if df.empty:
        return 0
    pend = df[df["status"] == "PENDING"]
    if pend.empty:
        return 0

    changed = 0
    for idx, row in pend.iterrows():
        start = pd.Timestamp(row["signal_time"])
        if pd.isna(start):
            continue
        bars = m15_getter(start, start + pd.Timedelta(minutes=15 * (max_bars + 4)))
        if bars is None or bars.empty:
            continue
        bars = bars[bars.index > start.tz_convert(bars.index.tz)]
        if bars.empty:
            continue

        status, ts, price, r, mae, mfe = _walk(
            bars, row["direction"], float(row["entry"]), float(row["sl"]),
            float(row["tp"]), float(row["sl_dist"]), max_bars, m1_getter)
        df.at[idx, "mae_r"], df.at[idx, "mfe_r"] = mae, mfe
        if status is not None:
            df.at[idx, "status"] = status
            df.at[idx, "exit_time"] = pd.Timestamp(ts).tz_convert("UTC")
            df.at[idx, "exit_price"] = price
            df.at[idx, "r_result"] = r
            changed += 1

    save(df, store)
    return changed


def stats(df: pd.DataFrame, by=None) -> pd.DataFrame:
    d = df[df["status"].isin(["WIN", "LOSS", "EXPIRED"])].copy()
    if d.empty:
        return pd.DataFrame()

    def agg(g):
        closed = g[g["status"].isin(["WIN", "LOSS"])]
        n = len(closed)
        wins = int((closed["status"] == "WIN").sum())
        return pd.Series({
            "Số lệnh": len(g), "Đã chốt": n, "Thắng": wins,
            "WR %": round(wins / n * 100, 1) if n else np.nan,
            "R/lệnh": round(g["r_result"].mean(), 2),
            "Tổng R": round(g["r_result"].sum(), 2),
            "MAE tb (R)": round(g["mae_r"].mean(), 2),
            "MFE tb (R)": round(g["mfe_r"].mean(), 2),
        })

    if by is None:
        return agg(d).to_frame("Tổng").T
    if by == "score_bucket":
        d["score_bucket"] = pd.cut(d["score"], [0, 55, 65, 75, 85, 101],
                                   labels=["<55", "55-64", "65-74", "75-84", "85+"],
                                   right=False)
    return d.groupby(by, observed=True).apply(agg, include_groups=False)
