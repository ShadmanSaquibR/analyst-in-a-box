# -*- coding: utf-8 -*-
"""State_version2.1.2.ipynb
###Setting up the environment
"""

"""###Setting up authentication and defining the Langgraph state."""

#Setup, Authentication, and State
import os
from dotenv import load_dotenv

load_dotenv()
import torch
import yfinance as yf
from ddgs import DDGS
from edgar import set_identity, Company
from transformers import pipeline
from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter
import warnings
import requests
import time
from defeatbeta_api.data.ticker import Ticker
import pandas as pd

warnings.filterwarnings('ignore', category=DeprecationWarning)
warnings.filterwarnings('ignore', message='.*utcnow.*')

# --- 1. AUTHENTICATION ---
set_identity("ssr2208@columbia.edu") # Apparently, SEC EDGAR requires this

# --- 2. INITIALIZE MODELS ---
# Using Gemini 2.5 Pro for the free tier speed/limits. Temp 0.0 for deterministic diagnostic logic.
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.0,
    max_retries=5
)

# Initializing FinBERT. truncation=True prevents memory crashes on massive SEC filings!
print("Loading FinBERT model... (this may take a moment)")
finbert = pipeline("sentiment-analysis", model="ProsusAI/finbert", truncation=True, max_length=512)

# --- 3. DEFINE LANGGRAPH STATE ---
class CompanyAnalysisState(TypedDict):
    ticker: str
    financial_data: str
    news_headlines: List[str]
    mda_text: str
    transcript_text: str
    financial_diagnostic: str
    external_sentiment: float
    internal_sentiment: float
    transcript_sentiment: float
    final_report: str

print("Setup complete! Models loaded and State defined.")

"""###Langgraph Pipline (Data Ingestion and ML diagnostic)"""

#The LangGraph Pipeline

