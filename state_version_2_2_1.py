# -*- coding: utf-8 -*-
"""state_version_2_2_1.py

Refactored from State_Version_2.1.3 with four efficiency improvements:
  1. Parallel data fetching (yfinance, DDG, EDGAR, Defeat-Beta run concurrently)
  2. Single batched FinBERT call instead of three sequential ones
  3. Optional disk cache for fetched data during development
  4. Async LLM nodes so the diagnostic call and FinBERT sentiment actually
     run concurrently under app.ainvoke() (not just on paper).

Set DEV_CACHE=1 in your environment to enable the dev cache.
Set GROQ_API_KEY and EMAIL_EDGAR_API in .env (never commit these).
"""

# --- IMPORTS ---
import os
import asyncio
import hashlib
import pickle
import warnings
from pathlib import Path
from datetime import date
from functools import wraps
from concurrent.futures import ThreadPoolExecutor
from typing import TypedDict, List

from dotenv import load_dotenv
load_dotenv()

DEMO_MODE = os.getenv("DEMO_MODE", "0") == "1"

import torch
import yfinance as yf
import pandas as pd
import requests
from ddgs import DDGS
from edgar import set_identity, Company
from defeatbeta_api.data.ticker import Ticker
from transformers import pipeline
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter

warnings.filterwarnings('ignore', category=DeprecationWarning)
warnings.filterwarnings('ignore', message='.*utcnow.*')

# --- 1. AUTHENTICATION ---
edgar_email = os.getenv("EMAIL_EDGAR_API", "mu2330@columbia.edu")
set_identity(edgar_email)

groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    raise RuntimeError(
        "GROQ_API_KEY not set. Add it to your .env file as:\n"
        "  GROQ_API_KEY=gsk_..."
    )

# --- 2. INITIALIZE MODELS ---
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.0,
    max_retries=5,
    api_key=groq_api_key,
)

print("Loading FinBERT model... (this may take a moment)")
finbert = pipeline(
    "sentiment-analysis",
    model="ProsusAI/finbert",
    truncation=True,
    max_length=512,
)

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

# ============================================================
# DEV CACHE (optional — set DEV_CACHE=1 to enable)
# ============================================================
CACHE_DIR = Path(".fsa_cache")
CACHE_DIR.mkdir(exist_ok=True)
_CACHE_ENABLED = os.getenv("DEV_CACHE") == "0"

