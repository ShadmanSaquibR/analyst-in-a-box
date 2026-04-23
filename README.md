# Analyst in a Box

Institutional-grade equity research generated in seconds using AI and NLP.

Built at Columbia University.

---

## Overview

Analyst in a Box is a full-stack financial research platform that ingests data from four primary sources — SEC EDGAR filings, earnings call transcripts, financial news, and market data — and synthesizes them into a structured equity forecast using a two-model AI pipeline (FinBERT + LLaMA 3.3 70B).

The system is designed around the same analytical framework used by institutional equity research desks: quantitative baseline → NLP sentiment scoring → synthesis with explicit citation of hard numbers.

---

## Architecture

```mermaid
graph TB
    subgraph Frontend ["Frontend — frontendpro.py (Streamlit)"]
        UI["Home Screen / Dashboard"]
        BAR["Live Trading Bar\n(S&P 500 · NASDAQ · DOW · VIX · Clock)"]
        CHARTS["Plotly Charts\n(Price · Earnings · Sentiment Gauges)"]
        EXPORT["PDF & JSON Export"]
    end

    subgraph Pipeline ["Pipeline — state_version_2_2_1.py (LangGraph)"]
        direction TB
        FETCH["fetch_data_node\n(Parallel — 4 workers)"]

        subgraph Concurrent ["Run concurrently"]
            DIAG["financial_diagnostic_node\nLLaMA 3.3 70B — 4-Step CoT"]
            SENT["sentiment_node\nFinBERT — batched inference"]
        end

        SYNTH["synthesis_node\nLLaMA 3.3 70B — Final Forecast"]
    end

    subgraph Sources ["External Data Sources"]
        YF["yfinance\nIncome · Balance Sheet · Cash Flow"]
        DDG["DuckDuckGo News\nReal-time financial headlines"]
        EDGAR["SEC EDGAR\n10-K MD&A via edgartools"]
        DB["Defeat-Beta API\nEarnings call transcripts"]
    end

    subgraph Models ["AI Models"]
        GROQ["Groq API\nLLaMA 3.3 70B Versatile"]
        BERT["HuggingFace\nProsusAI/FinBERT"]
    end

    UI -->|"ticker"| FETCH
    FETCH --> YF & DDG & EDGAR & DB
    FETCH --> DIAG
    FETCH --> SENT
    DIAG --> SYNTH
    SENT --> SYNTH
    SYNTH -->|"final state"| UI
    DIAG --> GROQ
    SYNTH --> GROQ
    SENT --> BERT
    UI --> BAR & CHARTS & EXPORT
```

---

## Pipeline Flow

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend
    participant FN as fetch_data_node
    participant FD as financial_diagnostic_node
    participant SN as sentiment_node
    participant SY as synthesis_node

    U->>FE: Enter ticker (equity only)
    FE->>FE: Validate quote_type = EQUITY
    FE->>FN: Launch background thread

    par Parallel data fetch (ThreadPoolExecutor x 4)
        FN->>FN: yfinance financials
        FN->>FN: DuckDuckGo news headlines
        FN->>FN: SEC EDGAR 10-K MD&A
        FN->>FN: Defeat-Beta earnings transcript
    end

    par Concurrent AI inference (asyncio)
        FN->>FD: financial_data
        FD->>FD: LLaMA 3.3 70B — 4-Step Chain of Thought
        FN->>SN: headlines + MD&A + transcript
        SN->>SN: FinBERT — batched sentiment scoring
    end

    FD->>SY: financial_diagnostic
    SN->>SY: internal / external / transcript sentiment scores
    SY->>SY: LLaMA 3.3 70B — Final Enterprise Forecast
    SY->>FE: CompanyAnalysisState (full result dict)
    FE->>U: Render dashboard
```

---

## LangGraph State Machine

```mermaid
stateDiagram-v2
    [*] --> fetch_data
    fetch_data --> financial_diagnostic
    fetch_data --> sentiment
    financial_diagnostic --> synthesis
    sentiment --> synthesis
    synthesis --> [*]
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit, Plotly |
| Orchestration | LangGraph, LangChain |
| LLM | LLaMA 3.3 70B via Groq API |
| Sentiment | FinBERT (ProsusAI/finbert) via HuggingFace |
| Financial Data | yfinance |
| News | DuckDuckGo Search (ddgs) |
| SEC Filings | edgartools (SEC EDGAR) |
| Transcripts | Defeat-Beta API |
| PDF Export | fpdf2 |
| Environment | python-dotenv |

---

## Setup

**1. Clone the repository**
```bash
git clone https://github.com/your-org/analyst-in-a-box.git
cd analyst-in-a-box
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Configure environment variables**

Create a `.env` file in the project root (never commit this):
```
GROQ_API_KEY=gsk_...
EMAIL_EDGAR_API=your@email.com
```

- `GROQ_API_KEY` — free key at [console.groq.com](https://console.groq.com)
- `EMAIL_EDGAR_API` — any valid email, used as the SEC EDGAR user-agent identifier

**4. Run**
```bash
streamlit run frontendpro.py
```

---

## Cloud Deployment

Secrets are injected via the hosting platform — never hardcoded.

**Streamlit Community Cloud:**
1. Push repo to GitHub (`.env` is gitignored and never leaves your machine)
2. Connect at [share.streamlit.io](https://share.streamlit.io), set entry point to `frontendpro.py`
3. Add under **Settings → Secrets**:
```toml
GROQ_API_KEY = "gsk_..."
EMAIL_EDGAR_API = "your@email.com"
```

**Railway / Render / Fly.io:** set the same two variables in the platform's environment UI. No code changes required.

---

## Project Structure

```
analyst-in-a-box/
├── frontendpro.py          # Streamlit UI — trading bar, charts, dashboard
├── state_version_2_2_1.py  # LangGraph pipeline — data fetch, AI inference
├── fixtures.py             # Demo mode fixture data (DEMO_MODE=1)
├── requirements.txt
└── .env                    # Local secrets — never committed
```

---

## Key Design Decisions

**Parallel fetching.** All four data sources are fetched concurrently via `ThreadPoolExecutor`, cutting fetch latency by ~75% vs. sequential calls.

**Batched FinBERT inference.** Headlines, MD&A chunks, and transcript chunks are concatenated into a single batched forward pass rather than three sequential calls.

**Concurrent LLM + NLP.** The quantitative diagnostic (LLaMA) and sentiment scoring (FinBERT) run concurrently via `asyncio` since neither depends on the other's output.

**Equity-only validation.** The frontend checks `quote_type == EQUITY` via `yfinance.fast_info` before running the pipeline, blocking crypto, ETFs, indices, futures, and mutual funds.

---

## Disclaimer

For informational and academic purposes only. Not investment advice. Past performance does not predict future results. This tool does not constitute a recommendation to buy or sell any security.

---

## Contact

Columbia University

- sy2367@columbia.edu
- mu2330@columbia.edu
- ssr2208@columbia.edu
