# 🌐 Full Website & Sandbox Workflow

This interactive Recruiter Dashboard operates completely separate from the offline hackathon ranking script. It demonstrates real-time interaction between the Next.js frontend, FastAPI backend, and the Multi-Agent interview system.
## System Architecture

```mermaid
graph TD
    %% User Interaction
    User((Recruiter)) -->|Visits Dashboard| Web[Next.js Frontend UI]
    Web -->|Views Ranked List| Table[Top-100 Candidates Table]
    Table -->|Selects Candidate Profile| Profile[Candidate Detail View]
    Profile -->|Clicks Simulate Interview| API[FastAPI Backend]

    %% Backend Services
    subgraph SkillSync AI Backend
        API -->|Fetch Profile| DB[(ChromaDB / JSON Cache)]
        API -->|Initiate Chat| Orchestrator[Multi-Agent Orchestrator]

        subgraph Agent Simulation Loop
            Orchestrator --> HM[Hiring Manager Agent]
            Orchestrator --> CP[Candidate Persona Agent]

            HM <-->|Live Simulated QA Session| CP
        end

        Orchestrator -->|Pass Transcript| Scorer[Interest Scorer Agent]
        Scorer -->|Extract Sentiment & Reasoning| JSON[Final Evaluation JSON]
    end

    %% Data Flow Back to User
    JSON -->|Stream Results via WebSocket / REST| Web
    Web -->|Render Live Chat UI| Modal[Interview Modal View]
    Modal -->|Display Final Rating| User

    %% Styling
    style User fill:#ffffff,stroke:#333333,stroke-width:2px
    style Web fill:#e1f5fe,stroke:#0288d1,stroke-width:2px,color:#000000
    style API fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:#000000
    style Orchestrator fill:#fff3e0,stroke:#e65100,stroke-width:2px,color:#000000
    style DB fill:#eceff1,stroke:#607d8b,stroke-width:2px,color:#000000
    style HM fill:#fce4ec,stroke:#ad1457,stroke-width:2px,color:#000000
    style CP fill:#f3e5f5,stroke:#6a1b9a,stroke-width:2px,color:#000000
    style Scorer fill:#fff8e1,stroke:#ff8f00,stroke-width:2px,color:#000000
    style JSON fill:#e8eaf6,stroke:#3949ab,stroke-width:2px,color:#000000
    style Modal fill:#f1f8e9,stroke:#558b2f,stroke-width:2px,color:#000000
```