def disk_cache(fn):
    """Cache fetcher results to disk, keyed by args + today's date.
    No-op unless DEV_CACHE=1. Delete .fsa_cache/ for a clean run."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not _CACHE_ENABLED:
            return fn(*args, **kwargs)
        key = hashlib.md5(
            f"{fn.__name__}:{args}:{kwargs}:{date.today()}".encode()
        ).hexdigest()
        path = CACHE_DIR / f"{key}.pkl"
        if path.exists():
            return pickle.loads(path.read_bytes())
        result = fn(*args, **kwargs)
        path.write_bytes(pickle.dumps(result))
        return result
    return wrapper

print(f"Setup complete! Models loaded and State defined. (dev cache: {'on' if _CACHE_ENABLED else 'off'})")

# ============================================================
# FETCH HELPERS
# ============================================================

@disk_cache
def _fetch_financials(ticker: str) -> str:
    stock = yf.Ticker(ticker)
    inc = stock.income_stmt
    bs = stock.balance_sheet
    cf = stock.cashflow

    # TEST MODE: 2 years, key rows only — cuts ~70% of financial tokens
    KEY_INC = ['Total Revenue', 'Gross Profit', 'Operating Income', 'Net Income', 'Diluted EPS']
    KEY_BS  = ['Total Assets', 'Total Debt', 'Stockholders Equity', 'Current Assets', 'Current Liabilities']
    KEY_CF  = ['Operating Cash Flow', 'Free Cash Flow', 'Capital Expenditure']
    def _slim(df, keys):
        if df is None: return "Data unavailable"
        rows = [r for r in keys if r in df.index]
        if DEMO_MODE:
            return df.loc[rows].iloc[:, :2].to_string() if rows else df.iloc[:5, :2].to_string()
        return df.loc[rows].to_string() if rows else df.iloc[:5].to_string()
    income_str    = _slim(inc, KEY_INC)
    cash_flow_str = _slim(cf,  KEY_CF)
    bs_str        = _slim(bs,  KEY_BS)

    try:
        shares_out = stock.info.get('sharesOutstanding', 'N/A')
    except Exception:
        shares_out = 'N/A'

    metrics = {}
    try:
        try:
            op_inc = inc.loc['Operating Income'].iloc[:3].values[::-1]
            rev = inc.loc['Total Revenue'].iloc[:3].values[::-1]
            margins = [(o / r) * 100 for o, r in zip(op_inc, rev)]
            metrics['Operating Margin'] = "[" + ", ".join(f"{m:.2f}%" for m in margins) + "] (Oldest to Newest)"
        except Exception:
            metrics['Operating Margin'] = "N/A"

        try:
            net_inc = inc.loc['Net Income'].iloc[:3].values[::-1]
            equity = (
                bs.loc['Stockholders Equity'].iloc[:3].values[::-1]
                if 'Stockholders Equity' in bs.index
                else bs.loc['Total Equity Gross Minority Interest'].iloc[:3].values[::-1]
            )
            roes = [(n / e) * 100 for n, e in zip(net_inc, equity)]
            metrics['Return on Equity (ROE)'] = "[" + ", ".join(f"{r:.2f}%" for r in roes) + "] (Oldest to Newest)"
        except Exception:
            metrics['Return on Equity (ROE)'] = "N/A"

        try:
            ca = (
                bs.loc['Current Assets'].iloc[:3].values[::-1]
                if 'Current Assets' in bs.index
                else bs.loc['Total Current Assets'].iloc[:3].values[::-1]
            )
            cl = (
                bs.loc['Current Liabilities'].iloc[:3].values[::-1]
                if 'Current Liabilities' in bs.index
                else bs.loc['Total Current Liabilities'].iloc[:3].values[::-1]
            )
            ratios = [(a / l) for a, l in zip(ca, cl)]
            metrics['Current Ratio'] = "[" + ", ".join(f"{r:.2f}" for r in ratios) + "] (Oldest to Newest)"
        except Exception:
            metrics['Current Ratio'] = "N/A"

        try:
            total_debt = bs.loc['Total Debt'].iloc[:3].values[::-1]
            ratios = [(d / e) for d, e in zip(total_debt, equity)]
            metrics['Debt-to-Equity Ratio'] = "[" + ", ".join(f"{r:.2f}" for r in ratios) + "] (Oldest to Newest)"
        except Exception:
            metrics['Debt-to-Equity Ratio'] = "N/A"

    except Exception as e:
        print(f"   WARNING: Math pre-computation failed for {ticker}. Error: {e}")

    header = "--- PYTHON PRE-COMPUTED QUANT METRICS (3-YEAR TREND) ---\n"
    header += "".join(f"{k}: {v}\n" for k, v in metrics.items())
    header += f"Shares Outstanding (Current): {shares_out}\n"
    header += "---------------------------------------------------------\n\n"

    return f"{header}INCOME STATEMENT:\n{income_str}\n\nBALANCE SHEET:\n{bs_str}\n\nCASH FLOW:\n{cash_flow_str}"


@disk_cache
def _fetch_news(ticker: str) -> List[str]:
    try:
        results = list(DDGS().news(f"{ticker} stock", max_results=8))
        if not results:
            print(f"   WARNING: DuckDuckGo returned an empty list for {ticker}.")
            return ["News fetch failed."]
        headlines = [r['title'] + " - " + r['body'] for r in results]
        print(f"   Successfully scraped {len(headlines)} news articles for {ticker}.")
        return headlines
    except Exception as e:
        print(f"   WARNING: News scraper crashed for {ticker}. Error: {e}")
        return ["News fetch failed."]


@disk_cache
def _fetch_mda(ticker: str) -> str:
    try:
        latest = Company(ticker).get_filings(form="10-K").latest()
        mda_text = latest.obj().management_discussion
        if not mda_text:
            mda_text = latest.text()[:3000] if DEMO_MODE else latest.text()
        if DEMO_MODE:
            mda_text = mda_text[:3000]
        print(f"   Successfully scraped SEC 10-K MD&A for {ticker} ({len(mda_text)} chars).")
        return mda_text
    except Exception as e:
        print(f"   WARNING: SEC scraper failed for {ticker}. Error: {e}")
        return "MD&A fetch failed or unavailable."


@disk_cache
def _fetch_transcript(ticker: str) -> str:
    try:
        df = Ticker(ticker).earning_call_transcripts().get_transcripts_list()
        if df is None or df.empty:
            print(f"   WARNING: No transcript found on Defeat-Beta for {ticker}.")
            return "Transcript unavailable."
        df = df.sort_values(by=['fiscal_year', 'fiscal_quarter'])
        paragraphs = df.iloc[-1]['transcripts']
        full_text = " ".join(p.get('content', '') for p in paragraphs)
        if DEMO_MODE:
            full_text = full_text[:3000]
        print(f"   Successfully scraped Defeat-Beta Transcript for {ticker} ({len(full_text)} chars).")
        return full_text
    except Exception as e:
        print(f"   WARNING: Defeat-Beta scraper failed for {ticker}. Error: {e}")
        return "Transcript fetch failed."


# ============================================================
# LANGGRAPH NODES
# ============================================================

def fetch_data_node(state: CompanyAnalysisState):
    ticker = state["ticker"]
    print(f"[{ticker}] Fetching all sources in parallel...")

    with ThreadPoolExecutor(max_workers=4) as ex:
        f_fin = ex.submit(_fetch_financials, ticker)
        f_news = ex.submit(_fetch_news, ticker)
        f_mda = ex.submit(_fetch_mda, ticker)
        f_tx = ex.submit(_fetch_transcript, ticker)

        return {
            "financial_data": f_fin.result(),
            "news_headlines": f_news.result(),
            "mda_text": f_mda.result(),
            "transcript_text": f_tx.result(),
        }


async def financial_diagnostic_node(state: CompanyAnalysisState):
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
    response = await llm.ainvoke(prompt)
    return {"financial_diagnostic": response.content}


def _to_score(results):
    if not results:
        return 0.0
    return sum(
        r['score'] if r['label'] == 'positive'
        else -r['score'] if r['label'] == 'negative'
        else 0
        for r in results
    ) / len(results)


def _chunk(text, size=2000, max_chunks=5):
    if not text or text in (
        "MD&A fetch failed or unavailable.",
        "Transcript unavailable.",
        "Transcript fetch failed.",
    ):
        return []
    chunks = [text[i:i+size] for i in range(0, len(text), size)]
    return chunks[:max_chunks] if DEMO_MODE else chunks


async def sentiment_node(state: CompanyAnalysisState):
    ticker = state["ticker"]
    print(f"[{ticker}] Running batched FinBERT sentiment...")

    headlines = state.get("news_headlines", [])
    if headlines == ["News fetch failed."]:
        headlines = []
    mda_chunks = _chunk(state.get("mda_text", ""))
    tx_chunks = _chunk(state.get("transcript_text", ""))

    all_inputs = headlines + mda_chunks + tx_chunks
    if not all_inputs:
        return {
            "external_sentiment": 0.0,
            "internal_sentiment": 0.0,
            "transcript_sentiment": 0.0,
        }

    try:
        all_results = await asyncio.to_thread(finbert, all_inputs, batch_size=16)
    except Exception as e:
        print(f"   WARNING: FinBERT batch failed for {ticker}: {e}")
        return {
            "external_sentiment": 0.0,
            "internal_sentiment": 0.0,
            "transcript_sentiment": 0.0,
        }

    n1 = len(headlines)
    n2 = n1 + len(mda_chunks)
    return {
        "external_sentiment":   _to_score(all_results[:n1]),
        "internal_sentiment":   _to_score(all_results[n1:n2]),
        "transcript_sentiment": _to_score(all_results[n2:]),
    }


async def synthesis_node(state: CompanyAnalysisState):
    ticker = state["ticker"]
    print(f"[{ticker}] Synthesizing Final Enterprise Forecast Report...")

    internal_sent = state.get('internal_sentiment', 0.0)
    external_sent = state.get('external_sentiment', 0.0)
    transcript_sent = state.get('transcript_sentiment', 0.0)

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

    raw_transcript = state.get('transcript_text', 'No transcript available.')
    if raw_transcript not in ["No transcript available.", "Transcript fetch failed.", "Transcript unavailable.", ""]:
        try:
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=3000,
                chunk_overlap=200,
                separators=["\n\n", "\n", ".", " "],
            )
            docs = text_splitter.split_text(raw_transcript)
            clean_transcript_chunk = (docs[0] if docs else "No transcript available.") if DEMO_MODE else " ".join(docs)
        except Exception as e:
            print(f"WARNING: Smart chunking failed for {ticker}: {e}")
            clean_transcript_chunk = raw_transcript[:3000] if DEMO_MODE else raw_transcript
    else:
        clean_transcript_chunk = "No transcript available."

    content = f"""
    Ticker: {ticker}

    --- QUANTITATIVE FINANCIAL DIAGNOSTIC ---
    {state.get('financial_diagnostic', 'No diagnostic available.')}

    --- EARNINGS CALL TRANSCRIPT EXCERPT ---
    {clean_transcript_chunk}
    """

    msg = await llm.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=content),
    ])

    return {"final_report": msg.content}


# ============================================================
# COMPILE THE GRAPH
# ============================================================
workflow = StateGraph(CompanyAnalysisState)

workflow.add_node("fetch_data", fetch_data_node)
workflow.add_node("financial_diagnostic", financial_diagnostic_node)
workflow.add_node("sentiment", sentiment_node)
workflow.add_node("synthesis", synthesis_node)

workflow.set_entry_point("fetch_data")
workflow.add_edge("fetch_data", "financial_diagnostic")
workflow.add_edge("fetch_data", "sentiment")
workflow.add_edge("financial_diagnostic", "synthesis")
workflow.add_edge("sentiment", "synthesis")
workflow.add_edge("synthesis", END)

app = workflow.compile()
print("LangGraph Pipeline compiled successfully!")


# ============================================================
# PUBLIC ENTRY POINT FOR FRONTENDS
# ============================================================
def run_pipeline(ticker: str) -> dict:
    """Synchronous wrapper around the async LangGraph pipeline.
    Safe to call from Streamlit or any sync context. Returns the final state dict."""
    return asyncio.run(app.ainvoke({"ticker": ticker}))
