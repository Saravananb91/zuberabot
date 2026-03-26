# 🤖 Zubera Bot — AI-Powered Financial Advisory Assistant

> Personalized financial guidance, 24/7 via WhatsApp — powered by multi-provider AI, live Indian market data, and a persistent memory system.

![Python](https://img.shields.io/badge/Python_3.11+-3776AB?style=flat&logo=python&logoColor=white)
![Node.js](https://img.shields.io/badge/Node.js_18+-339933?style=flat&logo=node.js&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL_15-4169E1?style=flat&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white)
![WhatsApp](https://img.shields.io/badge/WhatsApp-25D366?style=flat&logo=whatsapp&logoColor=white)
![LiteLLM](https://img.shields.io/badge/LiteLLM-7+_Providers-FF6B6B?style=flat)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [LLM Providers](#llm-providers--ai-models)
- [Agent Tools](#agent-tools--capabilities)
- [Database Schema](#database-schema)
- [External APIs](#external-apis)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Deployment](#deployment)
- [Security](#security-model)
- [Project Structure](#project-structure)

---

## Overview

Individual investors lack access to affordable, personalized financial guidance. Professional advisors are expensive, and generic tools don't account for personal risk profiles, investment goals, or spending habits.

**Zubera Bot** solves this by delivering an autonomous, multi-provider AI agent that offers personalized financial advisory through natural WhatsApp conversation — backed by real-time Indian market data, persistent user profiles, and a vector-powered knowledge base.

### What it does

- Understands each user's financial context and risk appetite
- Remembers preferences and conversation history across sessions
- Provides **live mutual fund data** (NAV, 1Y/3Y returns) from MFAPI India
- Tracks expenses with category-wise budgeting in INR (₹)
- Delivers **goal-based investment recommendations** — retirement, wealth, emergency fund, child education, short-term
- Manages support tickets with priority and full lifecycle tracking
- Maintains a **RAG knowledge base** for financial document search

---

## Features

### 🏦 Mutual Fund Advisory
- Risk-profiled recommendations: **Conservative** (debt), **Moderate** (hybrid), **Aggressive** (equity)
- Goal-based planning: Retirement, Wealth, Emergency, Child Education, Short-term
- Interactive 3-step questionnaire — risk → amount → goal → personalized picks
- Live NAV data from MFAPI with **1-year and 3-year return** calculations
- Fund comparison tool (up to 3 funds side-by-side)
- Pre-configured fund picks with real scheme codes (HDFC, Kotak, SBI, DSP, etc.)

### 📊 Expense Tracking
- Log expenses across 7 categories: food, transport, bills, entertainment, shopping, healthcare, other
- Monthly summaries with category-wise breakdown in INR (₹)
- History queries with month and category filters + top-10 recent expenses

### 📈 Real-Time Market Data
- Live stock prices — global + NSE/BSE (e.g., `TATAMOTORS.NS`)
- Fund info: NAV, category, YTD return
- Market news per ticker (latest 3 articles)
- Historical performance data for return calculations

### 🧠 RAG Knowledge Base
- PostgreSQL vector store with JSON embeddings and hybrid matching
- Multi-context isolation: `banking`, `personal`, `general` (or custom)
- PDF document ingestion via `extract_text_from_pdf`
- Semantic search returns top 3 relevant passages

### 🎫 Support Ticket Management
- Create tickets with priority levels: `low` / `medium` / `high`
- Status lifecycle: `open` → `in_progress` → `resolved` → `closed`
- Email capture for follow-up notifications

### 🤖 Multi-User AI Agent
- Per-user **memory isolation**: long-term `MEMORY.md` + daily date notes
- Per-user **workspace** with configurable storage quotas (default 1 GB)
- Database-backed **session persistence** with 7-day auto-cleanup
- **Sub-agent delegation** for complex multi-step tasks
- Up to **20 tool-call iterations** per request
- Multi-modal: text + image attachments (base64)
- Auto-reconnect on WhatsApp bridge disconnection (5s retry)

### 🔍 Web Intelligence
- Brave Search for real-time market news and financial articles
- URL content fetching with HTML → Markdown extraction via Readability

---

## Architecture

### High-Level System Flow

```
┌─────────────────────────────────────────────────────────────┐
│                      👥 Users                               │
│              WhatsApp (end-to-end encrypted)                │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│              📡 Node.js Bridge (Baileys)                     │
│         QR Auth · WebSocket ws://localhost:3001             │
└────────────────────────┬────────────────────────────────────┘
                         │ WebSocket JSON
┌────────────────────────▼────────────────────────────────────┐
│           📨 WhatsApp Channel (Python)                       │
│     Parses messages · Creates InboundMessage · MessageBus   │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                    🧠 Agent Core                             │
│                                                             │
│  ┌─────────────────┐   ┌──────────────────┐                 │
│  │  Agent Loop     │   │  Context Builder  │                 │
│  │  Max 20 iters   │   │  Prompt Assembly  │                 │
│  └────────┬────────┘   └──────────────────┘                 │
│           │                                                 │
│  ┌────────▼────────────────────────────────────────────┐    │
│  │              Tool Registry (10+)                    │    │
│  │  📈 Finance  💰 Expense  🎫 Ticket  📚 RAG          │    │
│  │  🔍 Web Search  🌐 Web Fetch  📁 File  🖥️ Shell      │    │
│  └─────────────────────────────────────────────────────┘    │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
┌────────▼──────┐ ┌──────▼──────┐ ┌─────▼──────────┐
│  LiteLLM GW   │ │ PostgreSQL  │ │  External APIs  │
│  7+ Providers │ │  9 Tables   │ │  yFinance       │
│  Gemini/Groq/ │ │  + Vector   │ │  MFAPI India    │
│  Ollama/vLLM  │ │  RAG Store  │ │  Brave Search   │
└───────────────┘ └─────────────┘ └────────────────┘
```

### End-to-End Message Pipeline

```
1. User sends WhatsApp message
2. Node.js bridge (Baileys) → forwards JSON over WebSocket
3. WhatsAppChannel parses: sender phone, content, timestamp
   → InboundMessage → MessageBus
4. SessionManager retrieves ChatSession from PostgreSQL
   (key: "whatsapp:<phone>") · loads last 50 messages
5. UserContextBuilder assembles LLM prompt:
   ├── System Identity + Financial Advisor persona
   ├── User Memory: MEMORY.md + today's daily notes
   ├── Loaded Skills
   └── Conversation History (50 messages)
6. LiteLLM call (8192 tokens · temp 0.7 · 120s timeout)
7. Tool Execution Loop (up to 20 iterations):
   ├── LLM returns tool_calls → execute async → append results
   ├── Re-call LLM with updated context
   └── Repeat until final text OR 20 iterations
8. Final response → OutboundMessage → Bridge → WhatsApp
9. Persist to: sessions table + conversations table
```

### Key Source Files

| File | Path | Purpose |
|------|------|---------|
| `loop.py` | `zuberabot/agent/` | Agent loop — core processing engine |
| `context.py` | `zuberabot/agent/` | System prompt builder |
| `user_context.py` | `zuberabot/agent/` | Per-user context builder |
| `user_memory.py` | `zuberabot/agent/` | Long-term + daily memory system |
| `models.py` | `zuberabot/database/` | SQLAlchemy ORM (8 tables) |
| `postgres.py` | `zuberabot/database/` | DatabaseManager CRUD |
| `litellm_provider.py` | `zuberabot/providers/` | Multi-provider LLM gateway |
| `ollama.py` | `zuberabot/providers/` | Ollama + Financial safety layer |
| `whatsapp.py` | `zuberabot/channels/` | WhatsApp channel bridge client |
| `finance.py` | `zuberabot/agent/tools/` | Stocks, MF data, recommendations |
| `expense.py` | `zuberabot/agent/tools/` | Expense tracking |
| `ticket.py` | `zuberabot/agent/tools/` | Support ticket management |
| `rag.py` | `zuberabot/agent/tools/` | RAG knowledge base |
| `web.py` | `zuberabot/agent/tools/` | Web search + URL fetch |

---

## LLM Providers & AI Models

Zubera Bot supports **7 LLM providers** through a unified `LiteLLMProvider` abstraction.

| # | Provider | Model | Type | Env Var |
|---|----------|-------|------|---------|
| 1 | **Google Gemini** | `gemini-2.0-flash` | ☁️ Cloud | `GEMINI_API_KEY` |
| 2 | **Groq** | `llama-3.3-70b` | ☁️ Ultra-fast | `GROQ_API_KEY` |
| 3 | **OpenRouter** | Claude, GPT, Llama… | ☁️ Multi-model | `OPENROUTER_API_KEY` |
| 4 | **Ollama** | `mistral:7b-instruct-q4_K_M` | 🏠 Local | — |
| 5 | **Anthropic** | `claude-sonnet-4-5` | ☁️ Cloud | `ANTHROPIC_API_KEY` |
| 6 | **OpenAI** | GPT-4, GPT-3.5 | ☁️ Cloud | `OPENAI_API_KEY` |
| 7 | **vLLM** | Custom hosted | 🏠 Self-hosted | `OPENAI_API_KEY` (compat) |

### Provider Routing

```
"gemini/"     →  Google Gemini
"groq/"       →  Groq
"openrouter/" →  OpenRouter
"anthropic/"  →  Anthropic
"ollama/"     →  Ollama (local)
"openai/gpt"  →  OpenAI
Custom base   →  vLLM
```

### Financial Safety Layer

`FinancialOllamaProvider` adds safeguards to every response:
- **Calculation verification** — validates numerical outputs
- **Disclaimer injection** — automatic investment risk warnings
- **Fact-checking enrichment** — financial accuracy guidelines in system prompt
- **Conservative defaults** — emergency fund always directed to debt instruments

### Embedding Model

| Model | Library | Dimensions | Purpose |
|-------|---------|-----------|---------|
| `all-MiniLM-L6-v2` | SentenceTransformers | 384 | PostgreSQL hybrid vector search |

---

## Agent Tools & Capabilities

### Tool Registry

| # | Tool | File | Description |
|---|------|------|-------------|
| 1 | `finance_tool` | `tools/finance.py` | Stock prices, MF NAV/returns, recommendations, fund comparison |
| 2 | `expense_tracker` | `tools/expense.py` | Add expenses, monthly summaries, category filters |
| 3 | `ticket_manager` | `tools/ticket.py` | Create, update, list support tickets |
| 4 | `rag_knowledge` | `tools/rag.py` | PostgreSQL knowledge store with semantic search |
| 5 | `web_search` | `tools/web.py` | Brave Search — titles, URLs, snippets |
| 6 | `web_fetch` | `tools/web.py` | Fetch URL content, HTML → Markdown |
| 7 | `message` | `tools/message.py` | Send messages to specific channels |
| 8 | `file tools` | `tools/filesystem.py` | Read, write, list, search workspace files |
| 9 | `shell` | `tools/shell.py` | Execute system commands |
| 10 | `spawn` | `tools/spawn.py` | Delegate tasks to sub-agents |

### Finance Tool Actions

| Action | Params | Description |
|--------|--------|-------------|
| `get_stock_price` | `symbol` | Live price (e.g., `AAPL`, `TATAMOTORS.NS`) |
| `get_fund_info` | `symbol` | NAV, category, YTD return |
| `market_news` | `symbol` | Latest 3 news articles |
| `search_funds` | `query` | Search Indian MFs by name/keyword |
| `get_fund_nav` | `scheme_code` | NAV, fund house, 1Y/3Y returns |
| `recommend_funds` | `risk_profile`, `amount` | Risk-profiled MF picks with live NAV |
| `get_fund_recommendation` | `risk_profile`, `amount`, `goal` | 3-step personalized advisory |
| `compare_funds` | `symbols[]` (2–3) | Side-by-side comparison |

### Expense Tracker Actions

| Action | Params | Description |
|--------|--------|-------------|
| `add_expense` | `user_id`, `amount`, `category`, `description` | Log an expense |
| `get_expenses` | `user_id`, `month?`, `category?` | Query with optional filters |
| `monthly_summary` | `user_id`, `month?` | Category-wise breakdown in INR |

### RAG Knowledge Actions

| Action | Params | Description |
|--------|--------|-------------|
| `add` | `content`/`file_path`, `context`, `category` | Store text or PDF |
| `search` | `query`, `context` | Semantic search — top 3 passages |
| `switch_context` | `context` | Switch active context |
| `list_contexts` | — | List all knowledge contexts |

---

## Database Schema

**Engine:** PostgreSQL 15 · **ORM:** SQLAlchemy 2.0 · **Pool:** QueuePool

### Entity Relationship

```
                    ┌──────────────┐
                    │    users     │
                    │  user_id PK  │
                    └──────┬───────┘
                           │
       ┌──────────┬─────────┼──────────┬──────────┐
       ▼          ▼         ▼          ▼          ▼
verifications  user_     conversa-  recomm-   tickets
               prefs     tions      endations
                   ├── sessions
                   └── user_workspaces
```

### Tables Overview

| Table | Key | Purpose |
|-------|-----|---------|
| `users` | `user_id` VARCHAR | Profiles, risk profile, KYC status |
| `verifications` | SERIAL | PAN / Aadhaar / Bank KYC records |
| `user_preferences` | SERIAL | Risk tolerance, investment horizon, budgets |
| `conversations` | SERIAL | Full chat message history |
| `recommendations` | SERIAL | Fund picks + acceptance tracking |
| `sessions` | `session_key` UNIQUE | DB-backed LLM context (JSON messages) |
| `user_workspaces` | SERIAL | Per-user filesystem (default 1 GB quota) |
| `tickets` | SERIAL | Support tickets: priority, status, lifecycle |

**Session key format:** `"whatsapp:919876543210@s.whatsapp.net"`

Sessions auto-cleaned after **7 days of inactivity**.

---

## External APIs

| API | Auth | Provides | Used By |
|-----|------|----------|---------|
| **yFinance** | None (public) | Stock prices, fund NAV/YTD, market news, historical data | `finance_tool` |
| **MFAPI India** (`mfapi.in`) | None (public) | MF search, scheme details, NAV, 1Y/3Y returns | `finance_tool` |
| **Brave Search** | `BRAVE_API_KEY` | Titles, URLs, snippets (max 10 results) | `web_search` |
| **WhatsApp (Baileys)** | QR code scan | Send/receive messages, auto-reconnect | `whatsapp` channel |

---

## Tech Stack

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| Runtime | Python | 3.11+ | Core application |
| Runtime | Node.js | 18+ | WhatsApp bridge |
| LLM Gateway | LiteLLM | ≥1.0 | Unified multi-provider API |
| Database | PostgreSQL | 15 Alpine | Relational + vector store |
| ORM | SQLAlchemy | ≥2.0 | DB mapping + QueuePool |
| Validation | Pydantic | ≥2.0 | Config + env injection |
| HTTP Client | httpx | ≥0.25 | Async API calls |
| Finance Data | yfinance | Latest | Stock/fund market data |
| WhatsApp | @whiskeysockets/baileys | Latest | WhatsApp Web protocol |
| WebSocket | websockets | ≥12.0 | Bridge ↔ Python |
| Embeddings | SentenceTransformers | Latest | RAG vector search |
| Logging | Loguru | ≥0.7 | Structured logging |
| CLI | Typer + Rich | Latest | Terminal interface |
| Scheduler | croniter | ≥2.0 | Cron tasks |
| HTML Parser | readability-lxml | ≥0.8 | URL content extraction |
| Container | Docker + Compose | 3.8 | Deployment |

---

## Getting Started

### Prerequisites

- Python 3.11+, Node.js 18+, Docker & Docker Compose
- At least one LLM API key (Gemini or Groq recommended)

### 1. Clone

```bash
git clone https://github.com/your-username/zuberabot.git
cd zuberabot
```

### 2. Configure `.env`

```env
# LLM (at least one required)
GEMINI_API_KEY=your_key
GROQ_API_KEY=your_key
ANTHROPIC_API_KEY=your_key       # optional
OPENROUTER_API_KEY=your_key      # optional
OPENAI_API_KEY=your_key          # optional

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/zubera_bot

# Optional
BRAVE_API_KEY=your_key
OLLAMA_API_BASE=http://localhost:11434
PYTHONIOENCODING=utf-8
```

### 3. Install dependencies

```bash
# Python
pip install -e .

# Node.js bridge
cd bridge && npm install && cd ..
```

### 4. Start the WhatsApp bridge

```bash
cd bridge && npm start
# Scan the QR code with your WhatsApp mobile app
```

### 5. Start Zubera Bot

```bash
nanobot gateway    # WhatsApp mode
# or
nanobot chat       # CLI terminal mode
```

---

## Deployment

### Docker Compose

```bash
docker-compose up -d
```

Starts:
- `zuberabot` — Python app on port `18790`
- `zuberabot-db` — PostgreSQL 15 Alpine on port `5432` (persistent volume)

### Deployment Modes

| Mode | Command | Description |
|------|---------|-------------|
| **CLI** | `nanobot chat` | Interactive terminal chat |
| **Gateway** | `nanobot gateway` | WebSocket server for WhatsApp bridge |
| **Docker** | `docker-compose up -d` | Full production stack |
| **Local Dev** | `./start_bot.ps1` | PowerShell with env setup |
| **Gemini Mode** | `./start_gemini_bot.ps1` | Pre-configured for Gemini |

---

## Security Model

- **Secrets:** `.env` file gitignored; Pydantic-validated with `NANOBOT_` prefix
- **User isolation:** Per-user workspaces, session keys, memory files — no cross-user data access
- **DB security:** Password-masked log URLs, QueuePool listeners, 7-day session auto-cleanup
- **Financial safety:** Disclaimers on all investment advice, calculation verification, conservative emergency fund defaults

---

## Project Structure

```
zuberabot/
├── .env                        # Secrets (gitignored)
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
│
├── zuberabot/                  # Python Core
│   ├── agent/
│   │   ├── loop.py             # AgentLoop
│   │   ├── context.py          # Prompt assembly
│   │   ├── user_context.py     # Per-user context
│   │   ├── user_memory.py      # Memory system
│   │   └── tools/
│   │       ├── finance.py      # Stocks + MF (yFinance + MFAPI)
│   │       ├── expense.py      # Expense tracking
│   │       ├── ticket.py       # Support tickets
│   │       ├── rag.py          # RAG knowledge base
│   │       ├── web.py          # Web search + fetch
│   │       ├── filesystem.py   # File tools
│   │       ├── shell.py        # System commands
│   │       └── spawn.py        # Sub-agent spawning
│   ├── channels/
│   │   └── whatsapp.py         # WhatsApp handler
│   ├── database/
│   │   ├── models.py           # SQLAlchemy ORM
│   │   └── postgres.py         # DatabaseManager
│   └── providers/
│       ├── litellm_provider.py # LiteLLM gateway
│       └── ollama.py           # Ollama + safety layer
│
├── bridge/                     # Node.js WhatsApp Bridge
│   └── src/
│       ├── index.ts
│       ├── server.ts           # WebSocket server
│       └── whatsapp.ts         # Baileys client
│
└── tests/
    ├── test_database.py
    ├── test_mf_integration.py
    ├── test_multi_user.py
    └── test_conversational_recommendations.py
```

---

## License

© 2026 Zubera Technologies — All rights reserved.

---

*Built with ❤️ using Python · Node.js · PostgreSQL · LiteLLM · WhatsApp Baileys · Google Gemini*
