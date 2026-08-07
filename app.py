import os
import sys
import time
from dataclasses import replace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
import streamlit as st

from config import CFG
from core import data_client as dc
from core.indicators import enrich, pct_rank_last
from core.strategy import evaluate, _in_session
from core.structure import market_structure
from journal import logger as J
from journal.store import get_store

_ICON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "gold.png")
st.set_page_config(page_title="XAU SIGNAL",
                   page_icon=_ICON if os.path.exists(_ICON) else "🪙",
                   layout="wide")

# --- Bảng màu: lân tinh hổ phách trên nền đen. Xanh/đỏ chỉ dùng cho hướng lệnh
#     và trạng thái cổng lọc, không dùng ở bất kỳ chỗ nào khác.
AMB = "#FF9E1B"     # hổ phách chính
AMD = "#8C6314"     # hổ phách mờ — nhãn
RUL = "#2A1E08"     # đường kẻ
INK = "#DCD5C6"     # số liệu
DIM = "#6E6558"     # chú thích
UP = "#00C176"
DN = "#FF4B44"
BG = "#000000"
PNL = "#070706"

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&display=swap');

#MainMenu, footer {display:none;}
header[data-testid="stHeader"] {background:transparent; height:0;
  pointer-events:none;}
[data-testid="stSidebarCollapsedControl"] {display:block !important; z-index:999;
  pointer-events:auto;}
