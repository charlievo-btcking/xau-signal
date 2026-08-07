"""Chi bao tu viet bang pandas — khong phu thuoc TA-Lib."""
import numpy as np
import pandas as pd


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def true_range(df: pd.DataFrame) -> pd.Series:
    prev = df["close"].shift(1)
    return pd.concat(
        [df["high"] - df["low"], (df["high"] - prev).abs(), (df["low"] - prev).abs()],
        axis=1,
    ).max(axis=1)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """ATR theo phuong phap Wilder."""
    return true_range(df).ewm(alpha=1.0 / n, adjust=False).mean()


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0.0)
    dn = (-d).clip(lower=0.0)
    au = up.ewm(alpha=1.0 / n, adjust=False).mean()
    ad = dn.ewm(alpha=1.0 / n, adjust=False).mean()
    rs = au / ad.replace(0.0, np.nan)
    out = 100.0 - 100.0 / (1.0 + rs)
    return out.fillna(50.0)


def stoch_rsi(s: pd.Series, rsi_n=14, stoch_n=14, k=3, d=3):
    """Tra ve (%K, %D) thang 0-100."""
    r = rsi(s, rsi_n)
    lo = r.rolling(stoch_n).min()
    hi = r.rolling(stoch_n).max()
    rng = (hi - lo).replace(0.0, np.nan)
    st = ((r - lo) / rng) * 100.0
    kk = st.rolling(k).mean()
    dd = kk.rolling(d).mean()
    return kk, dd


def daily_vwap(df: pd.DataFrame) -> pd.Series:
    """VWAP neo theo ngay, reset moi ngay. Dung tick_volume cua MT5."""
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    vol = df["tick_volume"].astype(float).replace(0.0, 1.0)
    day = pd.Series(df.index.date, index=df.index)
    pv = (tp * vol).groupby(day).cumsum()
    vv = vol.groupby(day).cumsum()
    return pv / vv


def pct_rank_last(s: pd.Series, lookback: int = 200) -> float:
    """Phan vi cua gia tri cuoi so voi `lookback` gia tri gan nhat (0-100)."""
    w = s.dropna().tail(lookback)
    if len(w) < 20:
        return 50.0
    return float((w < w.iloc[-1]).mean() * 100.0)


def enrich(df: pd.DataFrame, cfg) -> pd.DataFrame:
    """Gan cac cot chi bao vao khung du lieu."""
    out = df.copy()
    out["ema_fast"] = ema(out["close"], cfg.ema_fast)
    out["ema_slow"] = ema(out["close"], cfg.ema_slow)
    out["atr"] = atr(out, cfg.atr_period)
    out["atr_pct"] = out["atr"] / out["close"] * 100.0
    k, d = stoch_rsi(out["close"], cfg.rsi_period, cfg.stoch_period, cfg.stoch_k, cfg.stoch_d)
    out["stoch_k"], out["stoch_d"] = k, d
    if "tick_volume" in out.columns:
        out["vwap"] = daily_vwap(out)
    return out
