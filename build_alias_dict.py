"""
Build alias dictionary from gene_aliases CSV.

CSV format: two columns (col1, col2) where col1 is AGI or primary symbol,
col2 is a symbol/alias. Rows sharing the same col1 form an alias group.

Output: utils/alias_to_stringDict.json mapping lowercase alias -> canonical
string like "APUM22, PUM22, AT1G01410" (no parens — caller adds them).

Usage:
    python build_alias_dict.py path/to/aliases.csv
"""
import csv
import json
import re
import sys
from collections import defaultdict

CSV_PATH = sys.argv[1] if len(sys.argv) > 1 else "/mnt/data/gene_aliases_20230105.csv"
OUT_PATH = "utils/alias_to_stringDict.json"

AGI_RE = re.compile(r"^AT[1-5CM]G\d{5}$", re.IGNORECASE)

# Group rows by col1 (AGI or primary symbol)
groups = defaultdict(set)
with open(CSV_PATH, newline="", encoding="utf-8") as f:
    for row in csv.reader(f):
        if not row or len(row) < 2:
            continue
        a = row[0].strip()
        b = row[1].strip()
        if not a:
            continue
        groups[a].add(a)
        if b:
            groups[a].add(b)

print(f"Read {CSV_PATH}: {len(groups)} groups")

# Build canonical string for each group: non-AGI aliases (sorted) + AGI at end
alias_dict = {}
for primary, members in groups.items():
    agi = sorted(m for m in members if AGI_RE.match(m))
    non_agi = sorted((m for m in members if not AGI_RE.match(m)), key=str.lower)
    ordered = non_agi + agi
    canonical = ", ".join(ordered)
    for m in members:
        alias_dict[m.lower()] = canonical

# Drop keys shorter than 3 chars (too noisy)
short_keys = [k for k in alias_dict if len(k) < 3]
for k in short_keys:
    del alias_dict[k]

# Drop common English words, chemistry notations, and units that would
# cause false positives when the alias dict is used to tag entities.
EXCLUSIONS = {
    # originally-dropped english words
    "and", "ara", "main", "arm", "big", "sand", "can", "best", "polar",
    "fitness", "flip", "sub", "cal", "lot", "mate", "zip", "skip", "serrate",
    "fit", "tri", "man", "chat", "rep", "flu", "pumpkin", "dim", "act",
    "tic", "sup", "ant", "eat", "chia", "mid", "sap", "pan", "try", "fed",
    "rib", "chip", "kelp", "fact", "tasty", "clasp", "late", "daf", "chl",
    # ion/chemistry notations
    "ca2", "cu2", "mn2", "mg2", "fe3", "fe2", "zn2", "so4",
    # time / measurement units commonly seen inline in captions
    "min", "mins", "sec", "secs", "hr", "hrs", "day", "days", "mo", "yr",
    "ml", "ul", "mg", "ug", "ng", "kg", "cm", "mm", "nm", "pm", "ppm",
    # month abbreviations
    "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
    # common english that also happen to be gene symbols (tagging noise)
    "has", "not", "tax", "tip", "nut", "eye", "bar", "tub", "dip", "big",
    "sap", "sup", "sun", "win", "lip", "arm", "leg", "bat", "cat", "dog",
    "bed", "bus", "pot", "pit", "set", "pin", "cup", "map", "log", "bag",
}
removed_english = 0
for w in EXCLUSIONS:
    if w in alias_dict:
        del alias_dict[w]
        removed_english += 1

print(f"Dropped {len(short_keys)} short keys, {removed_english} English-word keys")
print(f"Final alias dict: {len(alias_dict)} entries")

# Sample output
print("\nSamples:")
for key in ["cesa", "etc1", "at1g01380", "pum22", "aar1", "npr1"]:
    print(f"  {key:20s} -> {alias_dict.get(key, '<not found>')}")

with open(OUT_PATH, "w") as f:
    json.dump(alias_dict, f)
print(f"\nWrote {OUT_PATH}")
