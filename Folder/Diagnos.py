"""
Run this to diagnose exactly what's missing and fix it.
    python diagnose.py
"""
import os

print("=" * 60)
print("PIPELINE DIAGNOSTIC")
print("=" * 60)

folders = {
    "data":      "Step 1 — Data Collection",
    "signals":   "Step 2 — Strategy / Signals",
    "portfolio": "Step 3 — Execution Engine",
    "results":   "Step 4 — Performance Metrics",
}

all_ok = True
for folder, step in folders.items():
    exists = os.path.exists(folder)
    files  = os.listdir(folder) if exists else []
    csvs   = [f for f in files if f.endswith(".csv")]
    status = "OK" if csvs else ("EMPTY" if exists else "MISSING")
    icon   = "✓" if csvs else "✗"
    print(f"\n  {icon} {folder}/  [{status}]  — {step}")
    if csvs:
        for f in sorted(csvs)[:5]:
            print(f"      {f}")
        if len(csvs) > 5:
            print(f"      ... and {len(csvs)-5} more")
    else:
        print(f"      No CSV files found")
    if not csvs:
        all_ok = False

print("\n" + "=" * 60)

if all_ok:
    print("All folders have data. Dashboard should work.")
    print("Run:  python -m streamlit run dashboard.py")
else:
    print("WHAT TO RUN:")
    print()
    if not [f for f in os.listdir("data") if f.endswith(".csv")] if os.path.exists("data") else True:
        print("  python Data.py          # creates data/")
    if not [f for f in os.listdir("signals") if f.endswith(".csv")] if os.path.exists("signals") else True:
        print("  python Strategy.py      # creates signals/")
    if not [f for f in os.listdir("portfolio") if f.endswith(".csv")] if os.path.exists("portfolio") else True:
        print("  python Engine.py        # creates portfolio/")
    if not [f for f in os.listdir("results") if f.endswith(".csv")] if os.path.exists("results") else True:
        print("  python metric.py        # creates results/")
    print()
    print("  Then: python -m streamlit run dashboard.py")

print("=" * 60)