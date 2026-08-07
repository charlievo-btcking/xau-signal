import os
import sys
import time
from dataclasses import replace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import CFG
from core import data_client as dc
from core.indicators import enrich, pct_rank_last
from core.strategy import evaluate, _in_session
from journal import logger as J
from journal.store import get_store

st.set_page_config(page_title="XAU TERMINAL", page_icon="📈", layout="wide")

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

#MainMenu, footer, header[data-testid="stHeader"] {display:none;}
.stApp {background:#000000;}
.block-container {padding:0.6rem 1.4rem 3rem 1.4rem; max-width:100%;}
html, body, [class*="css"], .stApp, p, div, span, label, th, td, input, button {
  font-family:'IBM Plex Mono', ui-monospace, 'Cascadia Mono', Consolas, monospace !important;
}

/* ---------- thanh chức năng ---------- */
.fnbar {display:flex; align-items:center; justify-content:space-between;
        border-top:2px solid #FF9E1B; border-bottom:1px solid #2A1E08;
        padding:7px 2px 8px 2px; margin-bottom:14px;}
.fnbar .sym {color:#FF9E1B; font-size:19px; font-weight:700; letter-spacing:3px;}
.fnbar .sub {color:#6E6558; font-size:10.5px; letter-spacing:2px; margin-left:14px;}
.fnbar .rt {color:#8C6314; font-size:10.5px; letter-spacing:1.6px;}

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
.gv {color:#8C6314; font-size:11.5px; text-align:right; white-space:nowrap;}
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
  letter-spacing:1px;}
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


def blocks(pct, width=14):
    """Thanh tiến độ bằng ký tự khối — kiểu terminal."""
    f = int(round(max(0.0, min(100.0, pct)) / 100 * width))
    return "█" * f + "░" * (width - f)


# ----------------------------------------------------------------- sidebar
def sidebar():
    st.sidebar.markdown("### Nguồn dữ liệu")
    has = dc.has_key()
    demo = st.sidebar.toggle("Chế độ giả lập (không cần API)", value=not has)

    if not demo and not has:
        st.sidebar.error("Chưa có TWELVEDATA_API_KEY trong secrets.")
        demo = True
    if not demo:
        st.sidebar.success("Twelve Data đã sẵn sàng", icon="✅")

    sym = st.sidebar.selectbox("Symbol", dc.find_symbols(CFG.symbol_hint))
    spread = st.sidebar.number_input("Spread giả định", 0.0, 5.0, CFG.assumed_spread, 0.05,
                                     help="Twelve Data không trả bid/ask. Đặt bằng spread "
                                          "trung bình của broker bạn để RR sát thực tế.")
    spec = dc.symbol_spec(sym)

    seed = 7
    if demo:
        seed = st.sidebar.number_input("Seed dữ liệu giả lập", 0, 999, 7, 1)
    else:
        st.sidebar.caption(f"Đã dùng {dc.usage()} credit hôm nay · hạn mức 800/ngày")

    st.sidebar.markdown("### Bộ lọc")
    thr = st.sidebar.slider("Ngưỡng điểm tối thiểu", 40, 90, CFG.min_score, 1,
                            help="Kéo lên: ít lệnh, chất lượng cao. Kéo xuống: nhiều lệnh hơn.")
    s1 = st.sidebar.checkbox("Phiên London 14:00–18:00", True)
    s2 = st.sidebar.checkbox("Phiên New York 19:30–23:00", True)
    ig = st.sidebar.checkbox("Bỏ qua bộ lọc phiên", False)
    sessions = ([("14:00", "18:00")] if s1 else []) + ([("19:30", "23:00")] if s2 else [])
    if ig:
        sessions = [("00:00", "23:59")]

    st.sidebar.markdown("### Rủi ro")
    bal = st.sidebar.number_input("Số dư tài khoản (USD)", 100.0, 10_000_000.0, CFG.balance, 100.0)
    rp = st.sidebar.number_input("Rủi ro mỗi lệnh (%)", 0.1, 5.0, CFG.risk_pct, 0.1)
    rr = st.sidebar.number_input("RR tối thiểu", 1.0, 5.0, CFG.min_rr, 0.5)
    cap = st.sidebar.slider("Trần SL (× ATR H1)", 0.6, 3.0, CFG.sl_max_atr_h1, 0.1)

    st.sidebar.markdown("### Nhật ký")
    autolog = st.sidebar.checkbox("Tự ghi tín hiệu", True)

    st.sidebar.markdown("### Làm mới")
    opt = {"Tắt": None, "30 giây": 30, "60 giây": 60, "2 phút": 120, "5 phút": 300}
    lab = st.sidebar.selectbox("Tự làm mới bảng giá", list(opt), index=2,
                               help="Mỗi lần làm mới tốn 1 credit. Chu kỳ càng ngắn, "
                                    "hạn mức 800/ngày càng nhanh hết.")
    saver = st.sidebar.checkbox("Chỉ hỏi giá trong giờ phiên", CFG.quote_in_session_only,
                                help="Ngoài phiên dùng giá đóng cửa của nến gần nhất, "
                                     "không tiêu credit.")
    st.sidebar.button("VẼ LẠI TOÀN BỘ", width='stretch')

    cfg = replace(CFG, sessions=sessions, min_score=thr, balance=bal, risk_pct=rp,
                  min_rr=rr, sl_max_atr_h1=cap, use_demo_data=demo,
                  assumed_spread=spread, quote_in_session_only=saver)
    return cfg, sym, spec, autolog, opt[lab], seed


@st.cache_data(ttl=120, show_spinner=False)
def load_frames(sym, tz, demo, n15, n1, n4, seed, bar_key):
    if demo:
        return (dc.demo_rates("M15", n15, tz, seed), dc.demo_rates("H1", n1, tz, seed),
                dc.demo_rates("H4", n4, tz, seed))
    return (dc.get_rates(sym, "M15", n15, tz),
            dc.get_rates(sym, "H1", n1, tz),
            dc.get_rates(sym, "H4", n4, tz))


# ----------------------------------------------------------------- vẽ
def verdict(sig, cfg, countdown):
    col = {"BUY": UP, "SELL": DN}.get(sig.direction, AMB)
    gc = UP if sig.score >= cfg.min_score else AMB
    a, b, c = st.columns([3, 3, 2])
    with a:
        st.markdown(f"""<div class="pnl">
          <div class="lbl">Tín hiệu · nến M15 đóng lúc {sig.time:%d/%m %H:%M}</div>
          <div class="big" style="color:{col}">{sig.direction}</div>
          <div class="note">{sig.reason}</div>
          <div class="note" style="color:{AMD}">{countdown}</div>
        </div>""", unsafe_allow_html=True)
    with b:
        st.markdown(f"""<div class="pnl">
          <div class="lbl">Điểm chất lượng · ngưỡng {cfg.min_score}</div>
          <div class="mid" style="color:{gc}">{sig.score:.0f}<span style="font-size:17px;
             color:{DIM}"> / 100 · hạng {sig.grade}</span></div>
          <div class="bar" style="color:{gc}">{blocks(sig.score, 18)}</div>
          <div class="note">H4 {sig.h4_bias} — {sig.h4_detail}</div>
        </div>""", unsafe_allow_html=True)
    with c:
        st.markdown(f"""<div class="pnl">
          <div class="lbl">Giá hiện tại</div>
          <div class="mid" style="color:{INK}">{sig.price:,.2f}</div>
          <div class="note">Spread {sig.spread:.2f} · {sig.session}</div>
        </div>""", unsafe_allow_html=True)


def datarow(sig, m15, h1, countdown):
    p = sig.plan
    live = sig.direction != "WAIT" and p is not None and p.reject is None
    if live:
        cells = [("ENTRY", f"{p.entry:,.2f}", INK), ("DỪNG LỖ", f"{p.sl:,.2f}", DN),
                 ("CHỐT LỜI", f"{p.tp:,.2f}", UP), ("R:R", f"{p.rr:.2f}", INK),
                 ("ĐỘ RỘNG SL", f"{p.sl_dist:.2f}", INK), ("KHỐI LƯỢNG", f"{p.lot:g}", AMB)]
    else:
        # Lúc chờ, ô trống không nói gì — thay bằng thông số theo dõi được.
        atr15 = float(m15["atr"].iloc[-1])
        ap = pct_rank_last(h1["atr_pct"], 200)
        z = min(sig.zones, key=lambda x: abs(x.mid - sig.price)) if sig.zones else None
        zt = f"{z.lo:,.0f}–{z.hi:,.0f}" if z else "—"
        zd = f"{abs(z.mid - sig.price):.2f}" if z else "—"
        cells = [("GIÁ", f"{sig.price:,.2f}", INK), ("SPREAD", f"{sig.spread:.2f}", INK),
                 ("ATR M15", f"{atr15:.2f}", INK), ("ATR% H1 · PHÂN VỊ", f"{ap:.0f}", INK),
                 ("VÙNG GẦN NHẤT", zt, AMB), ("CÁCH VÙNG", zd, INK)]
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


def chart(sig, m15, cfg, bars=90):
    d = m15.tail(bars)
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=d.index, open=d["open"], high=d["high"], low=d["low"], close=d["close"],
        increasing=dict(line=dict(color=UP, width=1), fillcolor=UP),
        decreasing=dict(line=dict(color=DN, width=1), fillcolor=DN), name="M15"))
    fig.add_trace(go.Scatter(x=d.index, y=d["ema_fast"], mode="lines", name="EMA20",
                             line=dict(color=AMB, width=1.1)))
    fig.add_trace(go.Scatter(x=d.index, y=d["ema_slow"], mode="lines", name="EMA50",
                             line=dict(color=AMD, width=1.1)))
    if "vwap" in d:
        fig.add_trace(go.Scatter(x=d.index, y=d["vwap"], mode="lines", name="VWAP",
                                 line=dict(color=DIM, width=1, dash="dot")))

    lo, hi = float(d["low"].min()), float(d["high"].max())
    pad = (hi - lo) * 0.06
    x0, x1 = d.index[0], d.index[-1]
    for z in sig.zones[:16]:
        if z.hi < lo - pad or z.lo > hi + pad:
            continue
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=z.lo, y1=z.hi, layer="below",
                      fillcolor=AMB, opacity=0.04 + 0.09 * min(1, z.score / 100),
                      line=dict(width=0))
        fig.add_annotation(x=x1, y=z.hi, text=f"{ZK.get(z.kind, z.kind)} {z.score:.0f}",
                           showarrow=False, xanchor="right", yanchor="bottom",
                           font=dict(size=8.5, color=AMD, family="IBM Plex Mono"))

    if sig.entry_zone:
        fig.add_hrect(y0=sig.entry_zone[0], y1=sig.entry_zone[1], line_width=0,
                      fillcolor=AMB, opacity=0.05)

    p = sig.plan
    if p and sig.direction != "WAIT" and p.reject is None:
        for y, c, t in ((p.entry, INK, "ENTRY"), (p.sl, DN, "SL"), (p.tp, UP, "TP")):
            fig.add_hline(y=y, line=dict(color=c, width=1, dash="dash"),
                          annotation_text=f"{t} {y:,.2f}", annotation_position="left",
                          annotation_font=dict(size=9.5, color=c, family="IBM Plex Mono"))

    fig.update_layout(
        height=640, margin=dict(l=6, r=6, t=10, b=6),
        paper_bgcolor=BG, plot_bgcolor="#040403", showlegend=False,
        font=dict(color=AMD, size=10, family="IBM Plex Mono"),
        xaxis_rangeslider_visible=False,
        xaxis=dict(gridcolor="#14100A", linecolor=RUL, zeroline=False,
                   showspikes=True, spikecolor=AMD, spikethickness=1, spikedash="dot"),
        yaxis=dict(gridcolor="#14100A", linecolor=RUL, zeroline=False, side="right",
                   showspikes=True, spikecolor=AMD, spikethickness=1, spikedash="dot"))
    st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})


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


