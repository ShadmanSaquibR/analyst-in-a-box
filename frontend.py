import streamlit as st
import yfinance as yf
import time
import os
from dotenv import load_dotenv
# ==========================================
# 1. PAGE CONFIG & 80s AFTERDARK CSS
# ==========================================
st.set_page_config(page_title="Analyst in a Box", layout="wide", initial_sidebar_state="collapsed")

# Inject custom CSS for the Monkeytype 80s Afterdark vibe
st.markdown("""
    <style>
    /* Main Background and Text */
    .stApp {
        background-color: #1b1d36; /* Deep navy/purple */
        color: #cbdaeb; /* Soft off-white/blue text */
        font-family: 'Courier New', Courier, monospace;
    }
    
    /* Hide Default Streamlit UI */
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Accent Colors for Headers */
    h1, h2, h3 {
        color: #99d6ea !important; /* Neon Teal */
    }
    
    /* Text Input Styling */
    .stTextInput input {
        background-color: #222442 !important;
        color: #99d6ea !important;
        border: 2px solid #3b3f70 !important;
        border-radius: 8px;
        font-size: 1.1rem;
    }
    .stTextInput input:focus {
        border-color: #c678dd !important; /* Neon Pink/Purple focus */
        box-shadow: none !important;
    }
    
    /* Button Styling */
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

    /* Sentiment Metric Cards */
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
    """Returns CSS color based on sentiment score"""
    if score is None:
        return "#6272a4"
    if score <= -0.1:
        return "#ff5c57" # Red/Pink for negative
    elif score >= 0.1:
        return "#50fa7b" # Green/Teal for positive
    else:
        return "#6272a4" # Grey/Muted for neutral

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
# 3. SESSION STATE MANAGEMENT
# ==========================================
if 'has_run' not in st.session_state:
    st.session_state.has_run = False
if 'current_ticker' not in st.session_state:
    st.session_state.current_ticker = ""

# ==========================================
# 4. UI ROUTING (HOME vs. DASHBOARD)
# ==========================================

if not st.session_state.has_run:
    # --- HOME SCREEN (Centered) ---
    st.markdown("<br><br><br><br><br><br><br>", unsafe_allow_html=True) # Vertical centering
    
    col_spacer1, col_center, col_spacer2 = st.columns([1, 2, 1])
    
    with col_center:
        st.markdown("<h1 style='text-align: center; font-size: 3rem;'>📦 Analyst in a Box</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #6272a4;'>ENTERPRISE QUANTITATIVE NLP ENGINE</p>", unsafe_allow_html=True)
        
        search_col, btn_col = st.columns([4, 1])
        with search_col:
            ticker_input = st.text_input("", placeholder="Enter any ticker, eg. AAPL", label_visibility="collapsed")
        with btn_col:
            st.markdown("<br>", unsafe_allow_html=True) # align button with input
            execute_btn = st.button("EXECUTE")
            
        if execute_btn and ticker_input:
            st.session_state.current_ticker = ticker_input.upper()
            st.session_state.has_run = True
            st.rerun()

else:
    # --- DASHBOARD SCREEN (Top Aligned) ---
    ticker = st.session_state.current_ticker
    
    # Top pinned search bar
    top_spacer1, top_center, top_spacer2 = st.columns([1, 2, 1])
    with top_center:
        st.markdown("<h3 style='text-align: center;'>📦 Analyst in a Box</h3>", unsafe_allow_html=True)
        search_col, btn_col = st.columns([4, 1])
        with search_col:
            new_ticker = st.text_input("", value=ticker, placeholder="Enter any ticker, eg. AAPL", label_visibility="collapsed", key="top_search")
        with btn_col:
            if st.button("EXECUTE", key="top_btn"):
                st.session_state.current_ticker = new_ticker.upper()
                st.rerun()
                
    st.markdown("---")
    
    # --- RUN THE BACKEND (Your LangGraph Pipeline) ---
    with st.spinner(f"Initiating pipeline for {ticker}... (Fetching Data, Running FinBERT, Synthesizing)"):
        # IMPORT YOUR COMPILED PIPELINE
        try:
            from backend import app
            
            initial_state = {"ticker": ticker}
            result = app.invoke(initial_state)
            
        except Exception as e:
            st.error(f"Failed to run the pipeline. Error: {e}")
            result = {}
        
    # --- RENDER THE 3 COLUMNS ---
    col_left, col_mid, col_right = st.columns([1, 2, 1], gap="large")
    
    # 1. Left Column: Sentiment
    with col_left:
        st.subheader("NLP Sentiment")
        render_sentiment_card("Internal (SEC 10-K)", result.get("internal_sentiment", 0))
        render_sentiment_card("External (News)", result.get("external_sentiment", 0))
        render_sentiment_card("Executive (Call)", result.get("transcript_sentiment", 0))

    # 2. Middle Column: AI Synthesis
    with col_mid:
        st.subheader("Final Equitystream Forecast")
        st.markdown(f"> {result.get('final_report', 'Pipeline did not return a final report.')}")
        
    # 3. Right Column: Market Data & News
    with col_right:
        st.subheader("Market Reality")
        try:
            # Fetch last 30 days of stock data
            hist = yf.Ticker(ticker).history(period="1mo")
            if not hist.empty:
                current_price = hist['Close'].iloc[-1]
                st.metric("Current Price", f"${current_price:.2f}")
                # Streamlit's native line chart (will match our dark theme)
                st.line_chart(hist['Close'], height=150)
        except Exception:
            st.error("Failed to fetch market data.")
            
        st.markdown("**Recent Catalysts (News)**")
        headlines = result.get("news_headlines", [])
        if headlines:
            for headline in headlines[:3]: # Show top 3
                st.markdown(f"- <span style='color: #6272a4; font-size: 0.9rem;'>{headline}</span>", unsafe_allow_html=True)
        else:
            st.markdown("<span style='color: #6272a4; font-size: 0.9rem;'>No recent headlines available.</span>", unsafe_allow_html=True)