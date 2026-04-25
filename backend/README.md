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