def journal_tab(cfg, sym, store, demo):
    c1, c2 = st.columns([1, 4])
    if c1.button("CẬP NHẬT KẾT QUẢ", width='stretch', disabled=demo):
        with st.spinner("Đang kéo nến để phân định…"):
            n = J.resolve_pending(
                store,
                lambda a, b: dc.get_rates_range(sym, "M15", a, b, cfg.tz_local),
                lambda a, b: dc.get_rates_range(sym, "M1", a, b, cfg.tz_local),
                cfg.resolve_max_bars_m15)
        c2.success(f"Đã phân định thêm {n} lệnh.")
    if demo:
        c2.markdown('<div class="cap">Chế độ giả lập không phân định kết quả.</div>',
                    unsafe_allow_html=True)

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
cfg, sym, spec, autolog, refresh_secs, seed = sidebar()
STORE = get_store(cfg)
TZ = cfg.tz_local


def expected_bar_open(now=None):
    now = now or pd.Timestamp.now(tz=TZ)
    return now.floor("15min") - pd.Timedelta(minutes=15)


def get_tick_now(px, now=None):
    """Ngoài phiên thì dùng giá đóng cửa nến gần nhất, khỏi tiêu credit."""
    h = cfg.assumed_spread / 2.0
    if cfg.use_demo_data:
        return dict(bid=px - h, ask=px + h, time=0, mid=px)
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


