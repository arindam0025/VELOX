"""
One-time fix: maps your existing results/ files → portfolio/ folder
with the exact names the dashboard expects.

Run:  python fix_portfolio.py
"""
import os, shutil, re

os.makedirs("portfolio", exist_ok=True)

# Map from signal column suffix → strategy name dashboard expects
SIGNAL_MAP = {
    "Signal_MA":  "MA_Crossover",
    "Signal_RSI": "RSI",
    "Signal_BB":  "Bollinger",
}

# Map from file type suffix → dashboard suffix
TYPE_MAP = {
    "equity": "portfolio",
    "trades": "trades",
}

fixed   = 0
skipped = 0

print("Scanning results/ folder...")
print("-" * 55)

for fname in sorted(os.listdir("results")):
    if not fname.endswith(".csv"):
        continue

    # Expected pattern: StockName_Signal_XX_type.csv
    # e.g. Bajaj_Finance_Signal_BB_equity.csv
    match = re.match(r"^(.+)_(Signal_(?:MA|RSI|BB))_(equity|trades)\.csv$", fname)
    if not match:
        print(f"  SKIP (unrecognised pattern): {fname}")
        skipped += 1
        continue

    stock_raw, signal_col, ftype = match.groups()

    strategy = SIGNAL_MAP.get(signal_col)
    suffix   = TYPE_MAP.get(ftype)

    if not strategy or not suffix:
        print(f"  SKIP (unknown signal/type): {fname}")
        skipped += 1
        continue

    new_name = f"{stock_raw}_{strategy}_{suffix}.csv"
    src  = os.path.join("results", fname)
    dst  = os.path.join("portfolio", new_name)

    shutil.copy2(src, dst)
    print(f"  OK: {fname}")
    print(f"   → portfolio/{new_name}")
    fixed += 1

print("-" * 55)
print(f"\nDone.  {fixed} files copied → portfolio/")
print(f"       {skipped} files skipped")
print()

# Verify
csvs = [f for f in os.listdir("portfolio") if f.endswith(".csv")]
print(f"portfolio/ now has {len(csvs)} CSV files.")
if csvs:
    print("Sample:")
    for f in sorted(csvs)[:6]:
        print(f"  {f}")
    print()
    print("Now run:")
    print("  python -m streamlit run dashboard.py")
else:
    print("Still empty — check that results/ has files matching:")
    print("  StockName_Signal_BB_equity.csv")
    print("  StockName_Signal_MA_equity.csv  etc.")