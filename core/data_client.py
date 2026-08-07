"""
Nguồn dữ liệu: Twelve Data (https://twelvedata.com).

Thay thế hoàn toàn MetaTrader5 — chạy được trên mọi hệ điều hành và trên
Streamlit Cloud. Khóa API đọc từ st.secrets hoặc biến môi trường,
KHÔNG BAO GIỜ ghi thẳng vào mã nguồn.

Gói Basic miễn phí: 8 credit/phút, 800 credit/ngày.
Mỗi lần lấy một khung thời gian = 1 credit. Mỗi lần hỏi giá = 1 credit.
"""
import os
import time
from datetime import datetime

import numpy as np
import pandas as pd
import requests

BASE = "https://api.twelvedata.com"
TF_MAP = {"M1": "1min", "M5": "5min", "M15": "15min",
          "H1": "1h", "H4": "4h", "D1": "1day"}

SYMBOLS = ["XAU/USD", "XAG/USD", "XPT/USD", "EUR/USD", "GBP/USD", "USD/JPY"]

# Đếm credit đã tiêu trong ngày để bạn biết còn bao nhiêu.
_USAGE = {"day": None, "n": 0}


class DataError(RuntimeError):
    pass


def _bump(n=1):
    today = datetime.utcnow().date()
    if _USAGE["day"] != today:
        _USAGE.update(day=today, n=0)
    _USAGE["n"] += n


def usage() -> int:
    today = datetime.utcnow().date()
    return _USAGE["n"] if _USAGE["day"] == today else 0


def get_key() -> str:
    """Ưu tiên st.secrets (dùng khi deploy), rồi tới biến môi trường."""
    try:
        import streamlit as st
        k = st.secrets.get("TWELVEDATA_API_KEY", "")
        if k:
            return str(k).strip()
    except Exception:
        pass
    return os.environ.get("TWELVEDATA_API_KEY", "").strip()


def has_key() -> bool:
    return bool(get_key())


def _req(path: str, params: dict, timeout: int = 20):
    key = get_key()
    if not key:
        raise DataError("Chưa có TWELVEDATA_API_KEY. Thêm vào .streamlit/secrets.toml "
                        "khi chạy máy cá nhân, hoặc vào phần Secrets của Streamlit Cloud.")
    p = dict(params)
    p["apikey"] = key
    try:
        r = requests.get(f"{BASE}/{path}", params=p, timeout=timeout)
    except requests.RequestException as e:
        raise DataError(f"Không gọi được Twelve Data: {e}")
    _bump()

    if r.status_code == 429:
        raise DataError("Vượt hạn mức Twelve Data (8 credit/phút hoặc 800/ngày). "
                        "Chờ một phút rồi thử lại, hoặc giãn chu kỳ tự làm mới.")
    if r.status_code >= 400:
        raise DataError(f"Twelve Data trả lỗi HTTP {r.status_code}")
    j = r.json()
    if isinstance(j, dict) and str(j.get("status", "")).lower() == "error":
        raise DataError(f"Twelve Data: {j.get('message', 'lỗi không rõ')}")
    return j