# --- NODE: Data Ingestion ---
def fetch_data_node(state: CompanyAnalysisState):
    ticker = state["ticker"]
    print(f"[{ticker}] Fetching Financials, News, and SEC Data...")

    # ==========================================
    # 1. Quantitative Financials & Math Baseline
    # ==========================================
    stock = yf.Ticker(ticker)

    # Get raw tables (Using up to 4 years to give the LLM full trend context)
    income_str = stock.income_stmt.iloc[:, :4].to_string() if stock.income_stmt is not None else "Data unavailable"
    cash_flow_str = stock.cashflow.iloc[:, :4].to_string() if stock.cashflow is not None else "Data unavailable"
    bs_str = stock.balance_sheet.iloc[:, :4].to_string() if stock.balance_sheet is not None else "Data unavailable"

    # Grab Shares Outstanding for the LLM prompt
    try:
        shares_out = stock.info.get('sharesOutstanding', 'N/A')
    except Exception:
        shares_out = 'N/A'

    # Compute 4-Pillar Math (Extracting 3-year arrays, Oldest -> Newest)
    metrics = {}
    try:
        inc = stock.income_stmt
        bs = stock.balance_sheet

        # Pillar 1: Profitability
        try:
            op_inc = inc.loc['Operating Income'].iloc[:3].values[::-1]
            rev = inc.loc['Total Revenue'].iloc[:3].values[::-1]
            margins = [(o / r) * 100 for o, r in zip(op_inc, rev)]
            metrics['Operating Margin'] = "[" + ", ".join([f"{m:.2f}%" for m in margins]) + "] (Oldest to Newest)"
        except Exception: metrics['Operating Margin'] = "N/A"

        try:
            net_inc = inc.loc['Net Income'].iloc[:3].values[::-1]
            equity = bs.loc['Stockholders Equity'].iloc[:3].values[::-1] if 'Stockholders Equity' in bs.index else bs.loc['Total Equity Gross Minority Interest'].iloc[:3].values[::-1]
            roes = [(n / e) * 100 for n, e in zip(net_inc, equity)]
            metrics['Return on Equity (ROE)'] = "[" + ", ".join([f"{r:.2f}%" for r in roes]) + "] (Oldest to Newest)"
        except Exception: metrics['Return on Equity (ROE)'] = "N/A"

        # Pillar 2: Liquidity
        try:
            curr_assets = bs.loc['Current Assets'].iloc[:3].values[::-1] if 'Current Assets' in bs.index else bs.loc['Total Current Assets'].iloc[:3].values[::-1]
            curr_liabs = bs.loc['Current Liabilities'].iloc[:3].values[::-1] if 'Current Liabilities' in bs.index else bs.loc['Total Current Liabilities'].iloc[:3].values[::-1]
            ratios = [(a / l) for a, l in zip(curr_assets, curr_liabs)]
            metrics['Current Ratio'] = "[" + ", ".join([f"{r:.2f}" for r in ratios]) + "] (Oldest to Newest)"
        except Exception: metrics['Current Ratio'] = "N/A"

        # Pillar 3: Solvency
        try:
            total_debt = bs.loc['Total Debt'].iloc[:3].values[::-1]
            ratios = [(d / e) for d, e in zip(total_debt, equity)]
            metrics['Debt-to-Equity Ratio'] = "[" + ", ".join([f"{r:.2f}" for r in ratios]) + "] (Oldest to Newest)"
        except Exception: metrics['Debt-to-Equity Ratio'] = "N/A"

    except Exception as e:
        print(f"   ☢ WARNING: Math pre-computation failed for {ticker}. Error: {e}")

    # Format the hard math context
    hard_math_context = "--- PYTHON PRE-COMPUTED QUANT METRICS (3-YEAR TREND) ---\n"
    for key, value in metrics.items():
        hard_math_context += f"{key}: {value}\n"
    hard_math_context += f"Shares Outstanding (Current): {shares_out}\n"
    hard_math_context += "---------------------------------------------------------\n\n"

    # Combine Math + ALL Raw Tables
    financial_data = f"{hard_math_context}INCOME STATEMENT:\n{income_str}\n\nBALANCE SHEET:\n{bs_str}\n\nCASH FLOW:\n{cash_flow_str}"

    # ==========================================
    # 2. Market News via DuckDuckGo
    # ==========================================
    try:
        results = list(DDGS().text(f"{ticker} stock financial news", max_results=5))
        if not results:
            print(f"   ☢ WARNING: DuckDuckGo returned an empty list for {ticker}.")
            headlines = ["News fetch failed."]
        else:
            headlines = [r['title'] + " - " + r['body'] for r in results]
            print(f"   ✅ Successfully scraped {len(headlines)} news articles.")
    except Exception as e:
        print(f"   ☢ WARNING: News scraper crashed for {ticker}. Error: {e}")
        headlines = ["News fetch failed."]


    # ==========================================
    # 3. SEC 10-K MD&A via edgartools
    # ==========================================
    try:
        filings = Company(ticker).get_filings(form="10-K")
        latest_10k_filing = filings.latest()
        tenk_obj = latest_10k_filing.obj()

        mda_text = tenk_obj.management_discussion

        if not mda_text:
            mda_text = latest_10k_filing.text()[:10000]

        print(f"   ✅ Successfully scraped SEC 10-K MD&A ({len(mda_text)} characters).")
    except Exception as e:
        print(f"   ☢ WARNING: SEC scraper failed or blocked for {ticker}. Error: {e}")
        mda_text = "MD&A fetch failed or unavailable."


    # ==========================================
    # 4. Earnings Call Transcripts via Defeat-Beta API
    # ==========================================
    try:
        db_ticker = Ticker(ticker)
        transcripts_df = db_ticker.earning_call_transcripts().get_transcripts_list()

        if transcripts_df is not None and not transcripts_df.empty:
            transcripts_df = transcripts_df.sort_values(by=['fiscal_year', 'fiscal_quarter'])
            latest_transcript_data = transcripts_df.iloc[-1]['transcripts']

            full_text = " ".join([paragraph.get('content', '') for paragraph in latest_transcript_data])
            transcript_text = full_text[:10000]
            print(f"   ✅ Successfully scraped Defeat-Beta Transcript ({len(transcript_text)} chars).")
        else:
            print(f"   ☢ WARNING: No transcript found on Defeat-Beta for {ticker}.")
            transcript_text = "Transcript unavailable."

    except Exception as e:
        print(f"   ☢ WARNING: Defeat-Beta scraper failed for {ticker}. Error: {e}")
        transcript_text = "Transcript fetch failed."

    # Return exactly what your pipeline needs!
    return {
        "financial_data": financial_data,
        "news_headlines": headlines,
        "mda_text": mda_text,
        "transcript_text": transcript_text
    }

