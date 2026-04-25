# TalentRadar System Architecture

This document provides a high-level overview of the TalentRadar system architecture, detailing the flow of data from the user interface through the multi-agent AI pipeline and back.

## High-Level Architecture Diagram

```mermaid
flowchart TD
    %% Define Styles
    classDef frontend fill:#1A3A22,stroke:#4A9D5F,stroke-width:2px,color:#fff;
    classDef backend fill:#1F5A2B,stroke:#2D7D3E,stroke-width:2px,color:#fff;
    classDef agent fill:#D4AF37,stroke:#A68312,stroke-width:2px,color:#000;
    classDef database fill:#0A0A0A,stroke:#D4AF37,stroke-width:2px,color:#fff;
    classDef external fill:#2D7D3E,stroke:#4A9D5F,stroke-width:2px,color:#fff;

    %% Client Layer
    subgraph Client [Frontend Layer - Next.js]
        UI[User Interface / React]:::frontend
        SSE[SSE Stream Reader]:::frontend
    end

    %% API Layer
    subgraph API [Backend Layer - FastAPI]
        Router[/api/scout/stream]:::backend
        Pipeline[run_pipeline_stream \n Async Generator]:::backend
        Semaphore[Asyncio Semaphore\n Max Concurrency: 2]:::backend
    end

    %% Agent Pipeline
    subgraph Agents [Multi-Agent Pipeline]
        A1[Agent 1: JD Parser]:::agent
        A2[Agent 2: Talent Scout]:::agent
        
        subgraph Interview [Parallel Interview Simulation]
            A3[Agent 3: Interviewer]:::agent
            A4[Agent 4: Candidate]:::agent
        end
        
        A5[Agent 5: Scorer / Evaluator]:::agent
    end

    %% Data Layer
    subgraph Data [Data Layer]
        Chroma[(ChromaDB Vector Store)]:::database
        Embed[ONNX MiniLM-L6-v2]:::database
    end

    %% External LLMs
    subgraph LLM [LLM Providers]
        Groq[Groq API \n Llama-3.3-70b]:::external
        Gemini[Google Gemini API \n 1.5 Flash - Fallback]:::external
    end

    %% ── Flow Connections ──
    UI -- "Raw JD text" --> Router
    Router --> Pipeline
    
    %% Step 1
    Pipeline -- "1. Parse JD" --> A1
    A1 -- "JSON Schema" --> Pipeline
    A1 <..> LLM
    
    %% Step 2
    Pipeline -- "2. Find Candidates" --> A2
    A2 --> Embed
    Embed --> Chroma
    Chroma -- "Top K Candidates" --> A2
    A2 -- "Match Scores" --> Pipeline
    
    %% Step 3
    Pipeline -- "3. Dispatch (Max 2)" --> Semaphore
    Semaphore --> Interview
    Interview <..> LLM
    Interview -- "6-Turn Transcript" --> A5
    
    %% Step 4
    A5 <..> LLM
    A5 -- "Interest Score & JSON Healing" --> Semaphore
    
    %% Streaming Return
    Semaphore -- "Candidate Result Chunk" --> Pipeline
    Pipeline -- "Yield data: {...}" --> Router
    Router -- "Server-Sent Events (Live Sort)" --> SSE
    SSE --> UI
    
    %% Fallback Logic
    Groq -. "429 Rate Limit" .-> Gemini
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
