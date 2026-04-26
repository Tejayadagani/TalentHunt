# 🛰️ TalentRadar: Autonomous AI Talent Scouting Agent

TalentRadar is a premium, AI-driven recruitment engine designed to transform raw job descriptions into highly qualified, ranked candidate shortlists. It goes beyond keyword matching by simulating deep-dive screening conversations with every candidate in your pool.

---

## 🏗️ System Architecture

Our architecture is designed for high-concurrency and real-time feedback using a multi-agent orchestration pattern.

```mermaid
flowchart LR
    classDef userNode fill:#2D7D3E,stroke:#1F5A2B,stroke-width:2px,color:#fff,font-weight:bold
    classDef feNode fill:#0f172a,stroke:#334155,stroke-width:2px,color:#e2e8f0
    classDef beNode fill:#1e1b4b,stroke:#4338ca,stroke-width:2px,color:#e0e7ff
    classDef agentNode fill:#78350f,stroke:#d97706,stroke-width:2px,color:#fef3c7,font-weight:bold
    classDef dbNode fill:#064e3b,stroke:#10b981,stroke-width:2px,color:#d1fae5
    classDef llmNode fill:#312e81,stroke:#818cf8,stroke-width:2px,color:#e0e7ff
    classDef fallbackNode fill:#7f1d1d,stroke:#f87171,stroke-width:2px,color:#fee2e2

    U((👤 User)):::userNode

    subgraph FE ["🖥️ Frontend — Next.js"]
        direction TB
        JD["📝 JD Input Form"]:::feNode
        DASH["📊 Live Dashboard"]:::feNode
    end

    subgraph BE ["⚡ Backend — FastAPI"]
        direction TB
        API["/api/scout/stream"]:::beNode
        SSE["SSE Stream"]:::beNode
    end

    subgraph AGENTS ["🤖 Multi-Agent Pipeline"]
        direction TB
        A1["🔍 Agent 1\nJD Parser"]:::agentNode
        A2["🎯 Agent 2\nTalent Scout"]:::agentNode
        A34["💬 Agents 3+4\nRecruiter ↔ Candidate"]:::agentNode
        A5["⭐ Agent 5\nInterest Scorer"]:::agentNode
        A1 --> A2 --> A34 --> A5
    end

    subgraph LLM ["🧠 LLM Engine — Per-Agent Routing"]
        direction TB
        GROQ["⚡ Groq\nLlama 3.3 70B · 3.1 8B"]:::llmNode
        OR["🔄 OpenRouter Fallback\nHermes 405B · Llama 3.3\nMistral 7B · Gemma 27B\nLlama 3.2 3B"]:::fallbackNode
        GROQ -. "429 → rotate" .-> OR
        OR -. "all exhausted → loop back" .-> GROQ
    end

    DB[("🗄️ ChromaDB\nall-MiniLM-L6-v2")]:::dbNode

    U -->|"Paste JD"| JD
    JD -->|"POST"| API
    API --> A1
    A2 <-->|"Semantic Search"| DB
    A1 & A2 & A34 & A5 <-->|"call_llm()"| GROQ
    A5 -->|"yield result"| SSE
    SSE -->|"Server-Sent Events"| DASH
    DASH -->|"Live ranked cards"| U
```

---

## 🤖 The Multi-Agent Pipeline

TalentRadar utilizes a **5-Agent Pipeline** to evaluate candidates with extreme precision:

1. **Agent 1: The JD Parser**: Standardizes messy, raw text into a structured JSON schema of skills, seniority, and core requirements.
2. **Agent 2: The Talent Scout**: Performs high-speed semantic search over the **ChromaDB** vector store to find the top 5 most relevant profiles.
3. **Agent 3 & 4: The Interviewers**: Two agents engage in a 6-turn simulated interview. One plays the hiring manager, the other plays the candidate based on their actual resume data.
4. **Agent 5: The Scorer**: Evaluates the resulting transcript, awarding an **Interest Score** based on technical depth, cultural alignment, and proactive questioning.

---

## ✨ Key Features

- **Live SSE Streaming**: Candidates appear and re-sort themselves on your dashboard in real-time as their "interviews" finish.
- **LLM Auto-Fallback**: If the primary engine (Groq) hits a rate limit, the system automatically hot-swaps to OpenRouter's free tier to ensure zero downtime.
- **JSON Healing**: Advanced error handling that automatically repairs truncated LLM responses to prevent pipeline crashes.
- **Premium UI**: A high-contrast, glassmorphic dark-mode dashboard built with Framer Motion and Tailwind CSS.

---

## ⚙️ Resilience & Rate Limits (Multi-Model Fallback)

Because TalentRadar's 5-Agent Pipeline evaluates candidates via highly conversational, multi-turn interviews, it consumes tokens very rapidly. A standard 4-candidate pipeline run can consume up to 30,000 tokens within 30 seconds.

**The Problem:** Free-tier API keys (like Groq) have strict limitations on both Requests-Per-Minute (RPM) and Daily Tokens (TPM). The massive burst of parallel agent calls easily exhausts these free-tier limits, resulting in `429 Too Many Requests` errors.

**The Solution:**
To prevent the application from crashing, we implemented an **Infinite State Carousel Fallback** architecture. 
As shown in the `backend/.env.example`, we utilize **OpenRouter** as a secondary safety net:

```env
# Get your key at: https://console.groq.com
GROQ_API_KEY=your_groq_api_key_here

# Fallback api key for rate limits
OPENROUTER_API_KEY=your_open_router_api_key
```

**How the Fallback Logic Works:**
1. **Primary Engine:** All agents start by querying the lightning-fast Groq endpoints.
2. **Exhaustion:** If Groq returns a `429 Rate Limit` error, the backend cleanly catches it and hot-swaps the agent's internal state to point to OpenRouter.
3. **Model Rotation:** OpenRouter provides access to a massive list of free-tier models (Llama 3.3, Hermes 405B, Mistral, Gemma). The pipeline will automatically rotate down this list if specific OpenRouter models are currently unavailable (e.g. returning `404 Not Found`).
4. **Infinite Carousel:** If the pipeline is incredibly unlucky and exhausts *all* 7 fallback models across both platforms, it gracefully loops the state back to Groq and applies a capped exponential backoff. This ensures the agents never get permanently stuck on dead models, allowing them to instantly resume evaluation once the API limits reset.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.12, FastAPI, Asyncio
- **Vector DB**: ChromaDB (all-MiniLM-L6-v2)
- **Frontend**: Next.js 14, Tailwind CSS, Lucide React
- **LLM Engines**: Groq (Llama-3.3-70b + 3.1-8b) + OpenRouter (Fallback)

---

## 🚀 Quick Start

### 1. Backend Setup
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Add your API keys (GROQ_API_KEY, OPENROUTER_API_KEY)

# Seed the database
python scripts/embed_candidates.py

# Start API
uvicorn app.main:app --reload
```

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

The application will be available at `http://localhost:3000`.