# --- NODE: Gemini Financial Diagnostic (Chain-of-Thought) ---
def financial_diagnostic_node(state: CompanyAnalysisState):
    ticker = state["ticker"]
    print(f"[{ticker}] Running 4-Step CoT Quantitative Baseline...")

    prompt = f"""
    You are an expert equity analyst and quantitative forecaster. Analyze the following 3-to-4 year historical financial data for {ticker} using a strict 4-step Chain of Thought process.
    Your objective is to project the near-term direction of Earnings Per Share (EPS) and Free Cash Flow (FCF) by isolating their mathematical drivers and evaluating their multi-year trajectory.

    Financial Data:
    {state["financial_data"]}

    You MUST structure your response exactly like this:

    STEP 1: DATA EXTRACTION & TRAJECTORY ANALYSIS
    [MANDATORY: Do not just list the arrays. You MUST explicitly calculate and state the 3-year momentum of the pre-computed metrics. (e.g., "Operating Margin compressed from X% in Year 1 to Y% in Year 3"). Extract Net Income, Shares Outstanding, Operating Cash Flow, and Capital Expenditures, stating their trend over the timeline.]

    STEP 2: DRIVER IDENTIFICATION & MARGIN DECONSTRUCTION
    [Analyze the trends from Step 1. You MUST explain WHY the margins and net income moved. Did revenue grow slower than operating expenses? Did a massive CapEx cycle consume cash flow? Cite the specific dollar amounts from the Income Statement and Cash Flow statement to prove your point.]

    STEP 3: FORWARD PROJECTIONS
    [Based exclusively on the momentum of the numeric drivers in Step 2, state your clear projection for the near-term direction (Improving, Degrading, or Flat) of both EPS and FCF.]

    STEP 4: QUANTITATIVE RISK & CONVICTION
    [State your conviction level (High, Medium, Low). Identify one or two purely quantitative risks, citing the exact numbers from the balance sheet or cash flow statement that concern you.]
    """
    response = llm.invoke(prompt)
    return {"financial_diagnostic": response.content}

# --- NODE: External Sentiment (FinBERT) ---
def external_sentiment_node(state: CompanyAnalysisState):
    print(f"[{state['ticker']}] Calculating External Sentiment (Market News)...")

    try:
      headlines = state["news_headlines"]
      if not headlines or headlines[0] == "News fetch failed.": return {"external_sentiment": 0.0}

      results = finbert(headlines)
      score = sum([res['score'] if res['label'] == 'positive' else -res['score'] if res['label'] == 'negative' else 0 for res in results])
      return {"external_sentiment": score / len(headlines)}

    except Exception as e:
      print(f"   ☢ WARNING: External News API failed for {state['ticker']}. Error: {e}")
      return {"external_sentiment": 0.0}

# --- NODE: Internal Sentiment (FinBERT) ---
def internal_sentiment_node(state: CompanyAnalysisState):
    print(f"[{state['ticker']}] Calculating Internal Sentiment (SEC MD&A)...")

    try:
      mda_text = state["mda_text"]
      if mda_text == "MD&A fetch failed or unavailable.": return {"internal_sentiment": 0.0}

      # Chunking the massive MD&A text into blocks. We process the first 5 blocks for MVP speed.
      chunks = [mda_text[i:i+2000] for i in range(0, len(mda_text), 2000)][:5]
      results = finbert(chunks)
      score = sum([res['score'] if res['label'] == 'positive' else -res['score'] if res['label'] == 'negative' else 0 for res in results])
      return {"internal_sentiment": score / len(chunks)}

    except Exception as e:
      print(f"   ☢ WARNING: SEC EDGAR API failed for {state['ticker']}. Error: {e}")
      return {"internal_sentiment": 0.0}


# --- NODE: Transcript Sentiment (FinBERT) ---
def transcript_sentiment_node(state: CompanyAnalysisState):
    ticker = state.get("ticker", "UNKNOWN")
    print(f"[{ticker}] Calculating Executive Sentiment (Earnings Call)...")

    # Safely get text, defaulting to empty string if missing
    text = state.get("transcript_text", "")
    if text in ["Transcript unavailable.", "Transcript fetch failed.", ""]:
        return {"transcript_sentiment": 0.0}

    try:
      # Using a simple chunking here to avoid FinBERT length errors
      chunks = [text[i:i+2000] for i in range(0, len(text), 2000)][:5]
      if not chunks: # Catching if somehow chunks is empty
            return {"transcript_sentiment": 0.0}
      results = finbert(chunks)
      score = sum([res['score'] if res['label'] == 'positive' else -res['score'] if res['label'] == 'negative' else 0 for res in results])
      final_score = score / len(chunks)

    except Exception as e:
        print(f"⚠️ [WARNING] FinBERT transcript processing failed for {ticker}: {e}")
        final_score = 0.0

    return {"transcript_sentiment": final_score}

