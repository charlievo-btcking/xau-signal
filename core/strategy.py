"""
Bo may tin hieu: 5 cong cung (bat buoc) + diem chat luong 0-100 (khong loai lenh).

H4 -> xu huong (cau truc HH/HL)
H1 -> vung gia tri (fibo hoi hoac vung S/R manh)
M15 -> kich hoat (mau price action)
"""
from dataclasses import dataclass, field
from datetime import datetime, time as dtime
from typing import List, Optional, Tuple
import numpy as np
import pandas as pd

from . import patterns as pat
from .indicators import pct_rank_last
from .risk import build_plan, RiskPlan
from .structure import market_structure, last_impulse, fib_zone
from .zones import build_zones, nearest_zone, Zone
from config import grade_of


@dataclass
class Gate:
    name: str
    passed: bool
    detail: str


@dataclass
class ScorePart:
    name: str
    points: float
    max_points: float
    detail: str


@dataclass
class Signal:
    time: pd.Timestamp
    symbol: str
    direction: str                       # 'BUY' | 'SELL' | 'WAIT'
    gates: List[Gate] = field(default_factory=list)
    parts: List[ScorePart] = field(default_factory=list)
    score: float = 0.0
    grade: str = "-"
    plan: Optional[RiskPlan] = None
    reason: str = ""
    h4_bias: str = "NEUTRAL"
    h4_detail: str = ""
    pattern: str = ""
    session: str = ""
    zone: Optional[Zone] = None
    zone_source: str = ""
    entry_zone: Optional[Tuple[float, float]] = None
    zones: List[Zone] = field(default_factory=list)
    price: float = 0.0
    spread: float = 0.0


def _in_session(ts: pd.Timestamp, sessions) -> Tuple[bool, str]:
    t = ts.time()
    for s, e in sessions:
        sh, sm = map(int, s.split(":"))
        eh, em = map(int, e.split(":"))
        if dtime(sh, sm) <= t < dtime(eh, em):
            return True, f"{s}-{e}"
    return False, "ngoai phien"


