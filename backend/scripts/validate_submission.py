import csv
import sys
from pathlib import Path

def validate():
    if len(sys.argv) > 1:
        csv_path = Path(sys.argv[1]).resolve()
    else:
        csv_path = Path(__file__).resolve().parent.parent / "submission.csv"

    if not csv_path.exists():
        print(f"❌ FAIL: {csv_path} does not exist.")
        sys.exit(1)
        
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        
        # Check 2: Exact Columns
        expected_header = ["candidate_id", "rank", "score", "reasoning"]
        if header != expected_header:
            print(f"❌ FAIL: Columns are {header}, expected {expected_header}")
            sys.exit(1)
            
        rows = list(reader)
        
    # Check 1: Exactly 100 rows
    if len(rows) != 100:
        print(f"❌ FAIL: Expected 100 rows, found {len(rows)}")
        sys.exit(1)
        
    # Check 3 & 4: Ranks 1-100 unique, and scores monotonic non-increasing
    ranks = []
    scores = []
    for r in rows:
        ranks.append(int(r[1]))
        scores.append(float(r[2]))
        
        # Check 6 part 1: Reasoning non-empty
        if not r[3].strip():
            print(f"❌ FAIL: Empty reasoning found for rank {r[1]}")
            sys.exit(1)

    expected_ranks = list(range(1, 101))
    if sorted(ranks) != expected_ranks:
        print("❌ FAIL: Ranks are not exactly integers 1 through 100 with no duplicates/gaps.")
        sys.exit(1)
        
    for i in range(len(scores) - 1):
        if scores[i] < scores[i+1]:
            print(f"❌ FAIL: Scores are not monotonically non-increasing! Score {scores[i]} at rank {i+1} < score {scores[i+1]} at rank {i+2}")
            sys.exit(1)
            
    print("✅ PASS: submission.csv is perfectly valid against all Hackathon constraints.")
    sys.exit(0)

if __name__ == "__main__":
    validate()
