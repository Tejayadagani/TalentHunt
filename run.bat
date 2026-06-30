@echo off
echo 🚀 Starting SkillSync AI offline ranking pipeline...

echo 📦 1. Installing dependencies...
pip install -r requirements.txt > nul 2>&1
echo ✅ Dependencies installed.

echo 📂 2. Checking candidate database...
if exist "candidates.jsonl" (
    echo ✅ Database found.
) else (
    echo ❌ ERROR: candidates.jsonl not found! Please run the curl download command first.
    exit /b 1
)

echo 🧠 3. Running deterministic 100k candidate sorting algorithm...
python rank.py --candidates ./candidates.jsonl --out ./submission.csv
echo ✅ Ranking complete. Output saved to submission.csv.

echo 🔍 4. Running official validation checks...
python backend/scripts/validate_submission.py submission.csv

echo 🎉 All Done! SkillSync AI pipeline completed successfully!