def evaluate(m15, h1, h4, tick, spec, cfg, last_signal_bar=None) -> Signal:
    """
    m15/h1/h4: DataFrame da qua enrich(), chi chua NEN DA DONG, index gio VN.
    tick: dict(bid, ask, time) — gia thuc te de tinh lai RR.
    """
    i = len(m15) - 1
    bar_time = m15.index[-1]
    close_time = bar_time + pd.Timedelta(minutes=15)
    price = float(m15["close"].iloc[-1])
    atr15 = float(m15["atr"].iloc[-1])
    atr_h1 = float(h1["atr"].iloc[-1])
    spread = max(0.0, float(tick["ask"] - tick["bid"]))

    sig = Signal(time=close_time, symbol=spec["name"], direction="WAIT",
                 price=price, spread=spread)

    # ---------- Cong 1: cau truc H4 ----------
    st = market_structure(h4, cfg.pivot_left, cfg.pivot_right)
    sig.h4_bias, sig.h4_detail = st.bias, st.detail
    g1 = Gate("CẤU TRÚC H4", st.bias != "NEUTRAL", f"{st.bias} — {st.detail}")
    sig.gates.append(g1)

    # ---------- Cong 2: phien giao dich ----------
    ok_sess, sess_name = _in_session(close_time, cfg.sessions)
    sig.session = sess_name
    sig.gates.append(Gate("PHIÊN GIAO DỊCH", ok_sess,
                          f"{close_time:%H:%M} giờ VN — {sess_name}"))

    if not g1.passed:
        sig.reason = "H4 chưa có cấu trúc rõ ràng"
        sig.zones = build_zones(h4, h1, cfg)
        return sig

    direction = "BUY" if st.bias == "UP" else "SELL"
    zones = build_zones(h4, h1, cfg)
    sig.zones = zones

    # ---------- Cong 3: vung gia tri H1 ----------
    imp = last_impulse(h1, st.bias, cfg.impulse_lookback_h1)
    fz = fib_zone(imp, cfg.fib_min, cfg.fib_max)
    in_fib = fz is not None and fz[0] <= price <= fz[1]

    want = "support" if direction == "BUY" else "resistance"
    z = nearest_zone(zones, price, want, pad=0.3 * atr15)
    in_zone = z is not None and z.score >= cfg.zone_min_score

    sources = []
    if in_fib:
        sources.append(f"fibo {cfg.fib_min:.3f}–{cfg.fib_max:.3f} ({fz[0]:.2f}–{fz[1]:.2f})")
    if in_zone:
        sources.append(f"vùng {z.kind} {z.lo:.2f}–{z.hi:.2f} điểm {z.score}")
    sig.zone = z if in_zone else None
    sig.zone_source = " + ".join(sources)
    sig.entry_zone = fz

    ok_zone = in_fib or in_zone
    sig.gates.append(Gate("VÙNG GIÁ TRỊ H1", ok_zone,
                          sig.zone_source or f"giá {price:.2f} ngoài mọi vùng"))

    # ---------- Cong 4: mau price action M15 ----------
    p = pat.detect(m15, i, direction, atr15, cfg)
    sig.pattern = p.name if p else ""
    sig.gates.append(Gate("MẪU PA TRÊN M15", p is not None,
                          f"{p.name} — {p.detail}" if p else "chưa có mẫu kích hoạt"))

    hard_ok = ok_sess and ok_zone and (p is not None)

    # ---------- Cong 5: RR sau spread ----------
    entry = float(tick["ask"]) if direction == "BUY" else float(tick["bid"])
    plan = build_plan(direction, entry, m15, i, atr15, atr_h1, zones, spec, cfg)
    ok_rr = plan.reject is None
    sig.plan = plan
    sig.gates.append(Gate(f"RR ≥ {cfg.min_rr:g} SAU SPREAD", ok_rr,
                          plan.reject or f"RR {plan.rr:.2f} — SL rộng {plan.sl_dist:.2f} "
                                         f"(spread {spread:.2f})"))

    # ---------- Diem chat luong ----------
    parts: List[ScorePart] = []

    q = p.quality if p else 0.0
    parts.append(ScorePart("Chất lượng mẫu nến", q * cfg.w_pattern, cfg.w_pattern,
                           f"{p.name} q={q:.2f}" if p else "không có mẫu"))

    k = float(m15["stoch_k"].iloc[-1]) if np.isfinite(m15["stoch_k"].iloc[-1]) else 50.0
    d = float(m15["stoch_d"].iloc[-1]) if np.isfinite(m15["stoch_d"].iloc[-1]) else 50.0
    recent_k = m15["stoch_k"].iloc[-4:-1]
    if direction == "BUY":
        cross = k > d
        extreme = bool((recent_k < 20).any())
    else:
        cross = k < d
        extreme = bool((recent_k > 80).any())
    s_stoch = cfg.w_stoch * (0.6 * float(cross) + 0.4 * float(extreme))
    parts.append(ScorePart("Stoch RSI M15", s_stoch, cfg.w_stoch,
                           f"%K {k:.0f} / %D {d:.0f} · "
                           f"{'cắt đúng chiều' if cross else 'chưa cắt'} · "
                           f"{'đã chạm vùng cực trị' if extreme else 'chưa chạm cực trị'}"))

    if z is not None:
        fresh = max(0.0, 1.0 - min(z.touches, 5) / 5.0) * 0.6 + float(np.exp(-z.age_days / 45.0)) * 0.4
        det = f"{z.touches} lần chạm · {z.age_days:.0f} ngày tuổi"
    else:
        fresh, det = 0.3, "không dựa trên vùng S/R"
    parts.append(ScorePart("Độ tươi của vùng", fresh * cfg.w_zone_fresh, cfg.w_zone_fresh, det))

    if z is not None:
        conf = min(1.0, z.score / 85.0)
        det = f"vùng điểm {z.score} · {' · '.join(z.parts)}"
    else:
        conf, det = 0.0, "entry không trùng vùng S/R nào"
    parts.append(ScorePart("Trùng vùng S/R mạnh", conf * cfg.w_sr_confluence,
                           cfg.w_sr_confluence, det))

    vw = float(h1["vwap"].iloc[-1]) if "vwap" in h1 else np.nan
    near_vwap = np.isfinite(vw) and abs(price - vw) <= 0.4 * atr_h1
    step = cfg.round_number_step
    near_round = abs(price - round(price / step) * step) <= cfg.round_number_tol_atr * atr15
    s_vr = cfg.w_vwap_round * (0.6 * float(near_vwap) + 0.4 * float(near_round))
    parts.append(ScorePart("VWAP / mốc tròn", s_vr, cfg.w_vwap_round,
                           f"{'gần VWAP ' + format(vw, '.2f') if near_vwap else 'xa VWAP'} · "
                           f"{'gần mốc tròn' if near_round else 'xa mốc tròn'}"))

    ap = pct_rank_last(h1["atr_pct"], cfg.atr_pct_lookback)
    if ap < cfg.atr_pct_low or ap > cfg.atr_pct_high:
        s_atr = 0.0
    elif cfg.atr_pct_ideal_low <= ap <= cfg.atr_pct_ideal_high:
        s_atr = float(cfg.w_atr_regime)
    else:
        s_atr = cfg.w_atr_regime * 0.5
    parts.append(ScorePart("Chế độ biến động", s_atr, cfg.w_atr_regime,
                           f"ATR% {float(h1['atr_pct'].iloc[-1]):.3f} — phân vị {ap:.0f}"))

    if st.bars_since_bos is None:
        s_ty, det = cfg.w_trend_youth * 0.3, "không xác định được BOS"
    else:
        ratio = max(0.0, 1.0 - st.bars_since_bos / max(cfg.trend_young_bars, 1))
        s_ty = cfg.w_trend_youth * (0.3 + 0.7 * ratio)
        det = f"BOS cách đây {st.bars_since_bos} nến H4"
    parts.append(ScorePart("Độ trẻ của trend", s_ty, cfg.w_trend_youth, det))

    sig.parts = parts
    sig.score = round(sum(x.points for x in parts), 1)
    sig.grade = grade_of(sig.score)

    # ---------- Ket luan ----------
    if not hard_ok or not ok_rr:
        failed = [g.name for g in sig.gates if not g.passed]
        sig.reason = "Chưa qua · " + " · ".join(failed)
        return sig

    if last_signal_bar is not None:
        gap = (close_time - last_signal_bar).total_seconds() / 900.0
        if gap < cfg.cooldown_bars_m15:
            sig.reason = f"Đang khóa sau tín hiệu trước ({gap:.0f}/{cfg.cooldown_bars_m15} nến M15)"
            return sig

    if sig.score < cfg.min_score:
        sig.reason = f"Điểm {sig.score} dưới ngưỡng {cfg.min_score}"
        return sig

    sig.direction = direction
    sig.reason = "Đủ điều kiện vào lệnh"
    return sig