[data-testid="stSidebarCollapsedControl"] svg {color:#FF9E1B; fill:#FF9E1B;}
.stApp {background:#000000;}
.block-container {padding:0.6rem 1.4rem 3rem 1.4rem; max-width:100%;}
html, body, [class*="css"], .stApp, p, div, span, label, th, td, input, button {
  font-family:'IBM Plex Mono', ui-monospace, 'Cascadia Mono', Consolas, monospace !important;
}
/* Icon của Streamlit phải giữ font riêng, ép monospace sẽ hiện ra tên icon */
[data-testid="stIconMaterial"], .material-symbols-rounded, .material-symbols-outlined,
span[data-testid="stIconMaterial"], [class*="material-symbols"] {
  font-family:'Material Symbols Rounded','Material Symbols Outlined' !important;
  color:#FF9E1B;
}

/* ---------- thanh chức năng ---------- */
.fnbar {display:flex; align-items:center; justify-content:space-between;
        border-top:2px solid #FF9E1B; border-bottom:1px solid #2A1E08;
        padding:7px 2px 8px 2px; margin-bottom:14px;
        position:relative; z-index:5;}
.fnbar a.tv {color:#FF9E1B; text-decoration:none; border:1px solid #FF9E1B;
             padding:5px 12px; margin-right:16px; letter-spacing:1.4px;
             display:inline-block; cursor:pointer;}
.fnbar a.tv:hover {background:#FF9E1B; color:#000;}
.fnbar .sym {color:#FF9E1B; font-size:19px; font-weight:700; letter-spacing:3px;}
.fnbar .sub {color:#6E6558; font-size:10.5px; letter-spacing:2px; margin-left:14px;}
.fnbar .rt {color:#8C6314; font-size:10.5px; letter-spacing:1.6px;}

/* ---------- dải xu hướng đa khung ---------- */
.trend {display:flex; align-items:center; gap:0; border:1px solid #2A1E08;
        background:#070706; margin-bottom:12px; flex-wrap:wrap;}
.trend .cell {padding:11px 18px; border-right:1px solid #2A1E08; display:flex;
              align-items:baseline; gap:9px;}
.trend .cell:last-child {border-right:none; margin-left:auto; background:#0C0A06;}
.trend .tf {color:#8C6314; font-size:9.5px; letter-spacing:2px;}
.trend .tv {font-size:13px; font-weight:600; letter-spacing:1px;}
.trend .head {color:#8C6314; font-size:9.5px; letter-spacing:2.4px;
              padding:11px 16px; border-right:1px solid #2A1E08;}
.trend .verdict {font-size:20px; font-weight:700; letter-spacing:3px;}

/* ---------- khối ---------- */
.pnl {border:1px solid #2A1E08; background:#070706; padding:14px 16px; height:100%;}
.lbl {color:#8C6314; font-size:9.5px; letter-spacing:2px; text-transform:uppercase;}
.big {font-size:52px; font-weight:700; letter-spacing:4px; line-height:1.05; margin-top:6px;}
.mid {font-size:34px; font-weight:600; letter-spacing:1px; line-height:1.1; margin-top:6px;}
.note {color:#6E6558; font-size:11.5px; margin-top:9px; line-height:1.6;}
.bar {color:#FF9E1B; font-size:15px; letter-spacing:-1px; margin-top:8px;}

/* ---------- bảng số liệu, tiêu đề đảo màu ---------- */
table.dt {width:100%; border-collapse:collapse; margin-top:2px;}
table.dt th {background:#FF9E1B; color:#000; font-size:9.5px; letter-spacing:1.8px;
             font-weight:700; text-align:right; padding:5px 12px; white-space:nowrap;}
table.dt td {text-align:right; padding:13px 12px 12px 12px; font-size:21px; color:#DCD5C6;
             border-bottom:1px solid #2A1E08; border-left:1px solid #14100A;}
table.dt td:first-child {border-left:none;}

/* ---------- dải cổng lọc, có đường chấm dẫn ---------- */
.gate {display:flex; align-items:baseline; padding:7px 2px; border-bottom:1px solid #14100A;}
.gs {font-size:11px; width:16px; flex:none;}
.gn {color:#DCD5C6; font-size:12px; letter-spacing:1.4px; white-space:nowrap;}
.gl {flex:1; border-bottom:1px dotted #2A1E08; margin:0 10px; transform:translateY(-4px);}
.gv {color:#8C6314; font-size:11.5px; text-align:right; white-space:nowrap;
     max-width:46%; overflow:hidden; text-overflow:ellipsis;}
.gv.on {color:#DCD5C6;}

/* ---------- tabs ---------- */
.stTabs [data-baseweb="tab-list"] {gap:0; border-bottom:1px solid #2A1E08;}
.stTabs [data-baseweb="tab"] {height:34px; padding:0 18px; background:transparent;
  color:#6E6558; font-size:10.5px; letter-spacing:1.8px; border-radius:0;}
.stTabs [aria-selected="true"] {color:#000 !important; background:#FF9E1B !important;}
.stTabs [data-baseweb="tab-highlight"] {display:none;}

/* ---------- sidebar ---------- */
section[data-testid="stSidebar"] {background:#050504; border-right:1px solid #2A1E08;}
section[data-testid="stSidebar"] .block-container {padding-top:1rem;}
section[data-testid="stSidebar"] h3 {color:#FF9E1B !important; font-size:10px !important;
  letter-spacing:2.4px; text-transform:uppercase; border-bottom:1px solid #2A1E08;
  padding-bottom:6px; margin:20px 0 12px 0;}
section[data-testid="stSidebar"] label {color:#8C6314 !important; font-size:10.5px !important;
  letter-spacing:0.4px; line-height:1.5;}
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] {margin-bottom:2px;}
section[data-testid="stSidebar"] input, section[data-testid="stSidebar"] [data-baseweb="select"] > div {
  background:#0D0C0A !important; border:1px solid #2A1E08 !important; border-radius:0 !important;
  color:#DCD5C6 !important;}
section[data-testid="stSidebar"] button {border-radius:0 !important; border:1px solid #FF9E1B !important;
  background:transparent !important; color:#FF9E1B !important; letter-spacing:1.6px;
  font-size:10.5px !important;}
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {font-size:10.5px !important;}

/* ---------- cảnh báo, khung dữ liệu ---------- */
.stAlert {border-radius:0 !important; border:1px solid #2A1E08 !important;}
[data-testid="stDataFrame"] {border:1px solid #2A1E08;}
hr {border-color:#2A1E08; margin:14px 0;}
.cap {color:#6E6558; font-size:10.5px; letter-spacing:1px; margin-top:8px;}
</style>""", unsafe_allow_html=True)

ZK = {"support": "HỖ TRỢ", "resistance": "KHÁNG CỰ", "flip": "ĐẢO VAI"}


def qp(key, default, cast=str):
    """Đọc lựa chọn đã lưu trong URL — sống qua lần tải lại trang."""
    v = st.query_params.get(key)
    if v is None:
        return default
    try:
        return cast(v) if cast is not bool else v == "1"
    except Exception:
        return default


def qp_save(d):
    new = {k: ("1" if v is True else "0" if v is False else str(v)) for k, v in d.items()}
    cur = dict(st.query_params)
    if any(cur.get(k) != v for k, v in new.items()):
        st.query_params.update(new)


def blocks(pct, width=14):
    """Thanh tiến độ bằng ký tự khối — kiểu terminal."""
    f = int(round(max(0.0, min(100.0, pct)) / 100 * width))
    return "█" * f + "░" * (width - f)


# ----------------------------------------------------------------- sidebar
def sidebar():
    st.sidebar.markdown("### Dữ liệu")
    if not dc.has_key():
        st.sidebar.error("Thiếu TWELVEDATA_API_KEY")
        st.error("Chưa cấu hình khóa Twelve Data. Thêm TWELVEDATA_API_KEY vào "
                 ".streamlit/secrets.toml (máy cá nhân) hoặc phần Secrets của "
                 "Streamlit Cloud, rồi tải lại trang.")
        st.stop()

    sym = st.sidebar.selectbox("Symbol", dc.find_symbols(CFG.symbol_hint))

    RF = {"Tắt": None, "60 giây": 60, "2 phút": 120, "5 phút": 300, "15 phút": 900}
    keys = list(RF)
    lab = st.sidebar.selectbox("Tự làm mới", keys,
                               index=keys.index(qp("rf", "2 phút")))

    thr = st.sidebar.slider("Ngưỡng điểm", 40, 90, qp("thr", CFG.min_score, int), 1)
    bal = st.sidebar.number_input("Số dư (USD)", 100.0, 10_000_000.0,
                                  qp("bal", CFG.balance, float), 100.0)
    rp = st.sidebar.number_input("Rủi ro / lệnh (%)", 0.1, 5.0,
                                 qp("rp", CFG.risk_pct, float), 0.1)

    # Không dùng st.expander — CSS nền đen của app làm tiêu đề nó chồng chữ.
    # Ô tick + session_state cho kết quả y hệt mà không lỗi hiển thị.
    st.sidebar.markdown("### Nâng cao")
    adv = st.sidebar.checkbox("Hiện cài đặt nâng cao", False)

    def _adv(key, default, widget=None, *args, **kw):
        if adv and widget is not None:
            return widget(*args, key=key, **kw)
        return st.session_state.get(key, default)

    spread = _adv("a_spread", CFG.assumed_spread, st.sidebar.number_input,
                  "Spread giả định", 0.0, 5.0, CFG.assumed_spread, 0.05)
    rr = _adv("a_rr", CFG.min_rr, st.sidebar.number_input,
              "RR tối thiểu", 1.0, 5.0, CFG.min_rr, 0.5)
    cap = _adv("a_cap", CFG.sl_max_atr_h1, st.sidebar.slider,
               "Trần SL (× ATR H1)", 0.6, 3.0, CFG.sl_max_atr_h1, 0.1)
    s1 = _adv("a_s1", True, st.sidebar.checkbox, "Phiên London 14:00–18:00", True)
    s2 = _adv("a_s2", True, st.sidebar.checkbox, "Phiên New York 19:30–23:00", True)
    ig = _adv("a_ig", False, st.sidebar.checkbox, "Bỏ qua bộ lọc phiên", False)
    saver = _adv("a_saver", CFG.quote_in_session_only, st.sidebar.checkbox,
                 "Chỉ hỏi giá trong phiên", CFG.quote_in_session_only)
    autolog = _adv("a_log", True, st.sidebar.checkbox, "Tự ghi nhật ký", True)

    sessions = ([("14:00", "18:00")] if s1 else []) + ([("19:30", "23:00")] if s2 else [])
    if ig:
        sessions = [("00:00", "23:59")]

    st.sidebar.button("TẢI LẠI DỮ LIỆU", width='stretch',
                      help="Buộc lấy lại nến và giá ngay, tốn khoảng 4 credit.")
    st.sidebar.caption(f"{dc.usage()} / 800 credit hôm nay")

    spec = dc.symbol_spec(sym)
    qp_save(dict(rf=lab, thr=thr, bal=bal, rp=rp))
    cfg = replace(CFG, sessions=sessions, min_score=thr, balance=bal, risk_pct=rp,
                  min_rr=rr, sl_max_atr_h1=cap, use_demo_data=False,
                  assumed_spread=spread, quote_in_session_only=saver)
    return cfg, sym, spec, autolog, RF[lab]


@st.cache_data(ttl=120, show_spinner=False)
def load_frames(sym, tz, n15, n1, n4, bar_key):
    return (dc.get_rates(sym, "M15", n15, tz),
            dc.get_rates(sym, "H1", n1, tz),
            dc.get_rates(sym, "H4", n4, tz))


# ----------------------------------------------------------------- vẽ
def trend_rail(m15, h1, h4, cfg):
    """Xu hướng ba khung. H4 và H1 đọc bằng cấu trúc, M15 đọc bằng EMA."""
    h4b = market_structure(h4, cfg.pivot_left, cfg.pivot_right).bias
    h1b = market_structure(h1, cfg.pivot_left, cfg.pivot_right).bias
    ef, es = float(m15["ema_fast"].iloc[-1]), float(m15["ema_slow"].iloc[-1])
    px = float(m15["close"].iloc[-1])
    m15b = "UP" if (ef > es and px > es) else ("DOWN" if (ef < es and px < es) else "NEUTRAL")

    look = {"UP": ("▲ TĂNG", UP), "DOWN": ("▼ GIẢM", DN), "NEUTRAL": ("■ ĐI NGANG", AMD)}
    cells = "".join(
        f'<div class="cell"><span class="tf">{tf}</span>'
        f'<span class="tv" style="color:{look[b][1]}">{look[b][0]}</span></div>'
        for tf, b in (("H4", h4b), ("H1", h1b), ("M15", m15b)))

    # Chỉ đi theo hướng H4 — đó là cổng cứng số 1 của hệ thống
    if h4b == "UP":
        side, sc = "CHỈ TÌM LỆNH MUA", UP
    elif h4b == "DOWN":
        side, sc = "CHỈ TÌM LỆNH BÁN", DN
    else:
        side, sc = "KHÔNG GIAO DỊCH", AMD
    agree = sum(b == h4b for b in (h1b, m15b)) + 1 if h4b != "NEUTRAL" else 0

    st.markdown(
        f'<div class="trend"><div class="head">XU HƯỚNG</div>{cells}'
        f'<div class="cell"><span class="tf">THIÊN HƯỚNG</span>'
        f'<span class="verdict" style="color:{sc}">{side}</span>'
        f'<span class="tf">{agree}/3 khung đồng thuận</span></div></div>',
        unsafe_allow_html=True)


def verdict(sig, cfg, countdown, passed, total):
    col = {"BUY": UP, "SELL": DN}.get(sig.direction, AMB)
    gc = UP if sig.score >= cfg.min_score else AMB
    a, b = st.columns([5, 2])
    with a:
        st.markdown(f"""<div class="pnl">
          <div class="lbl">Tín hiệu · nến {sig.time:%H:%M}</div>
          <div style="display:flex;align-items:baseline;gap:26px;flex-wrap:wrap">
            <span class="big" style="color:{col}">{sig.direction}</span>
            <span class="mid" style="color:{gc};font-size:26px">{sig.score:.0f}
              <span style="font-size:14px;color:{DIM}">/100 · {sig.grade}</span></span>
            <span class="bar" style="color:{gc}">{blocks(sig.score, 14)}</span>
          </div>
          <div class="note">{passed}/{total} cổng · {countdown}</div>
        </div>""", unsafe_allow_html=True)
    with b:
        st.markdown(f"""<div class="pnl">
          <div class="lbl">Giá</div>
          <div class="mid" style="color:{INK}">{sig.price:,.2f}</div>
          <div class="note">spread {sig.spread:.2f} · {sig.session}</div>
        </div>""", unsafe_allow_html=True)


def datarow(sig, m15, h1):
    p = sig.plan
    if not (sig.direction != "WAIT" and p is not None and p.reject is None):
        atr15 = float(m15["atr"].iloc[-1])
        ap = pct_rank_last(h1["atr_pct"], 200)
        z = min(sig.zones, key=lambda x: abs(x.mid - sig.price)) if sig.zones else None
        zt = f"{z.lo:,.0f}–{z.hi:,.0f} cách {abs(z.mid - sig.price):.1f}" if z else "—"
        st.markdown(f'<div class="cap">ATR M15 {atr15:.2f} · biến động phân vị '
                    f'{ap:.0f} · vùng gần nhất {zt}</div>', unsafe_allow_html=True)
        return

    cells = [("ENTRY", f"{p.entry:,.2f}", INK), ("DỪNG LỖ", f"{p.sl:,.2f}", DN),
             ("CHỐT LỜI", f"{p.tp:,.2f}", UP), ("R:R", f"{p.rr:.2f}", INK),
             ("RỘNG SL", f"{p.sl_dist:.2f}", INK), ("LOT", f"{p.lot:g}", AMB)]
    th = "".join(f"<th>{k}</th>" for k, _, _ in cells)
    td = "".join(f'<td style="color:{c}">{v}</td>' for _, v, c in cells)
    st.markdown(f'<table class="dt"><tr>{th}</tr><tr>{td}</tr></table>',
                unsafe_allow_html=True)


def gate_rail(sig):
    rows = []
    for g in sig.gates:
        col = UP if g.passed else DN
        glyph = "●" if g.passed else "○"
        rows.append(f'<div class="gate"><span class="gs" style="color:{col}">{glyph}</span>'
                    f'<span class="gn">{g.name}</span><span class="gl"></span>'
                    f'<span class="gv{" on" if g.passed else ""}">{g.detail}</span></div>')
    st.markdown("".join(rows), unsafe_allow_html=True)


def score_rail(sig):
    if not sig.parts:
        st.markdown('<div class="cap">Chưa chấm điểm — H4 chưa có cấu trúc rõ ràng.</div>',
                    unsafe_allow_html=True)
        return
    rows = []
    for p in sig.parts:
        pct = p.points / p.max_points * 100 if p.max_points else 0
        col = UP if pct >= 70 else (AMB if pct >= 35 else DN)
        rows.append(
            f'<div class="gate"><span class="gs" style="color:{col};font-size:10px;'
            f'letter-spacing:-1px;width:64px">{blocks(pct, 7)}</span>'
            f'<span class="gn" style="margin-left:12px">{p.name}</span>'
            f'<span class="gl"></span>'
            f'<span class="gv on" style="color:{col}">{p.points:.1f}/{p.max_points}</span>'
            f'<span class="gv" style="margin-left:14px;min-width:290px">{p.detail}</span></div>')
    st.markdown("".join(rows), unsafe_allow_html=True)


def zones_tab(sig):
    if not sig.zones:
        st.markdown('<div class="cap">Chưa dựng được vùng nào.</div>', unsafe_allow_html=True)
        return
    df = pd.DataFrame([{
        "Loại": ZK.get(z.kind, z.kind), "Từ": round(z.lo, 2), "Đến": round(z.hi, 2),
        "Điểm": z.score, "Lần chạm": z.touches, "Lực rời (×ATR)": z.impulse,
        "Tuổi (ngày)": z.age_days, "Có H4": "có" if z.has_h4 else "không",
    } for z in sig.zones[:25]])
    st.dataframe(df, width='stretch', hide_index=True)
    st.markdown('<div class="cap">Vùng bị chạm từ 4 lần trở lên bị trừ điểm: mỗi lần chạm '
                'là một lần thanh khoản bị ăn bớt, không phải một lần xác nhận.</div>',
                unsafe_allow_html=True)


def journal_tab(cfg, sym, store):
    c1, c2 = st.columns([1, 4])
    if c1.button("CẬP NHẬT KẾT QUẢ", width='stretch'):
        with st.spinner("Đang kéo nến để phân định…"):
            n = J.resolve_pending(
                store,
                lambda a, b: dc.get_rates_range(sym, "M15", a, b, cfg.tz_local),
                lambda a, b: dc.get_rates_range(sym, "M1", a, b, cfg.tz_local),
                cfg.resolve_max_bars_m15)
        c2.success(f"Đã phân định thêm {n} lệnh.")

    st.markdown(f'<div class="cap">Đang lưu tại: {store.label}</div>',
                unsafe_allow_html=True)
    df = J.load(store)
    if df.empty:
        st.markdown('<div class="cap">Chưa có tín hiệu nào được ghi.</div>',
                    unsafe_allow_html=True)
        return
    show = df.sort_values("signal_time", ascending=False).copy()
    show["signal_time"] = show["signal_time"].dt.tz_convert(cfg.tz_local)
    st.dataframe(show, width='stretch', hide_index=True)
    st.download_button("TẢI SIGNALS.CSV", df.to_csv(index=False), "signals.csv", "text/csv")


def stats_tab(cfg, store):
    df = J.load(store)
    closed = df[df["status"].isin(["WIN", "LOSS", "EXPIRED"])]
    if closed.empty:
        st.markdown('<div class="cap">Chưa có lệnh nào được phân định. '
                    'Bấm "Cập nhật kết quả" ở tab Nhật ký.</div>', unsafe_allow_html=True)
        return
    n = len(closed[closed["status"].isin(["WIN", "LOSS"])])
    if n < 30:
        st.warning(f"Mới có {n} lệnh đã chốt. Dưới 30 lệnh, sai số WR khoảng ±20% — "
                   f"đủ để dẫn bạn đi sai hướng nếu tưởng nó chính xác.")
    for label, key in ((None, None), ("Theo khoảng điểm", "score_bucket"),
                       ("Theo mẫu PA", "pattern"), ("Theo phiên", "session"),
                       ("Theo bias H4", "h4_bias")):
        t = J.stats(closed, key)
        if not t.empty:
            st.markdown(f'<div class="lbl" style="margin-top:14px">'
                        f'{label or "Tổng thể"}</div>', unsafe_allow_html=True)
            st.dataframe(t, width='stretch')
    mae = closed["mae_r"].mean()
    if pd.notna(mae) and abs(mae) < 0.5:
        st.info(f"MAE trung bình chỉ {mae:.2f}R — SL đang đặt rộng hơn mức cần thiết. "
                f"Cân nhắc siết buffer hoặc trần SL.")


# ----------------------------------------------------------------- main
cfg, sym, spec, autolog, refresh_secs = sidebar()
STORE = get_store(cfg)
TZ = cfg.tz_local


def expected_bar_open(now=None):
    now = now or pd.Timestamp.now(tz=TZ)
    return now.floor("15min") - pd.Timedelta(minutes=15)


def get_tick_now(px, now=None):
    """Ngoài phiên thì dùng giá đóng cửa nến gần nhất, khỏi tiêu credit."""
    h = cfg.assumed_spread / 2.0
    if cfg.quote_in_session_only:
        t = now or pd.Timestamp.now(tz=TZ)
        if not _in_session(t, cfg.sessions)[0]:
            return dict(bid=px - h, ask=px + h, time=0, mid=px)
    return dc.get_tick(sym, cfg.assumed_spread, fallback=px)


def cooldown_anchor():
    h = J.load(STORE)
    if h.empty:
        return None
    same = h[h["symbol"] == sym]
    return None if same.empty else pd.Timestamp(same["signal_time"].max()).tz_convert(TZ)


src = "TWELVE DATA"
st.markdown(f"""<div class="fnbar">
  <div><span class="sym">{sym}</span>
       <span class="sub">M15 ENTRY · H1 VÙNG · H4 XU HƯỚNG</span></div>
<div class="rt"><a class="tv" href="https://www.tradingview.com/chart/?symbol=OANDA%3AXAUUSD" target="_blank" rel="noopener">MỞ BIỂU ĐỒ ↗</a>{src} · {pd.Timestamp.now(tz=TZ):%H:%M} GIỜ VN</div>
</div>""", unsafe_allow_html=True)


try:
    with st.spinner("Đang tải nến…"):
        frames = load_frames(sym, TZ, cfg.n_m15, cfg.n_h1, cfg.n_h4,
                             str(expected_bar_open()))
except Exception as e:
    st.error(f"Không lấy được dữ liệu: {e}")
    st.stop()

m15, h1, h4 = (enrich(x, cfg) for x in frames)
st.session_state["frames"] = (m15, h1, h4)
st.session_state["bar_open"] = m15.index[-1]
st.session_state["anchor"] = cooldown_anchor()

sig_static = evaluate(m15, h1, h4, get_tick_now(float(m15["close"].iloc[-1])),
                      spec, cfg, last_signal_bar=st.session_state["anchor"])


@st.fragment(run_every=refresh_secs)
def live_panel():
    now = pd.Timestamp.now(tz=TZ)
    want, have = expected_bar_open(now), st.session_state.get("bar_open")
    if have is not None and have < want and (now - now.floor("15min")).total_seconds() > 8:
        st.cache_data.clear()
        st.rerun(scope="app")

    m15_, h1_, h4_ = st.session_state["frames"]
    try:
        tick = get_tick_now(float(m15_["close"].iloc[-1]), now)
    except Exception as e:
        st.error(f"Không lấy được giá: {e}")
        return

    sig = evaluate(m15_, h1_, h4_, tick, spec, cfg,
                   last_signal_bar=st.session_state.get("anchor"))

    if autolog and sig.direction != "WAIT":
        if J.append_signal(STORE, sig):
            st.session_state["anchor"] = pd.Timestamp(sig.time)
            st.toast(f"Đã ghi tín hiệu {sig.direction} vào nhật ký", icon="✅")

    mm, ss = divmod(int((now.ceil("15min") - now).total_seconds()), 60)
    cd = f"nến sau {mm:02d}:{ss:02d}"
    if refresh_secs is None:
        cd += " · tự làm mới TẮT"

    trend_rail(m15_, h1_, h4_, cfg)
    passed = sum(1 for g in sig.gates if g.passed)
    verdict(sig, cfg, cd, passed, len(sig.gates))
    st.write("")
    gate_rail(sig)
    datarow(sig, m15_, h1_)
    if sig.plan and sig.plan.block_note:
        st.warning(sig.plan.block_note, icon="⚠️")


live_panel()
st.write("")

t2, t3, t4, t5 = st.tabs(["ĐIỂM CHI TIẾT", "VÙNG S/R", "NHẬT KÝ", "THỐNG KÊ"])
with t2:
    score_rail(sig_static)
with t3:
    zones_tab(sig_static)
with t4:
    journal_tab(cfg, sym, STORE)
with t5:
    stats_tab(cfg, STORE)

st.markdown('<div class="cap" style="margin-top:22px;border-top:1px solid #2A1E08;'
            'padding-top:10px">Công cụ hỗ trợ ra quyết định, không phải lời khuyên đầu tư. '
            'Hãy chạy demo một thời gian trước khi tin nó bằng tiền thật.</div>',
            unsafe_allow_html=True)
