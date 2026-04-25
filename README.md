# TalentRadar — AI-Powered Talent Scouting Agent
# Built for Catalyst Hackathon · Free-tier stack

## Quick Start

### Backend
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your GEMINI_API_KEY
python scripts/embed_candidates.py
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Architecture
5-agent pipeline: JD Parser → Talent Scout → Conversation Simulator (Recruiter ↔ Candidate) → Scorer/Explainer → Ranked Shortlist

## Tech Stack
- **Backend:** Python · FastAPI · ChromaDB · sentence-transformers · Gemini 1.5 Flash
- **Frontend:** Next.js 14 · Tailwind CSS · shadcn/ui
- **Deploy:** Railway (backend) + Vercel (frontend)