def _to_df(values, tz: str) -> pd.DataFrame:
    if not values:
        return pd.DataFrame()
    df = pd.DataFrame(values)
    idx = pd.to_datetime(df["datetime"], errors="coerce")
    df = df.loc[idx.notna()].copy()
    idx = idx[idx.notna()]
    df.index = idx.dt.tz_localize(tz, ambiguous="NaT", nonexistent="shift_forward")
    df = df[df.index.notna()]

    for c in ("open", "high", "low", "close"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    # Forex/kim loại thường không có volume — thay bằng 1.0 để VWAP vẫn tính được.
    if "volume" in df.columns:
        v = pd.to_numeric(df["volume"], errors="coerce").fillna(0.0)
        df["tick_volume"] = v.where(v > 0, 1.0)
    else:
        df["tick_volume"] = 1.0

    out = df[["open", "high", "low", "close", "tick_volume"]].dropna()
    out = out[~out.index.duplicated(keep="last")].sort_index()
    out.index.name = "time"
    return out


def get_rates(symbol: str, tf: str, n: int, tz: str, drop_forming: bool = True) -> pd.DataFrame:
    """Lấy nến. drop_forming=True bỏ nến đang chạy — chỉ giữ nến ĐÃ ĐÓNG."""
    j = _req("time_series", dict(symbol=symbol, interval=TF_MAP[tf],
                                 outputsize=int(min(n, 5000)), timezone=tz, order="ASC"))
    df = _to_df(j.get("values"), tz)
    if df.empty:
        raise DataError(f"Không có dữ liệu {tf} cho {symbol}")
    return df.iloc[:-1] if drop_forming and len(df) > 1 else df


def get_rates_range(symbol: str, tf: str, start, end, tz: str) -> pd.DataFrame:
    """Dùng cho bộ phân định kết quả trong nhật ký."""
    fmt = "%Y-%m-%d %H:%M:%S"
    s = pd.Timestamp(start).tz_convert(tz).strftime(fmt)
    e = pd.Timestamp(end).tz_convert(tz).strftime(fmt)
    try:
        j = _req("time_series", dict(symbol=symbol, interval=TF_MAP[tf], timezone=tz,
                                     start_date=s, end_date=e, order="ASC", outputsize=5000))
    except DataError:
        return pd.DataFrame()
    return _to_df(j.get("values"), tz)


def get_price(symbol: str) -> float:
    j = _req("price", dict(symbol=symbol))
    try:
        return float(j["price"])
    except (KeyError, TypeError, ValueError):
        raise DataError(f"Không đọc được giá của {symbol}")


def get_tick(symbol: str, assumed_spread: float, fallback: float = 0.0) -> dict:
    """
    Twelve Data không trả bid/ask cho gói miễn phí, nên bid/ask được suy ra từ
    giá giữa cộng trừ nửa spread giả định. Con số này chỉnh ở sidebar.
    """
    try:
        p = get_price(symbol)
    except DataError:
        if not fallback:
            raise
        p = fallback
    h = max(0.0, assumed_spread) / 2.0
    return dict(bid=p - h, ask=p + h, time=time.time(), mid=p)


def symbol_spec(symbol: str) -> dict:
    """
    Không còn broker để hỏi, nên dùng quy ước chuẩn của XAU/USD:
    1 lot = 100 ounce, bước lot 0.01. Đổi trong config nếu broker bạn khác.
    """
    return dict(name=symbol, contract_size=100.0, volume_step=0.01,
                volume_min=0.01, volume_max=100.0, digits=2, point=0.01)


def find_symbols(hint: str = "XAU/USD"):
    out = list(SYMBOLS)
    if hint and hint not in out:
        out.insert(0, hint)
    return out


# ----------------------------------------------------------------------------
# Dữ liệu giả lập — chỉ để xem giao diện khi chưa có khóa API. KHÔNG dùng để trade.
# ----------------------------------------------------------------------------
def demo_rates(tf: str, n: int, tz: str, seed: int = 7) -> pd.DataFrame:
    step = {"M1": 1, "M5": 5, "M15": 15, "H1": 60, "H4": 240}[tf]
    rng = np.random.default_rng(seed + step)
    end = pd.Timestamp.now(tz=tz).floor(f"{step}min")
    idx = pd.date_range(end=end, periods=n, freq=f"{step}min")

    vol = 0.55 * np.sqrt(step / 60.0)
    drift = np.sin(np.linspace(0, 7, n)) * vol * 0.35
    close = 3300 + np.cumsum(rng.normal(0, vol, n) + drift)
    spread = np.abs(rng.normal(0, vol * 0.9, n)) + vol * 0.35
    high = close + spread * rng.uniform(0.3, 1.0, n)
    low = close - spread * rng.uniform(0.3, 1.0, n)
    open_ = np.concatenate([[close[0]], close[:-1]])
    high = np.maximum.reduce([high, open_, close])
    low = np.minimum.reduce([low, open_, close])

    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close,
         "tick_volume": rng.integers(400, 4000, n).astype(float)},
        index=idx).rename_axis("time")
