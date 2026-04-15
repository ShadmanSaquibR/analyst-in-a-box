import streamlit as st
import yfinance as yf

# ==========================================
# 1. PAGE CONFIG & 80s AFTERDARK CSS
# ==========================================
st.set_page_config(page_title="Analyst in a Box", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    .stApp {
        background-color: #1b1d36;
        color: #cbdaeb;
        font-family: 'Courier New', Courier, monospace;
    }
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    h1, h2, h3 { color: #99d6ea !important; }
    .stTextInput input {
        background-color: #222442 !important;
        color: #99d6ea !important;
        border: 2px solid #3b3f70 !important;
        border-radius: 8px;
        font-size: 1.1rem;
    }
    .stTextInput input:focus {
        border-color: #c678dd !important;
        box-shadow: none !important;
    }
    .stButton button {
        background-color: #3b3f70;
        color: #cbdaeb;
        border: 2px solid #3b3f70;
        border-radius: 8px;
        width: 100%;
        transition: all 0.3s ease;
    }
    .stButton button:hover {
        background-color: #c678dd;
        border-color: #c678dd;
        color: #1b1d36;
        font-weight: bold;
    }
    .sentiment-card {
        background-color: #222442;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 15px;
        border-left: 5px solid;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def get_sentiment_color(score):
    if score is None:
        return "#6272a4"
    if score <= -0.1:
        return "#ff5c57"
    elif score >= 0.1:
        return "#50fa7b"
    else:
        return "#6272a4"

def render_sentiment_card(title, score):
    color = get_sentiment_color(score)
    display_score = f"{score:.2f}" if score is not None else "N/A"
    html = f"""
    <div class="sentiment-card" style="border-left-color: {color};">
        <h4 style="margin-top: 0; font-size: 1rem; color: #cbdaeb;">{title}</h4>
        <h2 style="margin: 0; color: {color};">{display_score}</h2>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# ==========================================
# 3. CACHED PIPELINE CALL
# This is the key fix: @st.cache_data ensures the pipeline only runs
# once per ticker per session, instead of on every Streamlit rerun
# (which fires on every keystroke, focus change, button click, etc.).
# ==========================================
@st.cache_data(show_spinner=False, ttl=3600)
def cached_run_pipeline(ticker: str) -> dict:
    from state_version_2_2_1 import run_pipeline
    return run_pipeline(ticker)


@st.cache_data(show_spinner=False, ttl=900)
def cached_market_data(ticker: str):
    return yf.Ticker(ticker).history(period="1mo")


# ==========================================
# 4. SESSION STATE
# ==========================================
if 'has_run' not in st.session_state:
    st.session_state.has_run = False
if 'current_ticker' not in st.session_state:
    st.session_state.current_ticker = ""

# ==========================================
# 5. UI ROUTING
# ==========================================
if not st.session_state.has_run:
    # --- HOME SCREEN ---
    st.markdown("<br><br><br><br><br><br><br>", unsafe_allow_html=True)

    col_spacer1, col_center, col_spacer2 = st.columns([1, 2, 1])

    with col_center:
        st.markdown("<h1 style='text-align: center; font-size: 3rem;'>Analyst in a Box</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #6272a4;'>ENTERPRISE QUANTITATIVE NLP ENGINE</p>", unsafe_allow_html=True)

        search_col, btn_col = st.columns([4, 1])
        with search_col:
            ticker_input = st.text_input(
                "Ticker search",
                placeholder="Enter any ticker, eg. AAPL",
                label_visibility="collapsed",
                key="home_search",
            )
        with btn_col:
            st.markdown("<br>", unsafe_allow_html=True)
            execute_btn = st.button("EXECUTE", key="home_btn")

        if execute_btn and ticker_input:
            st.session_state.current_ticker = ticker_input.upper()
            st.session_state.has_run = True
            st.rerun()

else:
    # --- DASHBOARD SCREEN ---
    ticker = st.session_state.current_ticker

    top_spacer1, top_center, top_spacer2 = st.columns([1, 2, 1])
    with top_center:
        st.markdown("<h3 style='text-align: center;'>Analyst in a Box</h3>", unsafe_allow_html=True)
        search_col, btn_col = st.columns([4, 1])
        with search_col:
            new_ticker = st.text_input(
                "Ticker search",
                value=ticker,
                placeholder="Enter any ticker, eg. AAPL",
                label_visibility="collapsed",
                key="top_search",
            )
        with btn_col:
            if st.button("EXECUTE", key="top_btn"):
                st.session_state.current_ticker = new_ticker.upper()
                st.rerun()

    st.markdown("---")

    # --- RUN THE BACKEND ---
    # This call is cached by @st.cache_data — second time you visit
    # the same ticker, it returns instantly. Re-runs from typing in
    # the search box no longer trigger a fresh pipeline run.
    result = {}
    try:
        with st.spinner(f"Running pipeline for {ticker}..."):
            result = cached_run_pipeline(ticker)
    except Exception as e:
        import traceback
        st.error(f"Pipeline failed for {ticker}: {e}")
        with st.expander("Traceback"):
            st.code(traceback.format_exc())

    # --- RENDER THE 3 COLUMNS ---
    col_left, col_mid, col_right = st.columns([1, 2, 1], gap="large")

    with col_left:
        st.subheader("NLP Sentiment")
        render_sentiment_card("Internal (SEC 10-K)", result.get("internal_sentiment", 0))
        render_sentiment_card("External (News)", result.get("external_sentiment", 0))
        render_sentiment_card("Executive (Call)", result.get("transcript_sentiment", 0))

    with col_mid:
        st.subheader("Final Enterprise Forecast")
        st.markdown(f"> {result.get('final_report', 'Pipeline did not return a final report.')}")

    with col_right:
        st.subheader("Market Reality")
        try:
            hist = cached_market_data(ticker)
            if not hist.empty:
                current_price = hist['Close'].iloc[-1]
                st.metric("Current Price", f"${current_price:.2f}")
                st.line_chart(hist['Close'], height=150)
        except Exception:
            st.error("Failed to fetch market data.")

        st.markdown("**Recent Catalysts (News)**")
        headlines = result.get("news_headlines", [])
        if headlines:
            for headline in headlines[:3]:
                st.markdown(
                    f"- <span style='color: #6272a4; font-size: 0.9rem;'>{headline}</span>",
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                "<span style='color: #6272a4; font-size: 0.9rem;'>No recent headlines available.</span>",
                unsafe_allow_html=True,
            )
