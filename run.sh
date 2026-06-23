#!/usr/bin/env bash
# SkillSync AI - One Command Hackathon Execution Script

set -e

echo "🚀 Starting SkillSync AI offline ranking pipeline..."

echo "📦 1. Installing dependencies..."
pip install -r requirements.txt > /dev/null 2>&1
echo "✅ Dependencies installed."

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
python rank.py --candidates ./candidates.jsonl --out ./submission.csv
echo "✅ Ranking complete. Output saved to submission.csv."

echo "🔍 4. Running official validation checks..."
python backend/scripts/validate_submission.py submission.csv

echo "🎉 All Done! SkillSync AI pipeline completed successfully!"