src = "GIẢ LẬP" if cfg.use_demo_data else "TWELVE DATA"
st.markdown(f"""<div class="fnbar">
  <div><span class="sym">{sym}</span>
       <span class="sub">M15 ENTRY · H1 VÙNG · H4 XU HƯỚNG</span></div>
  <div class="rt">NGUỒN {src} · {pd.Timestamp.now(tz=TZ):%d/%m/%Y %H:%M} GIỜ VN</div>
</div>""", unsafe_allow_html=True)

if cfg.use_demo_data:
    st.error("DỮ LIỆU GIẢ LẬP — chỉ để xem giao diện. Không dùng để vào lệnh.", icon="⚠️")

try:
    with st.spinner("Đang tải nến…"):
        frames = load_frames(sym, TZ, cfg.use_demo_data,
                             cfg.n_m15, cfg.n_h1, cfg.n_h4, seed, str(expected_bar_open()))
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

    if autolog and sig.direction != "WAIT" and not cfg.use_demo_data:
        if J.append_signal(STORE, sig):
            st.session_state["anchor"] = pd.Timestamp(sig.time)
            st.toast(f"Đã ghi tín hiệu {sig.direction} vào nhật ký", icon="✅")

    mm, ss = divmod(int((now.ceil("15min") - now).total_seconds()), 60)
    cd = f"Nến M15 tiếp theo đóng sau {mm:02d}:{ss:02d}"
    if refresh_secs is None:
        cd += " · tự làm mới đang TẮT"

    verdict(sig, cfg, cd)
    st.write("")
    datarow(sig, m15_, h1_, cd)
    if sig.plan and sig.plan.block_note:
        st.warning(sig.plan.block_note, icon="⚠️")

    st.markdown('<div class="lbl" style="margin-top:20px">Năm cổng cứng · '
                'phải qua hết mới có tín hiệu</div>', unsafe_allow_html=True)
    gate_rail(sig)
    st.markdown(f'<div class="cap">Giá cập nhật {now:%H:%M:%S} · biểu đồ và vùng S/R '
                f'tính từ nến đóng lúc '
                f'{st.session_state["bar_open"] + pd.Timedelta(minutes=15):%H:%M}</div>',
                unsafe_allow_html=True)


live_panel()
st.write("")

t1, t2, t3, t4, t5 = st.tabs(["BIỂU ĐỒ", "ĐIỂM CHI TIẾT", "VÙNG S/R", "NHẬT KÝ", "THỐNG KÊ"])
with t1:
    chart(sig_static, m15, cfg)
with t2:
    score_rail(sig_static)
with t3:
    zones_tab(sig_static)
with t4:
    journal_tab(cfg, sym, STORE, cfg.use_demo_data)
with t5:
    stats_tab(cfg, STORE)

st.markdown('<div class="cap" style="margin-top:22px;border-top:1px solid #2A1E08;'
            'padding-top:10px">Công cụ hỗ trợ ra quyết định, không phải lời khuyên đầu tư. '
            'Hãy chạy demo một thời gian trước khi tin nó bằng tiền thật.</div>',
            unsafe_allow_html=True)
