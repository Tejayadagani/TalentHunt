# 🌐 Full Website & Sandbox Workflow

This interactive Recruiter Dashboard operates completely separate from the offline hackathon ranking script. It demonstrates real-time interaction between the Next.js frontend, FastAPI backend, and the Multi-Agent interview system.

```mermaid
graph TD
    %% User Interaction
    User((Recruiter)) -->|Visits Dashboard| Web[Next.js Frontend UI]
    Web -->|Views Ranked List| Table[Top-100 Candidates Table]
    Table -->|Selects Candidate Profile| Profile[Candidate Detail View]
    Profile -->|Clicks 'Simulate Interview'| API[FastAPI Backend]

    %% Backend Services
    subgraph TalentRadar Backend
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
    JSON -->|Stream Results via WebSocket/REST| Web
    Web -->|Render Live Chat UI| Modal[Interview Modal View]
    Modal -->|Display Final Rating| User

    %% Styling
    style User fill:#fff,stroke:#333,stroke-width:2px
    style Web fill:#e1f5fe,stroke:#0288d1,stroke-width:2px,color:#000
    style API fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:#000
    style Orchestrator fill:#fff3e0,stroke:#e65100,stroke-width:2px,color:#000
    style DB fill:#eceff1,stroke:#607d8b,stroke-width:2px,color:#000
```
