import streamlit as st
from backend_engine import app as langgraph_app

# 1. Page Configuration
st.set_page_config(
    page_title="Quant Terminal", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# Custom CSS for a dark-mode terminal look
st.markdown("""
    <style>
    .stMetric {
        background-color: #1E1E1E;
        padding: 15px;
        border-radius: 5px;
        border: 1px solid #333;
    }
    </style>
""", unsafe_allow_html=True)

# 2. Sidebar Command Center
st.sidebar.title("⚙️ System Command")
ticker = st.sidebar.text_input("Enter Ticker (e.g., AAPL):", "AAPL").upper()
run_button = st.sidebar.button("Execute Diagnostic", type="primary")

st.sidebar.markdown("---")
st.sidebar.caption("MATH GR5470 | Columbia University")

# 3. Main Dashboard Area
st.title(f"📊 Enterprise Diagnostic Terminal: {ticker}")
st.markdown("---")

if run_button:
    with st.spinner("Executing Pipeline... (Pacing API requests to respect limits. This takes ~45 seconds)"):
        try:
            # Trigger your LangGraph Engine
            initial_state = {"ticker": ticker}
            result = langgraph_app.invoke(initial_state)

            # --- TOP ROW: FINBERT METRICS ---
            st.subheader("🦾 FinBERT Sentiment Metrics (-1.0 to 1.0)")
            col1, col2, col3 = st.columns(3)
            
            internal = result.get('internal_sentiment', 0.0)
            external = result.get('external_sentiment', 0.0)
            executive = result.get('transcript_sentiment', 0.0)

            col1.metric("Internal (SEC 10-K)", f"{internal:.2f}")
            col2.metric("External (News)", f"{external:.2f}")
            col3.metric("Executive (Transcript)", f"{executive:.2f}")

            st.markdown("---")

            # --- BOTTOM ROW: FINAL FORECAST ---
            st.subheader("🧠 Synthesized Enterprise Forecast")
            st.markdown(result.get("final_report", "No report generated."))

        except Exception as e:
            st.error(f"☢️ SYSTEM ERROR: {e}")
else:
    st.info("Awaiting command. Enter a ticker in the sidebar and execute the diagnostic.")