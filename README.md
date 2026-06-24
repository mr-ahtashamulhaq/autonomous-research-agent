<div align="center">

# ▲ Autonomous Research Agent

### *Enter a topic. Get a fully researched, fact-checked report — automatically.*

[![🚀 Live Demo](https://img.shields.io/badge/🚀_Live_Demo-autonomous--research--agent.vercel.app-cc785c?style=for-the-badge)](https://autonomous-research-agent-beige.vercel.app)

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2-FF6B6B?style=flat-square)](https://langchain-ai.github.io/langgraph/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Groq](https://img.shields.io/badge/Groq-llama--3.3--70b-F55036?style=flat-square)](https://groq.com)
[![Tavily](https://img.shields.io/badge/Tavily-Search%20%2B%20Extract-4A90E2?style=flat-square)](https://tavily.com)
[![Vercel](https://img.shields.io/badge/Frontend-Vercel-000000?style=flat-square&logo=vercel)](https://autonomous-research-agent-beige.vercel.app)

</div>


---

## 🧠 The Problem This Solves

**Research is broken.** Manually researching any topic means:

- 🔍 Opening 15+ browser tabs and reading everything yourself
- 📋 Manually copying relevant snippets into a document
- 🤔 Trying to cross-reference sources and spot contradictions
- ✍️ Writing a coherent synthesis from scattered notes
- ✅ Fact-checking your own work (which no one actually does)

This entire workflow - which takes a human **2–4 hours** - takes this agent **under 60 seconds**.

---

## 💡 The Solution

An **autonomous multi-node research pipeline** built with [LangGraph](https://langchain-ai.github.io/langgraph/) that mimics how a professional research analyst actually works:

```
You type a topic
       │
       ▼
 ┌─────────────────────────────────────────────────────────────┐
 │               LangGraph Agent Pipeline                      │
 │                                                             │
 │  ┌────────┐  ┌────────┐  ┌──────┐  ┌───────────┐  ┌──────┐│
 │  │  Plan  │→ │ Search │→ │ Read │→ │ Synthesise│→ │Review││
 │  └────────┘  └────────┘  └──────┘  └───────────┘  └──────┘│
 │  5 queries  25 results  8 articles  Draft report   Final   │
 │  generated   collected   extracted   structured  fact-check │
 └─────────────────────────────────────────────────────────────┘
       │
       ▼
 Structured Markdown report with numbered citations
 delivered to your browser in real-time via SSE streaming
```

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        Frontend                              │
│           HTML + CSS + Vanilla JS (Claude.com theme)         │
│                                                              │
│  [Topic Input] → [Live Progress Bar] → [Rendered Report]     │
└─────────────────────┬────────────────────────────────────────┘
                      │ POST /research
                      │ ← SSE stream (started/progress/done)
┌─────────────────────▼────────────────────────────────────────┐
│                    FastAPI Backend                            │
│               api.py  (Uvicorn ASGI server)                  │
│                                                              │
│  POST /research  →  StreamingResponse (text/event-stream)    │
│  GET  /health    →  { "status": "ok" }                       │
│  GET  /docs      →  Swagger UI (auto-generated)              │
└─────────────────────┬────────────────────────────────────────┘
                      │ agent.stream()
┌─────────────────────▼────────────────────────────────────────┐
│                  LangGraph Agent (agent.py)                   │
│                                                              │
│  ResearchState (shared dict across all 5 nodes)              │
│                                                              │
│  plan_node → search_node → read_node → synthesise_node       │
│                                              → review_node   │
└──────────┬─────────────────┬────────────────────────────────┘
           │                 │
  ┌────────▼──────┐  ┌───────▼────────┐
  │  Groq Cloud   │  │ Tavily Search  │
  │ llama-3.3-70b │  │  + Extract API │
  └───────────────┘  └────────────────┘
```

---

## ⚙️ Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Agent Orchestration** | [LangGraph](https://langchain-ai.github.io/langgraph/) | Graph-based stateful agent framework - each node reads/writes a shared state dict |
| **LLM Inference** | [Groq](https://groq.com) - `llama-3.3-70b-versatile` | Fastest inference on the market (~500 tok/s) - Llama 3.3 70B rivals GPT-4 on reasoning |
| **Web Search** | [Tavily Search API](https://tavily.com) | Purpose-built for LLM agents - returns clean, structured results without scraping noise |
| **Content Extraction** | [Tavily Extract API](https://tavily.com) | Extracts clean article text from any URL - no Playwright/Selenium needed |
| **Backend API** | [FastAPI](https://fastapi.tiangolo.com) | Async, typed, auto-docs at `/docs`. `StreamingResponse` makes SSE effortless |
| **Streaming** | Server-Sent Events (SSE) | Real-time progress updates - shows users exactly which node is running |
| **Frontend** | Vanilla HTML/CSS/JS | Zero dependencies, deploys to Vercel as a static site in one click |
| **Frontend Design** | Claude.com / Anthropic design system | Warm cream canvas, coral CTAs, dark navy code cards - premium editorial look |

---

## 🔬 Pipeline Deep Dive

### Node 1 - Plan 🗺️
**Input:** raw topic string  
**Output:** 5 targeted search queries

The planning prompt instructs the LLM to act as a **senior research analyst** and decompose the topic into 5 queries, each targeting a different angle:
- 📰 Recent news and developments
- 🎓 Academic / expert analysis  
- 📊 Statistics and quantitative data
- 🏭 Real-world applications
- ⚠️ Challenges, criticism, and limitations

> **Why 5 angles?** A single broad query returns generic results. Five focused queries surface authoritative, varied sources - the same way a real researcher would approach a literature review.

---

### Node 2 - Search 🔍
**Input:** 5 search queries  
**Output:** up to 25 candidate results (title + URL + snippet)

Runs every query through the Tavily Search API with `max_results=5`. Tavily is purpose-built for LLM agent pipelines - it returns clean structured results with relevance scores, filtering out low-quality pages automatically.

> **Original project used** `max_results=2` across 3 queries = 6 results. **This version** uses `max_results=5` across 5 queries = up to **25 results** - dramatically better source coverage.

---

### Node 3 - Read 📖
**Input:** up to 25 candidate URLs  
**Output:** full article text from the top 8 sources

Deduplicates URLs, takes the top 8, and calls Tavily's Extract API to pull **full article text** from each page. Tavily Extract handles JavaScript-rendered pages, paywalls (where accessible), and ad-heavy pages - returning only the clean prose content.

Each article is truncated to **3,000 characters** to keep the combined context within the LLM's effective reasoning window.

> **Original project used** 4 URLs × 1,500 chars = ~6,000 chars of context. **This version** uses 8 URLs × 3,000 chars = up to **24,000 chars** - 4× more source material.

---

### Node 4 - Synthesise ✍️
**Input:** all extracted text + topic  
**Output:** structured 800–1,200 word draft report

The LLM acts as an **expert research analyst and science communicator**. The prompt enforces a specific Markdown structure:

```markdown
## Executive Summary      ← 2–3 sentence TL;DR
## Key Findings           ← 4–6 findings with ### subheadings
## Analysis & Implications ← patterns and trends
## Conclusion             ← forward-looking synthesis
```

Inline citations like `[Source: nature.com]` are added during writing. The prompt explicitly forbids the LLM from using outside knowledge - **only what the sources say**.

> **Original prompt:** "Write a short report... intro, 3 key findings, conclusion" (1 line)  
> **This prompt:** Role + word target + structured sections + citation rules + tone guidance (~200 words)

---

### Node 5 - Review ✅
**Input:** draft report + source material  
**Output:** final fact-checked report with numbered citations

A **second, independent LLM call** acts as a rigorous fact-checker and editor:
1. Cross-references every claim against the source material
2. Removes or softens unsupported claims
3. Upgrades inline citations to `[1]`, `[2]` numbered format
4. Appends a formatted `## Sources` reference list
5. Adds a `## Research Confidence` assessment

> **Why a separate review node?** LLMs can hallucinate even when told to stay grounded. Running a dedicated critic pass - separate from the writer - dramatically reduces unsupported claims. This mirrors professional editorial workflows.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Groq API key (free): https://console.groq.com
- Tavily API key (free tier: 1,000 searches/month): https://app.tavily.com

### 1. Clone & Install

```bash
git clone https://github.com/mr-ahtashamulhaq/autonomous-research-agent
cd autonomous-research-agent

python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux

pip install -r requirements.txt
```

### 2. Configure API Keys

```bash
copy .env.example .env
# Edit .env and add your real keys
```

`.env` file:
```env
GROQ_API_KEY=gsk_...
TAVILY_API_KEY=tvly-...
```

### 3. Start the Backend

```bash
python -m uvicorn api:app --reload --port 5000
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:5000
INFO:     Application startup complete.
```

🎯 **Bonus:** Visit `http://localhost:5000/docs` for the interactive Swagger UI - great for demos!

### 4. Open the Frontend

```bash
# Option A - just open the file
start frontend/index.html

# Option B - serve locally (avoids CORS edge cases)
cd frontend
python -m http.server 3000
# then open http://localhost:3000
```

### 5. CLI Usage (no frontend needed)

```bash
python agent.py --topic "Impact of AI on healthcare in 2024"
```

---

## 📁 Project Structure

```
autonomous-research-agent/
│
├── 🤖 agent.py              - LangGraph 5-node pipeline (core research logic)
├── ⚡ api.py                - FastAPI server with SSE streaming
├── 📦 requirements.txt      - Python dependencies
├── 🔑 .env.example          - API key template (copy → .env)
├── 🙈 .gitignore            - Keeps .env and caches out of git
├── 📖 README.md             - This file
│
└── 🌐 frontend/
    ├── index.html           - Single-page UI with semantic HTML + SEO tags
    ├── style.css            - Full Anthropic/Claude design system (from DESIGN.md)
    ├── app.js               - SSE client, live progress, Markdown rendering
    └── vercel.json          - Vercel static deployment config
```

---

## 🛠️ Skills Demonstrated

This project demonstrates proficiency in:

- **Agent Orchestration** - LangGraph stateful graph with typed state (`TypedDict`), 5 nodes wired with explicit edges
- **LLM Prompt Engineering** - role-based prompts, structured output formatting, chain-of-verification patterns
- **Async Python** - FastAPI `StreamingResponse`, `asyncio.Queue` to bridge sync LangGraph with async SSE
- **API Design** - RESTful endpoint, Pydantic request validation, CORS, SSE wire protocol
- **Web Fundamentals** - semantic HTML, CSS design systems, vanilla JS fetch + ReadableStream, Markdown rendering
- **Production Practices** - environment variable management, structured logging, `.gitignore`, deployment configs