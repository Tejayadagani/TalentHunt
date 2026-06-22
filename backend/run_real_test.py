import subprocess
import time
import sys
import pandas as pd

real_candidates = "/Users/bhargavchowdaryyadagani/Downloads/India_runs_data_and_ai_challenge/candidates.jsonl"
print(f"Using real candidates file: {real_candidates}")

start_sequence = time.time()

print("\n--- Running 03_pre_score.py ---")
subprocess.run([
    sys.executable, "precompute/03_pre_score.py",
    "--candidates", real_candidates
], check=True)

print("\n--- Running 05_agent2_scout.py ---")
subprocess.run([
    sys.executable, "precompute/05_agent2_scout.py",
    "--candidates", real_candidates
], check=True)

print("\n--- Running 08_combine.py ---")
subprocess.run([
    sys.executable, "precompute/08_combine.py",
    "--candidates", real_candidates
], check=True)

print("\n--- Running rank.py ---")
subprocess.run([
    sys.executable, "rank.py",
    "--candidates", real_candidates,
    "--out", "artifacts/real_submission.csv"
], check=True)

total_time = time.time() - start_sequence
print(f"\nTotal Real Pipeline Time: {total_time:.1f}s")

# Spot check 10 real reasoning strings
print("\n--- Spot Check 10 Real Reasoning Strings ---")
df = pd.read_csv("artifacts/real_submission.csv")
for idx, row in df.head(10).iterrows():
    print(f"Rank {row['rank']} ({row['candidate_id']}) Score: {row['score']:.4f}")
    print(f"Reasoning: {row['reasoning']}")
    print("-" * 60)