# --- NODE: Synthesis (Gemini/Groq) ---
def synthesis_node(state: CompanyAnalysisState):
    ticker = state["ticker"]
    print(f"[{ticker}] Synthesizing Final Enterprise Forecast Report...")

    # Safely get sentiment scores FIRST so we can inject them into the prompt
    internal_sent = state.get('internal_sentiment', 0.0)
    external_sent = state.get('external_sentiment', 0.0)
    transcript_sent = state.get('transcript_sentiment', 0.0)

    # NOW define the system prompt using f-strings to inject the actual scores
    system_prompt = f"""
    You are a Lead Portfolio Manager synthesizing quantitative data with NLP sentiment analysis.
    Synthesize the provided Financial Diagnostic, earnings transcripts, and sentiment metrics into a rigorous Final Enterprise Forecast.

    Do NOT provide stock trading advice or an investment rating.

    You MUST use a strict step-by-step Chain of Thought process.
    CRITICAL RULE: You are a quantitative analyst. You MUST explicitly cite the hard numbers, percentages, and dollar amounts from the Financial Diagnostic in your final report. Do not use vague terms like "improved" without stating the number.

    STEP 1: SENTIMENT VS. QUANTITATIVE ALIGNMENT
    [MANDATORY: Explicitly quote the exact ROE, Margins, and Debt metrics from the diagnostic. Then, evaluate if the Internal ({internal_sent:.2f}), External ({external_sent:.2f}), and Transcript ({transcript_sent:.2f}) sentiment scores confirm or contradict these hard numbers.]

    STEP 2: TRANSCRIPT CONTEXT & MANAGEMENT TONE
    [Extract 1-2 specific quotes from the transcript excerpt that either validate the quantitative drivers OR reveal management's forward guidance.]

    STEP 3: RISK VALIDATION
    [Look at the 'Quantitative Risk' identified in the diagnostic. Is there any evidence in the transcript excerpt or external sentiment that this specific numeric risk is materializing?]

    STEP 4: FINAL ENTERPRISE FORECAST
    [Synthesize the above into a final 3-4 sentence conclusion. You MUST include at least two hard quantitative metrics in your final paragraph to justify your projected direction of the business.]
    """

    # --- THE SMART CHUNKING UPGRADE ---
    raw_transcript = state.get('transcript_text', 'No transcript available.')

    if raw_transcript not in ["No transcript available.", "Transcript fetch failed.", ""]:
        try:
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=3000,
                chunk_overlap=200,
                separators=["\n\n", "\n", ".", " "]
            )
            docs = text_splitter.split_text(raw_transcript)
            clean_transcript_chunk = docs[0] if docs else "No transcript available."
        except Exception as e:
            print(f"⚠️ [WARNING] Smart chunking failed for {ticker}: {e}")
            clean_transcript_chunk = raw_transcript[:3000]
    else:
        clean_transcript_chunk = "No transcript available."

    content = f"""
    Ticker: {ticker}

    --- QUANTITATIVE FINANCIAL DIAGNOSTIC ---
    {state.get('financial_diagnostic', 'No diagnostic available.')}

    --- EARNINGS CALL TRANSCRIPT EXCERPT ---
    {clean_transcript_chunk}
    """

    # No time.sleep() needed here anymore!
    msg = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=content)
    ])

    return {"final_report": msg.content}

# --- COMPILING THE GRAPH ---
workflow = StateGraph(CompanyAnalysisState)

workflow.add_node("fetch_data", fetch_data_node)
workflow.add_node("financial_diagnostic", financial_diagnostic_node)
workflow.add_node("external_sentiment", external_sentiment_node)
workflow.add_node("internal_sentiment", internal_sentiment_node)
workflow.add_node("transcript_sentiment", transcript_sentiment_node)
workflow.add_node("synthesis", synthesis_node)

workflow.set_entry_point("fetch_data")
workflow.add_edge("fetch_data", "financial_diagnostic")
workflow.add_edge("fetch_data", "external_sentiment")
workflow.add_edge("fetch_data", "internal_sentiment")
workflow.add_edge("fetch_data", "transcript_sentiment")
workflow.add_edge("financial_diagnostic", "synthesis")
workflow.add_edge("external_sentiment", "synthesis")
workflow.add_edge("internal_sentiment", "synthesis")
workflow.add_edge("transcript_sentiment", "synthesis")
workflow.add_edge("synthesis", END)

app = workflow.compile()
print("LangGraph Pipeline compiled successfully!")

"""### Running the **MVP**"""

if __name__ == "__main__":
    test_tickers = ["TSLA"]

    for ticker in test_tickers:
        print(f"\n{'='*60}\nSTARTING ANALYSIS FOR: {ticker}\n{'='*60}")

        initial_state = {"ticker": ticker}
        result = app.invoke(initial_state)

        print(f"\n--- FINAL DIAGNOSTIC SCREENING: {ticker} ---\n")
        print(result["final_report"])
        print("\n--- FINBERT SENTIMENT METRICS ---")
        print(f"Internal Sentiment (SEC 10-K): {result['internal_sentiment']:.2f} (-1 to 1)")
        print(f"External Sentiment (News):     {result['external_sentiment']:.2f} (-1 to 1)")
        print(f"Executive Sentiment (Call):    {result['transcript_sentiment']:.2f} (-1 to 1)")