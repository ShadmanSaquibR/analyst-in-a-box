import io
import json
import os
import queue
import re
import textwrap
import threading
import traceback
from datetime import datetime

import streamlit as st
import yfinance as yf

DEMO_MODE = os.getenv("DEMO_MODE", "0") == "1"
# ==========================================
# PAGE CONFIG
# ==========================================
st.set_page_config(
    page_title="Analyst in a Box",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, .stApp {
    background-color: #0d1117;
    color: #c9d1d9;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}
#MainMenu, header, footer { visibility: hidden; }

h1, h2, h3, h4 { color: #f0f6fc !important; font-weight: 600 !important; letter-spacing: -0.3px; }
p, li { color: #8b949e; }
hr { border-color: #21262d !important; margin: 1.2rem 0 !important; }

/* Input */
.stTextInput input {
    background-color: #161b22 !important;
    color: #c9d1d9 !important;
    border: 1px solid #30363d !important;
    border-radius: 6px !important;
    font-size: 0.95rem !important;
    padding: 10px 14px !important;
}
.stTextInput input::placeholder {
    font-style: italic !important;
}

/* Buttons (Updated to Hollow/Ghost Green style) */
.stButton button {
    background-color: transparent !important;
    border: 1.5px solid #3fb950 !important;
    border-radius: 6px !important;
    padding: 8px 16px !important;
    width: 100%;
    transition: all 0.2s ease;
}

/* Force the text INSIDE the button to be green */
.stButton button p {
    color: #3fb950 !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
    margin: 0 !important;
}

/* Hover state */
.stButton button:hover { 
    background-color: rgba(63, 185, 80, 0.1) !important; 
    border-color: #3fb950 !important; 
}
.stButton button:hover p {
    color: #3fb950 !important;
}
.stDownloadButton button:hover {
    background-color: #21262d !important;
    border-color: #8b949e !important;
    color: #f0f6fc !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background-color: transparent !important;
    border-bottom: 1px solid #21262d !important;
    gap: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    background-color: transparent !important;
    color: #8b949e !important;
    border-radius: 0 !important;
    border-bottom: 2px solid transparent !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
    padding: 10px 20px !important;
}
.stTabs [aria-selected="true"] {
    color: #f0f6fc !important;
    border-bottom: 2px solid #388bfd !important;
    background-color: transparent !important;
}
.stTabs [data-baseweb="tab-panel"] { padding-top: 24px !important; }

/* Sentiment card */
.sentiment-card {
    background-color: #161b22;
    border: 1px solid #21262d;
    border-radius: 8px;
    padding: 16px 18px;
    margin-bottom: 10px;
    border-left: 3px solid;
}

/* KPI card */
.kpi-card {
    background-color: #161b22;
    border: 1px solid #21262d;
    border-radius: 8px;
    padding: 18px 20px;
    text-align: center;
}
.kpi-label { font-size: 0.72rem; color: #8b949e; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px; }
.kpi-value { font-size: 1.55rem; font-weight: 700; color: #f0f6fc; font-variant-numeric: tabular-nums; }
.kpi-trend { font-size: 0.78rem; margin-top: 4px; }
.kpi-trend.up { color: #3fb950; }
.kpi-trend.down { color: #f85149; }
.kpi-trend.flat { color: #8b949e; }

/* Feature card (home screen) */
.feature-card {
    background-color: #161b22;
    border: 1px solid #21262d;
    border-radius: 10px;
    padding: 22px 20px;
    height: 100%;
}
.feature-icon { font-size: 1.4rem; margin-bottom: 10px; }
.feature-title { font-size: 0.9rem; font-weight: 600; color: #f0f6fc; margin-bottom: 6px; }
.feature-desc { font-size: 0.8rem; color: #8b949e; line-height: 1.5; }

/* Metric pill */
.metric-pill {
    display: inline-block;
    background-color: #21262d;
    border-radius: 20px;
    padding: 3px 10px;
    font-size: 0.72rem;
    color: #8b949e;
    margin-right: 5px;
    margin-bottom: 4px;
}

/* Expander */
.streamlit-expanderHeader {
    background-color: #161b22 !important;
    border: 1px solid #21262d !important;
    border-radius: 6px !important;
    color: #c9d1d9 !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
}
.streamlit-expanderContent {
    background-color: #0d1117 !important;
    border: 1px solid #21262d !important;
    border-top: none !important;
    border-radius: 0 0 6px 6px !important;
    color: #8b949e !important;
    font-size: 0.88rem !important;
    line-height: 1.7 !important;
}

/* Metrics widget */
[data-testid="stMetricValue"] { color: #f0f6fc !important; font-size: 1.5rem !important; font-weight: 700 !important; }
[data-testid="stMetricLabel"] { color: #8b949e !important; font-size: 0.78rem !important; }
[data-testid="stMetricDelta"] svg { display: none; }

/* Logo dot */
.logo-dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }

/* BRANDING UPDATES */
.brand-title {
    font-family: 'Inter', sans-serif;
    font-weight: 800 !important;
    color: #f0f6fc;
    letter-spacing: -0.5px;
    background: -webkit-linear-gradient(45deg, #f0f6fc, #58a6ff);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.top-left-logo {
    position: fixed;
    top: 15px;
    left: 20px;
    z-index: 99999;
    display: flex;
    align-items: center;
    gap: 10px;
}
</style>
""", unsafe_allow_html=True)
# ==========================================
# PIPELINE STAGES
# ==========================================
STAGES = [
    ("fetch",      "Fetching financials, news, SEC 10-K & transcript"),
    ("diagnostic", "Running quantitative baseline (LLM)"),
    ("sentiment",  "Running FinBERT sentiment analysis"),
    ("synthesis",  "Synthesizing final enterprise forecast (LLM)"),
    ("done",       "Complete"),
]


# ==========================================
# BACKGROUND PIPELINE RUNNER
# ==========================================
def _pipeline_thread(ticker: str, progress_q: queue.Queue, result_box: list):
    try:
        from backend_final import (
            fetch_data_node,
            financial_diagnostic_node,
            sentiment_node,
            synthesis_node,
            CompanyAnalysisState,
        )
        import asyncio

        state: CompanyAnalysisState = {"ticker": ticker}
        loop = asyncio.new_event_loop()

        progress_q.put("fetch")
        state.update(fetch_data_node(state))

        progress_q.put("diagnostic")
        state.update(loop.run_until_complete(financial_diagnostic_node(state)))

        progress_q.put("sentiment")
        state.update(loop.run_until_complete(sentiment_node(state)))

        progress_q.put("synthesis")
        state.update(loop.run_until_complete(synthesis_node(state)))
        loop.close()

        progress_q.put("done")
        result_box.append(dict(state))

    except Exception as e:
        progress_q.put(("error", traceback.format_exc(), str(e)))


def run_with_status(ticker: str) -> dict:
    progress_q: queue.Queue = queue.Queue()
    result_box: list = []
    thread = threading.Thread(
        target=_pipeline_thread, args=(ticker, progress_q, result_box), daemon=True
    )
    thread.start()

    stage_labels = {s[0]: s[1] for s in STAGES}
    total_stages = len(STAGES) - 1  # exclude "done"
    completed: list = []

    status_text = st.empty()
    progress_bar = st.progress(0)
    stage_log = st.empty()
    log_lines: list[str] = []

    status_text.markdown(
        f"<div style='font-size:0.88rem; font-weight:600; color:#f0f6fc; margin-bottom:6px;'>"
        f"Analyzing {ticker}</div>"
        f"<div style='font-size:0.78rem; color:#8b949e;'>Initializing pipeline…</div>",
        unsafe_allow_html=True,
    )

    while thread.is_alive() or not progress_q.empty():
        try:
            tag = progress_q.get(timeout=0.25)
        except queue.Empty:
            continue

        if isinstance(tag, tuple) and tag[0] == "error":
            _, tb, msg = tag
            progress_bar.empty()
            status_text.empty()
            stage_log.empty()
            st.error(f"Pipeline error: {msg}")
            with st.expander("Error details"):
                st.code(tb)
            thread.join()
            return {}

        if tag in stage_labels and tag not in completed:
            completed.append(tag)
            n = min(len(completed), total_stages)
            progress_bar.progress(n / total_stages)

            if tag == "done":
                status_text.markdown(
                    f"<div style='font-size:0.88rem; font-weight:600; color:#3fb950; margin-bottom:6px;'>"
                    f"Analysis complete — {ticker}</div>",
                    unsafe_allow_html=True,
                )
                log_lines.append(f"[{n}/{total_stages}] {stage_labels[tag]}")
            else:
                status_text.markdown(
                    f"<div style='font-size:0.88rem; font-weight:600; color:#f0f6fc; margin-bottom:6px;'>"
                    f"Analyzing {ticker}</div>"
                    f"<div style='font-size:0.78rem; color:#8b949e;'>{stage_labels[tag]}…</div>",
                    unsafe_allow_html=True,
                )
                log_lines.append(f"[{n}/{total_stages}] {stage_labels[tag]}")

            stage_log.markdown(
                "<div style='font-size:0.75rem; color:#484f58; line-height:1.9; margin-top:8px;'>"
                + "<br>".join(log_lines)
                + "</div>",
                unsafe_allow_html=True,
            )

    thread.join()

    return result_box[0] if result_box else {}


# ==========================================
# PDF EXPORT
# ==========================================
def build_pdf(ticker: str, result: dict, price: float | None) -> bytes:
    from fpdf import FPDF

    class PDF(FPDF):
        def header(self):
            self.set_fill_color(13, 17, 23)
            self.rect(0, 0, 210, 297, "F")
            self.set_font("Helvetica", "B", 18)
            self.set_text_color(240, 246, 252)
            self.cell(0, 12, "ANALYST IN A BOX", align="C", new_x="LMARGIN", new_y="NEXT")
            self.set_font("Helvetica", "", 9)
            self.set_text_color(139, 148, 158)
            self.cell(
                0, 6,
                f"Enterprise Quantitative NLP Report  |  {ticker}  |  {datetime.now().strftime('%B %d, %Y')}",
                align="C", new_x="LMARGIN", new_y="NEXT",
            )
            self.ln(4)
            self.set_draw_color(33, 38, 45)
            self.line(15, self.get_y(), 195, self.get_y())
            self.ln(4)

        def footer(self):
            self.set_y(-14)
            self.set_font("Helvetica", "", 8)
            self.set_text_color(48, 54, 61)
            self.cell(0, 6, f"Page {self.page_no()}  |  Analyst in a Box", align="C")

    def clean(text: str) -> str:
        _MAP = {
            "\u2014": "-", "\u2013": "-", "\u2012": "-", "\u2010": "-", "\u2011": "-",
            "\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"',
            "\u2026": "...", "\u2022": "-", "\u00b7": "-",
            "\u2039": "<", "\u203a": ">", "\u00a0": " ",
            "\u2014": "-",  # em dash (belt-and-suspenders duplicate key is fine)
        }
        for ch, rep in _MAP.items():
            text = text.replace(ch, rep)
        # Nuclear fallback: drop any character outside latin-1 range entirely
        return "".join(c if ord(c) < 256 else "-" for c in text)

    def section_title(pdf, title):
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(56, 139, 253)
        pdf.cell(0, 7, clean(title).upper(), new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(33, 38, 45)
        pdf.line(15, pdf.get_y(), 195, pdf.get_y())
        pdf.ln(3)

    def body_text(pdf, text, size=9):
        # Clean the full string once before splitting so no unicode slips through
        text = clean(text)
        pdf.set_font("Helvetica", "", size)
        pdf.set_text_color(139, 148, 158)
        for line in text.split("\n"):
            for wl in (textwrap.wrap(line, width=110) or [""]):
                pdf.cell(0, 5, wl, new_x="LMARGIN", new_y="NEXT")

    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(15, 20, 15)
    pdf.add_page()

    section_title(pdf, "NLP Sentiment Scores")
    labels = [
        ("Internal (SEC 10-K)",  result.get("internal_sentiment")),
        ("External (News)",      result.get("external_sentiment")),
        ("Executive (Call)",     result.get("transcript_sentiment")),
    ]
    for label, score in labels:
        val = f"{score:+.2f}" if score is not None else "N/A"
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(139, 148, 158)
        pdf.cell(80, 6, clean(label))
        if score is not None and score >= 0.1:
            pdf.set_text_color(63, 185, 80)
        elif score is not None and score <= -0.1:
            pdf.set_text_color(248, 81, 73)
        else:
            pdf.set_text_color(139, 148, 158)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 6, val, new_x="LMARGIN", new_y="NEXT")

    if price:
        pdf.ln(2)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(139, 148, 158)
        pdf.cell(80, 6, "Current Market Price")
        pdf.set_text_color(240, 246, 252)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 6, f"${price:.2f}", new_x="LMARGIN", new_y="NEXT")

    section_title(pdf, "Final Enterprise Forecast")
    report_text = result.get("final_report", "No report available.")
    steps = re.split(r"(\*{0,2}STEP \d+:[^\n]*\*{0,2})", report_text)
    if len(steps) > 1:
        i = 0
        while i < len(steps):
            chunk = steps[i].strip().strip("*")
            if re.match(r"STEP \d+:", chunk):
                pdf.set_font("Helvetica", "B", 9)
                pdf.set_text_color(200, 210, 220)
                pdf.cell(0, 6, clean(chunk), new_x="LMARGIN", new_y="NEXT")
                body_text(pdf, steps[i + 1].strip() if i + 1 < len(steps) else "")
                pdf.ln(2)
                i += 2
            else:
                if chunk:
                    body_text(pdf, chunk)
                i += 1
    else:
        body_text(pdf, report_text)

    headlines = result.get("news_headlines", [])
    if headlines and headlines != ["News fetch failed."]:
        section_title(pdf, "Recent News Catalysts")
        for h in headlines[:5]:
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(139, 148, 158)
            pdf.cell(5, 5, "-")
            pdf.cell(0, 5, textwrap.shorten(clean(h), width=120, placeholder="..."),
                     new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())


# ==========================================
# UI HELPERS
# ==========================================
def _sentiment_color(score) -> str:
    if score is None:
        return "#8b949e"
    if score <= -0.1:
        return "#f85149"
    if score >= 0.1:
        return "#3fb950"
    return "#8b949e"


def _section_label(text: str) -> str:
    return (
        f"<div style='font-size:0.7rem; color:#8b949e; letter-spacing:1.5px; "
        f"text-transform:uppercase; margin-bottom:12px;'>{text}</div>"
    )

FOOTER_HTML = """
<div style='border-top:1px solid #21262d; margin-top:56px; padding-top:32px; padding-bottom:28px;'>
  <div style='display:flex; justify-content:space-between; align-items:flex-start;
              flex-wrap:wrap; gap:24px; max-width:860px; margin:0 auto;'>

    <div>
      <div style='font-size:0.9rem; font-weight:1; color:#f0f6fc; margin-bottom:5px;border:2px solid #f0f6fc; padding:6px 12px; display:inline-block; width:max-content;'>
        ANALYST IN A BOX
      </div>
      <div style='font-size:0.76rem; color:#8b949e; line-height:1.7; max-width:220px;'>
        Institutional-grade equity research<br>generated in seconds using AI &amp; NLP.
      </div>
    </div>

    <div>
      <div style='font-size:0.68rem; color:#8b949e; text-transform:uppercase;
                  letter-spacing:1.2px; margin-bottom:8px;'>Contact</div>
      <div style='font-size:0.78rem; color:#8b949e; line-height:1.9;'>
        <a href="mailto:sy2367@columbia.edu"
           style='color:#388bfd; text-decoration:none;'>sy2367@columbia.edu</a><br>
        <a href="mailto:mu2330@columbia.edu"
           style='color:#388bfd; text-decoration:none;'>mu2330@columbia.edu</a><br>
        <a href="mailto:ssr2208@columbia.edu"
           style='color:#388bfd; text-decoration:none;'>ssr2208@columbia.edu</a><br>
        Columbia University
      </div>
    </div>

    <div>
      <div style='font-size:0.68rem; color:#8b949e; text-transform:uppercase;
                  letter-spacing:1.2px; margin-bottom:8px;'>Built With</div>
      <div style='font-size:0.76rem; color:#8b949e; line-height:1.9;'>
        FinBERT &nbsp;·&nbsp; LLaMA 3.3 70B<br>
        SEC EDGAR &nbsp;·&nbsp; LangGraph<br>
        yfinance &nbsp;·&nbsp; Streamlit
      </div>
    </div>

    <div>
      <div style='font-size:0.68rem; color:#8b949e; text-transform:uppercase;
                  letter-spacing:1.2px; margin-bottom:8px;'>Disclaimer</div>
      <div style='font-size:0.74rem; font-style:italic; color:#8b949e; line-height:1.7; max-width:200px;'>
        For informational purposes only.<br>
        Not investment advice. Past performance<br>
        does not predict future results.
      </div>
    </div>

  </div>
  <div style='text-align:center; font-size:0.68rem; color:#8b949e; margin-top:24px;'>
    © 2026 Analyst in a Box &nbsp;·&nbsp; Columbia University
  </div>
</div>
"""


def price_chart(hist, height: int = 180):
    import plotly.graph_objects as go
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=hist.index,
        y=hist["Close"],
        mode="lines",
        line=dict(color="#388bfd", width=2, shape="spline", smoothing=0.6),
        fill="tozeroy",
        fillgradient=dict(
            type="vertical",
            colorscale=[[0, "rgba(56,139,253,0.18)"], [1, "rgba(56,139,253,0)"]],
        ),
        hovertemplate="<b>%{x|%b %d, %Y}</b><br>$%{y:.2f}<extra></extra>",
    ))
    lo = float(hist["Close"].min()) * 0.997
    hi = float(hist["Close"].max()) * 1.003
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=4, t=4, b=0),
        height=height,
        xaxis=dict(
            showgrid=False, zeroline=False, showline=False,
            tickfont=dict(color="#484f58", size=9, family="Inter"),
            tickformat="%b %d",
        ),
        yaxis=dict(
            showgrid=True, gridcolor="#161b22", zeroline=False, showline=False,
            tickfont=dict(color="#484f58", size=9, family="Inter"),
            tickprefix="$", range=[lo, hi],
        ),
        hoverlabel=dict(
            bgcolor="#161b22", bordercolor="#388bfd",
            font=dict(color="#f0f6fc", size=12, family="Inter"),
        ),
        showlegend=False,
    )
    return fig


def financials_mini_chart(name: str, vals: list, unit: str, height: int = 150):
    import plotly.graph_objects as go

    n = len(vals)
    yr_labels = ["Y-2", "Y-1", "Y0"][-n:]
    colors = ["#21262d"] * (n - 1) + ["#388bfd"]
    trend_color = "#3fb950" if (len(vals) >= 2 and vals[-1] >= vals[-2]) else "#f85149"

    fig = go.Figure(go.Bar(
        x=yr_labels,
        y=vals,
        marker=dict(color=colors, line=dict(width=0)),
        text=[_fmt_metric(v, unit) for v in vals],
        textposition="outside",
        textfont=dict(color="#8b949e", size=9, family="Inter"),
        hovertemplate=f"%{{x}}: %{{text}}<extra>{name}</extra>",
        width=0.5,
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=8, b=20),
        height=height,
        xaxis=dict(showgrid=False, tickfont=dict(color="#484f58", size=9, family="Inter")),
        yaxis=dict(showgrid=True, gridcolor="#161b22", zeroline=False, visible=False),
        showlegend=False,
        hoverlabel=dict(bgcolor="#161b22", font=dict(color="#f0f6fc", size=11)),
    )
    return fig, trend_color


def sentiment_bar_chart(internal, external, transcript, height: int = 170):
    import plotly.graph_objects as go

    labels  = ["Earnings Call", "News", "SEC 10-K"]
    values  = [transcript or 0, external or 0, internal or 0]
    colors  = [_sentiment_color(v) for v in values]

    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation="h",
        marker=dict(color=colors, line=dict(width=0)),
        text=[f"{v:+.2f}" for v in values],
        textposition="outside",
        textfont=dict(color=[_sentiment_color(v) for v in values], size=11, family="Inter"),
        hovertemplate="%{y}: %{x:+.2f}<extra></extra>",
        width=0.5,
    ))
    fig.add_vline(x=0, line_width=1, line_color="#30363d")
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=55, t=4, b=4), height=height,
        xaxis=dict(range=[-1, 1], showgrid=True, gridcolor="#161b22",
                   zeroline=False, tickfont=dict(color="#484f58", size=9, family="Inter")),
        yaxis=dict(showgrid=False, tickfont=dict(color="#8b949e", size=10, family="Inter")),
        showlegend=False,
        hoverlabel=dict(bgcolor="#161b22", font=dict(color="#f0f6fc", size=11)),
    )
    return fig


def earnings_bar_chart(series, label: str, prefix: str = "$", suffix: str = "", height: int = 230):
    import plotly.graph_objects as go

    s = series.sort_index()
    dates = [d.strftime("%b '%y") for d in s.index]
    values = [float(v) for v in s.values]
    colors = ["#3fb950" if v >= 0 else "#f85149" for v in values]
    texts = [f"{prefix}{v:.2f}{suffix}" if abs(v) < 100 else f"{prefix}{v:.1f}B" for v in values]

    fig = go.Figure(go.Bar(
        x=dates, y=values,
        marker=dict(color=colors, line=dict(width=0)),
        text=texts,
        textposition="outside",
        textfont=dict(color="#8b949e", size=9, family="Inter"),
        hovertemplate=f"%{{x}}: {prefix}%{{y:.2f}}{suffix}<extra>{label}</extra>",
        width=0.65,
    ))
    fig.add_hline(y=0, line_width=1, line_color="#30363d")
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=28, b=0),
        height=height,
        xaxis=dict(showgrid=False, tickfont=dict(color="#8b949e", size=9, family="Inter")),
        yaxis=dict(showgrid=True, gridcolor="#161b22", zeroline=False, visible=False),
        showlegend=False,
        hoverlabel=dict(bgcolor="#161b22", font=dict(color="#f0f6fc", size=11)),
    )
    return fig


def _verdict(result: dict) -> tuple[str, str, str]:
    scores = [result.get("internal_sentiment") or 0,
              result.get("external_sentiment") or 0,
              result.get("transcript_sentiment") or 0]
    avg = sum(scores) / len(scores)
    if avg >= 0.12:
        return "BULLISH", "#3fb950", "rgba(63,185,80,0.08)"
    if avg <= -0.12:
        return "BEARISH", "#f85149", "rgba(248,81,73,0.08)"
    return "NEUTRAL", "#8b949e", "rgba(139,148,158,0.08)"


def sentiment_gauge(score, title: str):
    import plotly.graph_objects as go
    color = _sentiment_color(score)
    val = score if score is not None else 0.0
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=val,
        number={
            "font": {"color": color, "size": 36, "family": "Inter"},
            "valueformat": "+.2f",
        },
        gauge={
            "axis": {
                "range": [-1, 1],
                "tickvals": [-1, -0.5, 0, 0.5, 1],
                "ticktext": ["-1.0", "-0.5", "0", "+0.5", "+1.0"],
                "tickfont": {"color": "#484f58", "size": 9},
                "tickcolor": "#21262d",
                "linecolor": "#21262d",
            },
            "bar": {"color": color, "thickness": 0.22},
            "bgcolor": "rgba(0,0,0,0)",
            "borderwidth": 0,
            "steps": [
                {"range": [-1, -0.1], "color": "rgba(248,81,73,0.07)"},
                {"range": [-0.1, 0.1], "color": "rgba(33,38,45,0.4)"},
                {"range": [0.1, 1],   "color": "rgba(63,185,80,0.07)"},
            ],
            "threshold": {
                "line": {"color": color, "width": 3},
                "thickness": 0.7,
                "value": val,
            },
        },
        title={"text": title, "font": {"color": "#8b949e", "size": 11, "family": "Inter"}},
        domain={"x": [0, 1], "y": [0, 1]},
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=55, b=5),
        height=210,
        font={"color": "#c9d1d9", "family": "Inter"},
    )
    return fig


def kpi_card(label: str, value: str, trend: str = "", trend_dir: str = "flat") -> str:
    trend_html = f"<div class='kpi-trend {trend_dir}'>{trend}</div>" if trend else ""
    return f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        {trend_html}
    </div>
    """


def render_sentiment_card(title: str, score):
    color = _sentiment_color(score)
    display = f"{score:+.2f}" if score is not None else "N/A"
    label = "POSITIVE" if (score or 0) >= 0.1 else "NEGATIVE" if (score or 0) <= -0.1 else "NEUTRAL"
    st.markdown(f"""
    <div class="sentiment-card" style="border-left-color:{color};">
        <div style="font-size:0.72rem; color:#8b949e; margin-bottom:6px;
                    text-transform:uppercase; letter-spacing:0.5px;">{title}</div>
        <div style="display:flex; align-items:center; justify-content:space-between;">
            <div style="font-size:1.7rem; font-weight:700; color:{color};
                        font-variant-numeric:tabular-nums;">{display}</div>
            <div style="font-size:0.68rem; font-weight:600; color:{color};
                        background:rgba(255,255,255,0.05); border-radius:4px;
                        padding:3px 8px; letter-spacing:0.5px;">{label}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_report(text: str):
    # Handle both **STEP N:** and plain STEP N: formats from the LLM
    parts = re.split(r"(\*{0,2}STEP \d+:[^\n]*\*{0,2})", text)
    if len(parts) <= 1:
        st.markdown(
            f"<div style='color:#8b949e; font-size:0.9rem; line-height:1.8'>{text}</div>",
            unsafe_allow_html=True,
        )
        return
    i = 0
    while i < len(parts):
        chunk = parts[i].strip().strip("*")
        if re.match(r"STEP \d+:", chunk):
            body = parts[i + 1].strip() if i + 1 < len(parts) else ""
            with st.expander(chunk, expanded=(i == 0)):
                st.markdown(
                    f"<div style='color:#8b949e; font-size:0.88rem; line-height:1.85'>{body}</div>",
                    unsafe_allow_html=True,
                )
            i += 2
        else:
            if chunk:
                st.markdown(chunk)
            i += 1


def parse_metrics(financial_data: str) -> dict:
    """Extract pre-computed quant metrics + key income statement rows."""
    out = {}
    pre = [
        ("Operating Margin", r"Operating Margin: \[([^\]]+)\]", "%"),
        ("ROE",              r"Return on Equity \(ROE\): \[([^\]]+)\]", "%"),
        ("Current Ratio",    r"Current Ratio: \[([^\]]+)\]", "x"),
        ("D/E Ratio",        r"Debt-to-Equity Ratio: \[([^\]]+)\]", "x"),
    ]
    for name, pat, unit in pre:
        m = re.search(pat, financial_data)
        if m:
            vals = []
            for v in m.group(1).split(","):
                try:
                    vals.append(float(v.strip().rstrip("%")))
                except ValueError:
                    pass
            if vals:
                out[name] = {"values": vals, "unit": unit}

    # EPS — row appears as: "Diluted EPS   7.46   6.08   6.13   6.11"
    m = re.search(r"Diluted EPS\s+([\d.e+\-]+)\s+([\d.e+\-]+)\s+([\d.e+\-]+)", financial_data)
    if m:
        out["EPS (Diluted)"] = {
            "values": [float(m.group(3)), float(m.group(2)), float(m.group(1))],
            "unit": "$",
        }

    # Revenue
    m = re.search(r"Total Revenue\s+([\d.e+\-]+)\s+([\d.e+\-]+)\s+([\d.e+\-]+)", financial_data)
    if m:
        out["Revenue"] = {
            "values": [float(m.group(3)) / 1e9, float(m.group(2)) / 1e9, float(m.group(1)) / 1e9],
            "unit": "B",
        }

    # Free Cash Flow
    m = re.search(r"Free Cash Flow\s+([\d.e+\-]+)\s+([\d.e+\-]+)\s+([\d.e+\-]+)", financial_data)
    if m:
        out["Free Cash Flow"] = {
            "values": [float(m.group(3)) / 1e9, float(m.group(2)) / 1e9, float(m.group(1)) / 1e9],
            "unit": "B",
        }

    return out


def _fmt_metric(val: float, unit: str) -> str:
    if unit == "%":
        return f"{val:.1f}%"
    if unit == "$":
        return f"${val:.2f}"
    if unit == "B":
        return f"${val:.1f}B"
    return f"{val:.2f}{unit}"


def _trend_pct(vals: list) -> tuple[str, str]:
    if len(vals) < 2:
        return "", "flat"
    chg = ((vals[-1] - vals[-2]) / abs(vals[-2])) * 100 if vals[-2] else 0
    arrow = "↑" if chg > 0.5 else "↓" if chg < -0.5 else "→"
    direction = "up" if chg > 0.5 else "down" if chg < -0.5 else "flat"
    return f"{arrow} {abs(chg):.1f}% YoY", direction


@st.cache_data(show_spinner=False, ttl=900)
def cached_market_data(ticker: str):
    return yf.Ticker(ticker).history(period="3mo")


@st.cache_data(show_spinner=False, ttl=900)
def cached_earnings_data(ticker: str) -> dict:
    try:
        t = yf.Ticker(ticker)
        q = t.quarterly_income_stmt
        if q is None or q.empty:
            return {}
        out = {}
        if "Diluted EPS" in q.index:
            out["eps"] = q.loc["Diluted EPS"].dropna().sort_index()
        if "Total Revenue" in q.index:
            out["revenue"] = q.loc["Total Revenue"].dropna().sort_index() / 1e9
        if "Net Income" in q.index:
            out["net_income"] = q.loc["Net Income"].dropna().sort_index() / 1e9
        return out
    except Exception:
        return {}


@st.cache_data(show_spinner=False, ttl=60)
def cached_index_data() -> list[dict]:
    symbols = [("^GSPC", "S&P 500"), ("^IXIC", "NASDAQ"), ("^DJI", "DOW"), ("^VIX", "VIX")]
    out = []
    for sym, label in symbols:
        try:
            fi = yf.Ticker(sym).fast_info
            price = fi.last_price
            prev  = fi.previous_close
            if price and prev:
                chg = ((price - prev) / prev) * 100
                out.append({"label": label, "price": price, "chg": chg})
        except Exception:
            pass
    return out


def render_trading_bar(indices: list[dict]):
    import streamlit.components.v1 as components

    idx_parts = []
    for item in indices:
        color = "#3fb950" if item["chg"] >= 0 else "#f85149"
        sign  = "+" if item["chg"] >= 0 else ""
        # VIX shows no sign prefix
        chg_str = f"{sign}{item['chg']:.2f}%" if item["label"] != "VIX" else f"{item['price']:.2f}"
        price_str = f"{item['price']:,.2f}"
        idx_parts.append(
            f'<div class="seg">'
            f'<span class="lbl">{item["label"]}</span>'
            f'<span class="val" style="color:{color};">{price_str}</span>'
            f'<span class="chg" style="color:{color};">{chg_str}</span>'
            f'</div>'
        )
    idx_html = '<div class="pipe"></div>'.join(idx_parts)

    html = f"""<!DOCTYPE html><html><head><style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:#0d1117;overflow:hidden;font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif;}}
.bar{{display:flex;align-items:center;height:44px;padding:0 24px;border-bottom:1px solid #21262d;}}
.brand{{color:#f0f6fc;font-weight:700;letter-spacing:2px;font-size:0.72rem;white-space:nowrap;margin-right:20px;}}
.pipe{{width:1px;height:16px;background:#21262d;margin:0 16px;flex-shrink:0;}}
.seg{{display:flex;align-items:center;gap:6px;white-space:nowrap;}}
.lbl{{color:#484f58;font-size:0.68rem;text-transform:uppercase;letter-spacing:0.8px;}}
.val{{font-weight:600;font-size:0.78rem;font-variant-numeric:tabular-nums;}}
.chg{{font-size:0.68rem;}}
.spacer{{flex:1;}}
.mkt{{display:flex;align-items:center;gap:7px;font-size:0.68rem;color:#8b949e;text-transform:uppercase;letter-spacing:1px;white-space:nowrap;}}
.dot{{width:6px;height:6px;border-radius:50%;flex-shrink:0;}}
.dot-open{{background:#3fb950;animation:pulse 2s ease-in-out infinite;}}
.dot-closed{{background:#484f58;}}
.dot-pre{{background:#e3b341;animation:pulse 2s ease-in-out infinite;}}
.clock-wrap{{display:flex;flex-direction:column;align-items:flex-end;margin-left:18px;}}
.clock{{color:#c9d1d9;font-size:0.82rem;font-weight:600;font-variant-numeric:tabular-nums;letter-spacing:0.5px;white-space:nowrap;}}
.date{{color:#484f58;font-size:0.65rem;letter-spacing:0.5px;margin-top:1px;white-space:nowrap;}}
@keyframes pulse{{0%,100%{{opacity:1;}}50%{{opacity:0.25;}}}}
</style></head><body>
<div class="bar">
  <span class="brand">ANALYST IN A BOX</span>
  <div class="pipe"></div>
  {idx_html}
  <div class="spacer"></div>
  <div class="mkt"><div class="dot" id="dot"></div><span id="mkt-lbl"></span></div>
  <div class="pipe"></div>
  <div class="clock-wrap">
    <div class="clock" id="clk"></div>
    <div class="date" id="dte"></div>
  </div>
</div>
<script>
function mktStatus(){{
  var et=new Date(new Date().toLocaleString('en-US',{{timeZone:'America/New_York'}}));
  var day=et.getDay(),mins=et.getHours()*60+et.getMinutes();
  if(day===0||day===6)return['CLOSED','dot-closed'];
  if(mins>=570&&mins<960)return['NYSE OPEN','dot-open'];
  if(mins>=240&&mins<570)return['PRE-MARKET','dot-pre'];
  if(mins>=960&&mins<1200)return['AFTER HOURS','dot-closed'];
  return['CLOSED','dot-closed'];
}}
function tick(){{
  var now=new Date();
  var t=now.toLocaleTimeString('en-US',{{timeZone:'America/New_York',hour12:false,hour:'2-digit',minute:'2-digit',second:'2-digit'}});
  var d=now.toLocaleDateString('en-US',{{timeZone:'America/New_York',weekday:'short',month:'short',day:'numeric',year:'numeric'}});
  document.getElementById('clk').textContent=t+' ET';
  document.getElementById('dte').textContent=d;
  var s=mktStatus();
  document.getElementById('mkt-lbl').textContent=s[0];
  document.getElementById('dot').className='dot '+s[1];
}}
tick();setInterval(tick,1000);
</script></body></html>"""

    components.html(html, height=44, scrolling=False)


# ==========================================
# SESSION STATE
# ==========================================
for _k, _v in [("has_run", False), ("current_ticker", "")]:
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ==========================================
# TRADING BAR (always visible)
# ==========================================
render_trading_bar(cached_index_data())
# ==========================================
# HOME SCREEN
# ==========================================
if not st.session_state.has_run:
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, hero, _ = st.columns([1, 1.6, 1])
    with hero:
        st.markdown(
            "<h1 style='text-align:center; font-weight:0.01;letter-spacing:3px;font-size:1.5rem; color:#f0f6fc; border:2px solid #f0f6fc; padding:12px 32px; width:max-content; margin:0 auto 12px auto;'>"
            "ANALYST IN A BOX</h1>"
            "<p style='text-align:center; font-size:0.75rem; color:#484f58; text-transform:uppercase;"
            " letter-spacing:3px; margin-bottom:28px;'>SEC · Earnings Calls · News · LLM Analysis · NLP</p>",
            unsafe_allow_html=True,
        )
        s_col, b_col = st.columns([5, 1])
        with s_col:
            ticker_input = st.text_input(
                "Ticker", placeholder="Enter any ticker like NVDA",
                label_visibility="collapsed", key="home_search",
            )
        with b_col:
            go = st.button("Analyze", key="home_btn")

        if go and ticker_input:
            st.session_state.current_ticker = ticker_input.upper().strip()
            st.session_state.has_run = True
            st.rerun()

    st.markdown("<br><br>", unsafe_allow_html=True)
    _, feat, _ = st.columns([0.5, 3, 0.5])
    with feat:
        st.markdown(_section_label("What's inside every report"), unsafe_allow_html=True)
        f1, f2, f3, f4 = st.columns(4, gap="medium")
        features = [
            ("SEC 10-K Analysis",
             "Management Discussion & Analysis parsed directly from the latest EDGAR annual filing."),
            ("News Sentiment",
             "Real-time financial news scored by FinBERT, a domain-specific NLP model."),
            ("Earnings Call NLP",
             "Executive tone and forward guidance extracted from the most recent earnings transcript."),
            ("LLM Synthesis",
             "LLaMA 3.3 70B synthesizes quant data, sentiment, and fundamentals into a forecast."),
        ]
        for col, (title, desc) in zip([f1, f2, f3, f4], features):
            with col:
                st.markdown(f"""
                <div class="feature-card">
                    <div class="feature-title">{title}</div>
                    <div class="feature-desc">{desc}</div>
                </div>
                """, unsafe_allow_html=True)

    st.html(FOOTER_HTML)


# ==========================================
# DASHBOARD SCREEN
# ==========================================
else:
    ticker = st.session_state.current_ticker

    # ── Nav ──
    _, nav, _ = st.columns([1, 2, 1])
    with nav:
        sc, bc = st.columns([5, 1])
        with sc:
            new_ticker = st.text_input(
                "Ticker", value=ticker, label_visibility="collapsed", key="top_search",
            )
        with bc:
            if st.button("Analyze", key="top_btn"):
                st.session_state.current_ticker = new_ticker.upper().strip()
                st.rerun()

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Validate ticker — equities and ETFs only ──
    try:
        fast = yf.Ticker(ticker).fast_info
        if not getattr(fast, "last_price", None):
            st.error(f"**{ticker}** — no market data found. Please enter a valid stock ticker.")
            st.stop()
        quote_type = getattr(fast, "quote_type", "").upper()
        ALLOWED = {"EQUITY"}
        TYPE_LABELS = {
            "ETF":            "ETF",
            "CRYPTOCURRENCY": "cryptocurrency",
            "MUTUALFUND":     "mutual fund",
            "INDEX":          "market index",
            "FUTURE":         "futures contract",
            "CURRENCY":       "currency pair",
            "OPTION":         "options contract",
        }
        if quote_type and quote_type not in ALLOWED:
            label = TYPE_LABELS.get(quote_type, quote_type.lower())
            st.error(
                f"**{ticker}** is a {label}, not an equity. "
                f"This tool supports stocks and ETFs only. "
                f"Please enter a valid equity ticker (e.g. AAPL, MSFT, NVDA)."
            )
            st.stop()
    except Exception:
        st.warning("Could not validate ticker — proceeding anyway.")

    # ── Run or load ──
    cache_key = f"result_{ticker}"
    if DEMO_MODE:
        from fixtures import DEMO_RESULT
        result = DEMO_RESULT
        st.info("**Demo mode** — showing fixture data. Unset `DEMO_MODE` in `.env` to run the real pipeline.")
    elif cache_key not in st.session_state:
        result = run_with_status(ticker)
        st.session_state[cache_key] = result
    else:
        result = st.session_state[cache_key]

    if not result:
        st.stop()

    # ── Market data ──
    current_price = prev_close = price_delta = None
    hist = None
    try:
        hist = cached_market_data(ticker)
        if not hist.empty:
            current_price = float(hist["Close"].iloc[-1])
            prev_close    = float(hist["Close"].iloc[-2]) if len(hist) > 1 else current_price
            price_delta   = current_price - prev_close
    except Exception:
        pass

    # ── Company info ──
    company_name = ""
    sector = ""
    try:
        info = yf.Ticker(ticker).info
        company_name = info.get("longName", "")
        sector = info.get("sector", "")
    except Exception:
        pass

    # ── Header ──
    h_left, h_right = st.columns([3, 1])
    with h_left:
        st.markdown(f"""
        <div style='margin-bottom:6px;'>
            <span style='font-size:2rem; font-weight:700; color:#f0f6fc;'>{ticker}</span>
            {'<span style="font-size:1rem; color:#8b949e; margin-left:12px;">' + company_name + '</span>' if company_name else ''}
        </div>
        <div>
            {'<span class="metric-pill">' + sector + '</span>' if sector else ''}
            <span class='metric-pill'>SEC 10-K</span>
            <span class='metric-pill'>Earnings Call</span>
            <span class='metric-pill'>FinBERT NLP</span>
            <span class='metric-pill'>LLaMA 3.3 70B</span>
            <span class='metric-pill'>{datetime.now().strftime("%b %d, %Y")}</span>
        </div>
        """, unsafe_allow_html=True)
    with h_right:
        if current_price is not None:
            pct = ((price_delta / prev_close) * 100) if prev_close else 0
            st.metric("Price", f"${current_price:.2f}", delta=f"{pct:+.2f}%")

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Parse financial metrics ──
    metrics = parse_metrics(result.get("financial_data", ""))
    headlines = result.get("news_headlines", [])
    valid_headlines = headlines if (headlines and headlines != ["News fetch failed."]) else []

    # ═══════════════════════════════════════
    # SECTION 1 — OVERVIEW
    # ═══════════════════════════════════════
    label, color, bg = _verdict(result)

    st.markdown(f"""
    <div style='background:{bg}; border:1px solid {color}40; border-radius:10px;
                padding:20px 28px; margin-bottom:24px;
                display:flex; align-items:center; gap:20px;'>
        <div style='font-size:1.6rem; font-weight:800; color:{color};
                    letter-spacing:2px;'>{label}</div>
        <div style='width:1px; height:40px; background:{color}30;'></div>
        <div>
            <div style='font-size:0.72rem; color:#8b949e; text-transform:uppercase;
                        letter-spacing:1px; margin-bottom:4px;'>Composite Sentiment Signal</div>
            <div style='font-size:0.88rem; color:#c9d1d9;'>
                Based on SEC 10-K, financial news, and earnings call NLP analysis
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if metrics:
        kpi_keys = ["Revenue", "EPS (Diluted)", "Free Cash Flow"]
        kpi_cols = st.columns(len(kpi_keys), gap="small")
        for col, key in zip(kpi_cols, kpi_keys):
            if key in metrics:
                m = metrics[key]
                vals, unit = m["values"], m["unit"]
                val_str = _fmt_metric(vals[-1], unit)
                trend_str, trend_dir = _trend_pct(vals)
                with col:
                    st.markdown(kpi_card(key, val_str, trend_str, trend_dir), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    ov_left, ov_right = st.columns([1, 1.4], gap="large")

    with ov_left:
        st.markdown(_section_label("Sentiment Alignment"), unsafe_allow_html=True)
        try:
            st.plotly_chart(
                sentiment_bar_chart(
                    result.get("internal_sentiment"),
                    result.get("external_sentiment"),
                    result.get("transcript_sentiment"),
                ),
                use_container_width=True,
                config={"displayModeBar": False},
            )
        except Exception:
            pass
        render_sentiment_card("Internal — SEC 10-K",  result.get("internal_sentiment"))
        render_sentiment_card("External — News",       result.get("external_sentiment"))
        render_sentiment_card("Executive — Earnings",  result.get("transcript_sentiment"))

    with ov_right:
        st.markdown(_section_label("Price — 3 Months"), unsafe_allow_html=True)
        if hist is not None and not hist.empty:
            st.plotly_chart(price_chart(hist, height=160), use_container_width=True,
                            config={"displayModeBar": False})

        if metrics:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(_section_label("Key Financials — 3-Year Trend"), unsafe_allow_html=True)
            fin_keys = ["Revenue", "EPS (Diluted)", "Operating Margin", "Free Cash Flow"]
            available = [(k, metrics[k]) for k in fin_keys if k in metrics]
            if available:
                row1 = available[:2]
                row2 = available[2:]
                for row in (row1, row2):
                    if not row:
                        continue
                    fcols = st.columns(len(row), gap="medium")
                    for fcol, (name, m) in zip(fcols, row):
                        with fcol:
                            st.markdown(
                                f"<div style='font-size:0.72rem; color:#8b949e; "
                                f"text-transform:uppercase; letter-spacing:1px; "
                                f"margin-bottom:4px;'>{name}</div>",
                                unsafe_allow_html=True,
                            )
                            try:
                                fig, _ = financials_mini_chart(name, m["values"], m["unit"], height=130)
                                st.plotly_chart(fig, use_container_width=True,
                                                config={"displayModeBar": False})
                            except Exception:
                                pass

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown(_section_label("Full LLM Report"), unsafe_allow_html=True)
    render_report(result.get("final_report", "No report available."))

    # ═══════════════════════════════════════
    # SECTION 2 — FINANCIALS
    # ═══════════════════════════════════════
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown(_section_label("Financials"), unsafe_allow_html=True)

    if metrics:
        m_cols = st.columns(len(metrics), gap="small")
        for col, (name, m) in zip(m_cols, metrics.items()):
            vals, unit = m["values"], m["unit"]
            val_str = _fmt_metric(vals[-1], unit)
            trend_str, trend_dir = _trend_pct(vals)
            with col:
                st.markdown(kpi_card(name, val_str, trend_str, trend_dir), unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

    earnings_data = cached_earnings_data(ticker)
    if earnings_data:
        st.markdown(_section_label("Quarterly Earnings History"), unsafe_allow_html=True)
        e_cols = []
        e_items = []
        if "eps" in earnings_data:
            e_items.append(("Diluted EPS", earnings_data["eps"], "$", ""))
        if "revenue" in earnings_data:
            e_items.append(("Revenue", earnings_data["revenue"], "$", "B"))
        if "net_income" in earnings_data:
            e_items.append(("Net Income", earnings_data["net_income"], "$", "B"))

        if e_items:
            e_cols = st.columns(len(e_items), gap="large")
            for col, (name, series, prefix, suffix) in zip(e_cols, e_items):
                with col:
                    st.markdown(
                        f"<div style='font-size:0.72rem; color:#8b949e; text-transform:uppercase; "
                        f"letter-spacing:1px; margin-bottom:4px;'>{name}</div>",
                        unsafe_allow_html=True,
                    )
                    try:
                        st.plotly_chart(
                            earnings_bar_chart(series, name, prefix, suffix),
                            use_container_width=True,
                            config={"displayModeBar": False},
                        )
                    except Exception:
                        pass
        st.markdown("<br>", unsafe_allow_html=True)

    diag = result.get("financial_diagnostic", "")
    if diag:
        st.markdown(_section_label("4-Step Quantitative Diagnostic (LLM)"), unsafe_allow_html=True)
        render_report(diag)

    raw = result.get("financial_data", "")
    if raw:
        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("Raw Financial Data — Income Statement · Balance Sheet · Cash Flow", expanded=False):
            st.code(raw, language=None)

    # ═══════════════════════════════════════
    # SECTION 3 — SENTIMENT & NEWS
    # ═══════════════════════════════════════
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown(_section_label("Sentiment & News"), unsafe_allow_html=True)

    g1, g2, g3 = st.columns(3, gap="medium")
    gauges = [
        (result.get("internal_sentiment"),  "Internal Sentiment<br>SEC 10-K MD&A"),
        (result.get("external_sentiment"),   "External Sentiment<br>Financial News"),
        (result.get("transcript_sentiment"), "Executive Sentiment<br>Earnings Call"),
    ]
    for col, (score, gtitle) in zip([g1, g2, g3], gauges):
        with col:
            try:
                st.plotly_chart(
                    sentiment_gauge(score, gtitle),
                    use_container_width=True,
                    config={"displayModeBar": False},
                )
            except Exception:
                render_sentiment_card(gtitle.replace("<br>", " — "), score)

    st.markdown("<hr>", unsafe_allow_html=True)
    n_left, n_right = st.columns([1, 1], gap="large")

    with n_left:
        st.markdown(_section_label("Score Interpretation"), unsafe_allow_html=True)
        st.markdown("""
        <div style='font-size:0.85rem; color:#8b949e; line-height:2.2;'>
            <span style='color:#3fb950; font-weight:600;'>+0.10 to +1.00</span> &nbsp; Positive signal<br>
            <span style='color:#8b949e; font-weight:600;'>-0.10 to +0.10</span> &nbsp; Neutral / mixed<br>
            <span style='color:#f85149; font-weight:600;'>-1.00 to -0.10</span> &nbsp; Negative signal<br><br>
            Scored by <strong style='color:#c9d1d9;'>FinBERT</strong>, a BERT model
            fine-tuned on financial text from Reuters, earnings releases, and analyst reports.
        </div>
        """, unsafe_allow_html=True)

    with n_right:
        st.markdown(_section_label("News Headlines"), unsafe_allow_html=True)
        if valid_headlines:
            for h in valid_headlines:
                htitle, _, body = h.partition(" - ")
                htitle = htitle.strip()
                snippet = body.strip()[:160] + "…" if len(body.strip()) > 160 else body.strip()
                st.markdown(
                    f"<div style='padding:10px 0; border-bottom:1px solid #21262d;'>"
                    f"<div style='font-size:0.85rem; font-weight:500; color:#c9d1d9; line-height:1.4; margin-bottom:3px;'>{htitle}</div>"
                    f"<div style='font-size:0.77rem; color:#8b949e; line-height:1.5;'>{snippet}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                "<span style='color:#8b949e; font-size:0.85rem;'>No headlines available.</span>",
                unsafe_allow_html=True,
            )

    transcript = result.get("transcript_text", "")
    if transcript and transcript not in ("Transcript unavailable.", "Transcript fetch failed.", ""):
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(_section_label("Earnings Call Transcript (excerpt)"), unsafe_allow_html=True)
        with st.expander("Show full excerpt", expanded=False):
            st.markdown(
                f"<div style='font-size:0.82rem; color:#8b949e; line-height:1.8;'>{transcript[:4000]}…</div>",
                unsafe_allow_html=True,
            )

    # ═══════════════════════════════════════
    # SECTION 4 — EXPORT
    # ═══════════════════════════════════════
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown(_section_label("Export"), unsafe_allow_html=True)

    _, ex_col, _ = st.columns([1, 1, 1])
    with ex_col:
        st.markdown("<br>", unsafe_allow_html=True)

        try:
            pdf_bytes = build_pdf(ticker, result, current_price)
            st.download_button(
                label="Download PDF Report",
                data=pdf_bytes,
                file_name=f"analyst_in_a_box_{ticker}_{datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf",
            )
        except ImportError:
            st.warning("Install `fpdf2` to enable PDF export:  `pip install fpdf2`")
        except Exception as e:
            st.error(f"PDF generation failed: {e}")

        safe_result = {
            k: v for k, v in result.items()
            if isinstance(v, (str, int, float, list, dict, type(None)))
        }
        st.download_button(
            label="Download JSON (raw data)",
            data=json.dumps(safe_result, indent=2),
            file_name=f"analyst_in_a_box_{ticker}_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json",
        )

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f"""
        <div style='background:#161b22; border:1px solid #21262d; border-radius:8px;
                    padding:16px 18px; font-size:0.82rem; color:#8b949e; line-height:1.8;'>
            <strong style='color:#c9d1d9;'>Report Details</strong><br>
            Ticker: <span style='color:#f0f6fc;'>{ticker}</span><br>
            Generated: <span style='color:#f0f6fc;'>{datetime.now().strftime("%B %d, %Y at %H:%M")}</span><br>
            Sources: SEC EDGAR 10-K, Financial News, Earnings Transcript<br>
            Models: FinBERT (sentiment) · LLaMA 3.3 70B (synthesis)
        </div>
        """, unsafe_allow_html=True)

    st.html(FOOTER_HTML)
