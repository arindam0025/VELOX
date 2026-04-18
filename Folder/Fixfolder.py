"""
Run this ONCE to fix folder structure.
Just run:  python fix_folders.py
"""
import os, shutil

fixes = [
    ("Logic",   "portfolio"),   # rename Logic → portfolio
    ("Signals", "signals"),     # just in case capitalisation is off
    ("Data",    "data"),
    ("Results", "results"),
    ("Signals", "signals"),
]

for old, new in fixes:
    if os.path.exists(old) and not os.path.exists(new):
        shutil.copytree(old, new)
        print(f"  Copied {old}/ → {new}/")
    elif os.path.exists(new):
        print(f"  OK: {new}/ already exists")
    else:
        print(f"  SKIP: {old}/ not found")

# Check what we have now
print("\nCurrent folder structure:")
for folder in ["data", "signals", "portfolio", "results"]:
    if os.path.exists(folder):
        files = os.listdir(folder)
        print(f"  {folder}/ — {len(files)} files")
    else:
        print(f"  {folder}/ — MISSING (need to run pipeline)")