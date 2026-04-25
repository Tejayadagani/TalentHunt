# TalentRadar System Architecture

This document provides a high-level overview of the TalentRadar system architecture, detailing the flow of data from the user interface through the multi-agent AI pipeline and back.

## High-Level Architecture Diagram

```mermaid
flowchart TD
    %% Define Theme Colors for perfect Dark/Light Mode Contrast
    classDef user fill:#2D7D3E,stroke:#1F5A2B,stroke-width:2px,color:#fff
    classDef frontend fill:#1A1A1A,stroke:#4A4A4A,stroke-width:2px,color:#fff
    classDef backend fill:#111827,stroke:#374151,stroke-width:2px,color:#fff
    classDef agent fill:#D4AF37,stroke:#A68312,stroke-width:2px,color:#000
    classDef db fill:#0A0A0A,stroke:#D4AF37,stroke-width:2px,color:#fff
    classDef external fill:#1F5A2B,stroke:#2D7D3E,stroke-width:2px,color:#fff

    User((User)):::user

    subgraph Client [Frontend Layer - Next.js]
        Input[Raw Job Description Input]:::frontend
        Dashboard[Live Ranking Dashboard]:::frontend
    end

    subgraph Server [Backend Layer - FastAPI]
        Endpoint[POST /api/scout/stream]:::backend
        SSE[SSE Stream Generator]:::backend
    end

    subgraph Pipeline [Multi-Agent Pipeline]
        A1[Agent 1: Parse & Structure JD]:::agent
        A2[Agent 2: Embed & Semantic Match]:::agent
        A3[Agents 3 & 4: Simulate Interview]:::agent
        A5[Agent 5: Evaluate & Score]:::agent
    end

    subgraph Data [Data & AI Services]
        Chroma[(ChromaDB)]:::db
        Groq[Groq API: Llama 3]:::external
        Gemini[Gemini API: Auto-Fallback]:::external
    end

    %% Step-by-Step Flow
    User -->|1. Pastes Text| Input
    Input -->|2. Submits| Endpoint
    Endpoint -->|3. Triggers| A1

    A1 <-->|JSON Structuring| Groq
    A1 -->|Structured JD| A2

    A2 <-->|Top 5 Query| Chroma
    A2 -->|Candidates| A3

    A3 <-->|Parallel 6-Turn Chat| Groq
    A3 -->|Transcripts| A5

    A5 <-->|Interest Scoring| Groq
    A5 -.->|If 429 Rate Limit| Gemini
    
    A5 -->|Yield JSON Chunk| SSE
    SSE -->|Server-Sent Events| Dashboard
    Dashboard -->|Live Re-sorts| User
```

## System Components

### 1. Frontend (Next.js)
* **Glassmorphic UI**: Uses Tailwind CSS and Framer motion to create a highly responsive, premium dark-mode interface.
* **Live Sorting**: Implements an SSE (Server-Sent Events) decoder that intercepts chunked data from the backend and performs `Array.sort()` in real-time, allowing users to watch the candidate ranks shift dynamically.

### 2. Backend (FastAPI)
* **Asynchronous Execution**: The entire pipeline is built on Python's `asyncio` to allow parallel I/O bound LLM calls.
* **Concurrency Control**: Utilizes `asyncio.Semaphore(2)` to strictly limit simultaneous LLM multi-turn conversations to 2, heavily reducing the likelihood of rate limits.
* **Live Streaming**: Exposes `/api/scout/stream` which uses a `StreamingResponse` generator to yield candidate JSON chunks directly to the client as soon as their respective evaluation finishes.

### 3. Multi-Agent System
* **Agent 1 (Parser)**: Standardizes raw user input into structured JSON.
* **Agent 2 (Scout)**: Translates the structured JD into an embedding vector and queries ChromaDB.
* **Agent 3 & 4 (Simulated Interview)**: A dynamic ping-pong loop where Agent 3 plays the recruiter and Agent 4 acts as the specific candidate based on their historical data.
* **Agent 5 (Scorer)**: Analyzes the resulting transcript, outputting an Interest Score and detailed rationale. Includes a "JSON Healer" to gracefully repair truncated LLM responses.

### 4. LLM Abstraction Layer (`llm_client.py`)
* **Primary**: Groq (`llama-3.3-70b-versatile`) for extreme speed.
* **Auto-Fallback**: If Groq returns a `429 Rate Limit Exceeded` error (due to its strict daily limits), the client intercepts the exception and seamlessly re-routes the exact same request to Google Gemini (`gemini-1.5-flash`), guaranteeing execution without interrupting the user experience.
