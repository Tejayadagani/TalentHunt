#!/usr/bin/env bash
# SkillSync AI - One Command Hackathon Execution Script

set -e

echo "🚀 Starting SkillSync AI offline ranking pipeline..."

echo "📦 1. Checking Python environment..."
PYTHON=$(command -v python3 || command -v python)
echo "Using: $($PYTHON --version)"
echo "✅ Python ready. (rank.py uses only standard library — no pip install needed!)"

echo "📂 2. Extracting candidate database..."
if [ -f "candidates.jsonl.gz" ]; then
    gunzip -k -f candidates.jsonl.gz
    echo "✅ Database extracted."
elif [ -f "candidates.jsonl" ]; then
    echo "✅ Database already extracted."
else
    echo "❌ ERROR: candidates.jsonl.gz not found! Please place it in this directory."
    exit 1
fi

echo "🧠 3. Running deterministic 100k candidate sorting algorithm..."
$PYTHON rank.py --candidates ./candidates.jsonl --out ./submission.csv
echo "✅ Ranking complete. Output saved to submission.csv."

echo "🔍 4. Running official validation checks..."
$PYTHON backend/scripts/validate_submission.py submission.csv

echo "🎉 All Done! SkillSync AI pipeline completed successfully!"
