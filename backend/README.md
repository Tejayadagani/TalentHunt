# TalentRadar — Backend

## Setup

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment variables
cp .env.example .env
# Edit .env and add your OPENROUTER_API_KEY (and GROQ_API_KEY)

# 4. Embed candidates (run once, after Step 1.2 + 1.3 are complete)
python scripts/embed_candidates.py

# 5. Start the API server
uvicorn app.main:app --reload
```

API docs available at: http://localhost:8000/docs

## Architecture Notes

**Responsibility Split (Agent 2):**
In the offline pipeline, `03_pre_score.py` handles the heavy semantic retrieval and full multi-signal math scoring across candidates. Despite its name, `05_agent2_scout.py` primarily serves as a metadata mapper and filter that prepares the previously scored results for the UI and the interview simulation stages. The true mathematical "Scouting" and ranking happens in `03_pre_score.py`.
