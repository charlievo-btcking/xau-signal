"""
Toan bo tham so cua he thong. Sua o day, khong sua trong core/.
"""
from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class Config:
    # ---------- Du lieu ----------
    symbol_hint: str = "XAU/USD"     # ký hiệu của Twelve Data
    n_m15: int = 600
    n_h1: int = 400
    n_h4: int = 250
    tz_local: str = "Asia/Ho_Chi_Minh"
    use_demo_data: bool = False      # True = chạy bằng dữ liệu giả lập
    assumed_spread: float = 0.25     # Twelve Data không trả bid/ask → spread giả định
    quote_in_session_only: bool = True   # ngoài phiên thì không gọi giá, để tiết kiệm credit

    # ---------- Phien giao dich (gio VN) ----------
    sessions: List[Tuple[str, str]] = field(
        default_factory=lambda: [("14:00", "18:00"), ("19:30", "23:00")]
    )

    # ---------- H4: cau truc thi truong ----------
    pivot_left: int = 2               # fractal 5 nen = 2 trai + 2 phai
    pivot_right: int = 2
    trend_young_bars: int = 12        # BOS trong bao nhieu nen H4 thi coi la trend con tre

    # ---------- H1: vung vao lenh ----------
    fib_min: float = 0.382
    fib_max: float = 0.786
    impulse_lookback_h1: int = 40     # tim chan song day gan nhat trong bao nhieu nen H1

    # ---------- Vung S/R ----------
    zone_merge_atr: float = 0.40      # gop pivot cach nhau duoi 0.4 x ATR(H4)
    zone_min_score: int = 60          # diem toi thieu de vung duoc dung lam vung vao lenh
    zone_block_score: int = 70        # diem toi thieu de vung chan duong di toi TP
    zone_touch_gap: int = 5           # 2 lan cham phai cach nhau it nhat 5 nen H1
    zone_impulse_bars: int = 12       # do luc roi vung trong bao nhieu nen
    zone_max_age_days: int = 120

    # ---------- M15: mau price action ----------
    pin_wick_ratio: float = 0.55      # duoi nen toi thieu 55% bien do
    pin_body_ratio: float = 0.40      # than nen toi da 40% bien do
    engulf_min_body_atr: float = 0.35 # than nen nhan chim toi thieu 0.35 x ATR(M15)
    bos_lookback_m15: int = 20

    # ---------- Chi bao ----------
    ema_fast: int = 20
    ema_slow: int = 50
    atr_period: int = 14
    rsi_period: int = 14
    stoch_period: int = 14
    stoch_k: int = 3
    stoch_d: int = 3
    atr_pct_lookback: int = 200
    atr_pct_low: float = 10.0         # ngoai dai nay thi diem che do bien dong = 0
    atr_pct_high: float = 95.0
    atr_pct_ideal_low: float = 30.0
    atr_pct_ideal_high: float = 80.0

    # ---------- Rui ro ----------
    min_rr: float = 2.0
    sl_buffer_atr_m15: float = 0.20   # dem them ngoai swing M15
    sl_max_atr_h1: float = 1.20       # SL khong duoc xa hon 1.2 x ATR(H1)
    sl_min_atr_m15: float = 0.60      # SL khong duoc hep hon 0.6 x ATR(M15)
    swing_lookback_m15: int = 12
    round_number_step: float = 5.0    # moc tron cua vang
    round_number_tol_atr: float = 0.25

    # ---------- Cham diem (tong = 100) ----------
    w_pattern: int = 20
    w_stoch: int = 12
    w_zone_fresh: int = 15
    w_sr_confluence: int = 20
    w_vwap_round: int = 10
    w_atr_regime: int = 13
    w_trend_youth: int = 10

    min_score: int = 60               # nguong mac dinh, chinh duoc bang thanh truot

    # ---------- Chong spam ----------
    cooldown_bars_m15: int = 8        # khoa cung chieu 8 nen M15 (~2 gio)

    # ---------- Tai khoan ----------
    balance: float = 1000.0
    risk_pct: float = 1.0

    # ---------- Nhat ky ----------
    journal_path: str = "signals.csv"        # dùng khi chạy máy cá nhân
    sheet_name: str = "XAU Signal Journal"   # dùng khi deploy lên cloud
    sheet_worksheet: str = "signals"
    resolve_max_bars_m15: int = 48    # qua 12 gio chua cham gi thi EXPIRED


CFG = Config()


def grade_of(score: float) -> str:
    if score >= 85:
        return "A+"
    if score >= 75:
        return "A"
    if score >= 65:
        return "B"
    if score >= 55:
        return "C"
    return "D"
