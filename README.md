# Analyst in a Box

An autonomous AI equity research engine built with LangGraph and Streamlit. Enter any ticker and the pipeline aggregates SEC 10-K filings, earnings call transcripts, live market news, and quantitative financials — then fuses FinBERT NLP sentiment scoring with LLM Chain-of-Thought synthesis to deliver a rigorous fundamental forecast.

---

## How It Works

### Pipeline Architecture

```mermaid
---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([START]):::first
	fetch_data(fetch_data)
	financial_diagnostic(financial_diagnostic)
	external_sentiment(external_sentiment)
	internal_sentiment(internal_sentiment)
	transcript_sentiment(transcript_sentiment)
	synthesis(synthesis)
	__end__([END]):::last
	__start__ --> fetch_data;
	fetch_data --> external_sentiment;
	fetch_data --> financial_diagnostic;
	fetch_data --> internal_sentiment;
	fetch_data --> transcript_sentiment;
	external_sentiment --> synthesis;
	financial_diagnostic --> synthesis;
	internal_sentiment --> synthesis;
	transcript_sentiment --> synthesis;
	synthesis --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
```

After `fetch_data` completes, the two analysis nodes run in parallel before converging at `synthesis`.

### Node Breakdown

| Node | What it does |
|---|---|
| `fetch_data` | Pulls yfinance financials, DuckDuckGo news, SEC 10-K MD&A via edgartools, and earnings call transcripts via Defeat-Beta API |
| `financial_diagnostic` | Runs a 4-step Chain-of-Thought quantitative analysis on 3-4 years of income, balance sheet, and cash flow data using Groq LLaMA 3.3 70B |
| `external_sentiment` | Scores market news headlines with FinBERT (-1 to 1) |
| `internal_sentiment` | Chunks and scores SEC MD&A text with FinBERT (-1 to 1) |
| `transcript_sentiment` | Chunks and scores earnings call transcript with FinBERT (-1 to 1) |
| `synthesis` | Synthesizes the diagnostic + sentiment scores into a final enterprise forecast using Groq LLaMA 3.3 70B |

---

## Stack

- **Orchestration**: LangGraph
- **LLM**: Groq (LLaMA 3.3 70B)
- **NLP**: FinBERT (ProsusAI/finbert via HuggingFace Transformers)
- **Financial Data**: yfinance, SEC EDGAR (edgartools), Defeat-Beta API
- **News**: DuckDuckGo Search (ddgs)
- **Frontend**: Streamlit

---

## Setup

```bash
pip install -r requirements.txt
streamlit run frontend.py
```

Set your API keys in a `.env` file:

```
GROQ_API_KEY=your_key_here
```

---

## Usage

1. Enter any stock ticker (e.g. `AAPL`, `TSLA`, `NVDA`)
2. The pipeline fetches and analyzes data across all four parallel nodes
3. The dashboard displays:
   - **NLP Sentiment** scores for SEC filings, news, and earnings calls
   - **Quantitative Financial Diagnostic** with multi-year trend analysis
   - **Final Enterprise Forecast** synthesized from all signals
   - **Market Reality** — live price and 30-day chart
