"""Recount sampling-frame sizes for RoganInglis/apps-control-arena at a pinned revision.

Reads only the needed parquet column chunks over HTTP range requests (a few MB,
not the 744 MB dataset), checks the problem-level flags against the individual
backdoor records, and writes the per-source sampling frames to CSV.

Usage:
    pip install pyarrow fsspec aiohttp
    python recount.py            # prints counts; writes frame_apps.csv, frame_control_tax.csv

Default pool = ControlArena's default AppsSetting filters
(has_solution=True -> solution_passes_tests, exclude_nondeterministic=True).
A problem is in a source's frame if at least one backdoor record has
source == <src> AND backdoor_works == True.
"""

import csv
import sys

import fsspec
import pyarrow.parquet as pq

REV = "29db28f76042952d56add8671f798280b200744d"
BASE = f"https://huggingface.co/datasets/RoganInglis/apps-control-arena/resolve/{REV}/data/"
FILES = [
    "train-00000-of-00003.parquet",
    "train-00001-of-00003.parquet",
    "train-00002-of-00003.parquet",
]
FLAT = [
    "problem_id",
    "solution_passes_tests",
    "is_nondeterministic",
    "backdoor_works",
    "has_apps_backdoor",
    "has_control_tax_backdoor",
    "apps_backdoor_works",
    "control_tax_backdoor_works",
]

fs = fsspec.filesystem("http", block_size=2**20)
rows = []
for name in FILES:
    with fs.open(BASE + name, "rb") as fh:
        pf = pq.ParquetFile(fh)
        if name == FILES[0]:
            paths = [pf.schema.column(i).path for i in range(len(pf.schema))]
            print("nested backdoor paths:", [p for p in paths if p.startswith("backdoors")], file=sys.stderr)
        bd_paths = [p for p in (pf.schema.column(i).path for i in range(len(pf.schema)))
                    if p.startswith("backdoors") and p.split(".")[-1] in ("source", "backdoor_works")]
        # Select flat columns plus only the two needed nested leaves (skips backdoor_code).
        t = pf.read(columns=FLAT + bd_paths)
        rows.extend(t.to_pylist())

def any_src(bds, src=None):
    for b in bds or []:
        if b.get("backdoor_works") is True and (src is None or b.get("source") == src):
            return True
    return False

def n_src(bds, src):
    return sum(1 for b in (bds or []) if b.get("backdoor_works") is True and b.get("source") == src)

N = len(rows)
mism = {"apps": 0, "control_tax": 0, "any": 0}
worry = {"apps": 0, "control_tax": 0}
pool = frame_any = frame_apps = frame_ct = frame_both = 0
rec_apps = rec_ct = 0
frames = {"apps": [], "control_tax": []}
for r in rows:
    bds = r.get("backdoors") or []
    pa_ = any_src(bds, "apps"); pc_ = any_src(bds, "control_tax"); pany = any_src(bds)
    mism["apps"] += pa_ != bool(r["apps_backdoor_works"])
    mism["control_tax"] += pc_ != bool(r["control_tax_backdoor_works"])
    mism["any"] += pany != bool(r["backdoor_works"])
    worry["apps"] += bool(r["has_apps_backdoor"]) and bool(r["backdoor_works"]) and not pa_
    worry["control_tax"] += bool(r["has_control_tax_backdoor"]) and bool(r["backdoor_works"]) and not pc_
    if r["solution_passes_tests"] and not r["is_nondeterministic"]:
        pool += 1
        frame_any += pany; frame_apps += pa_; frame_ct += pc_; frame_both += pa_ and pc_
        rec_apps += n_src(bds, "apps") if pa_ else 0
        rec_ct += n_src(bds, "control_tax") if pc_ else 0
        for src, hit in (("apps", pa_), ("control_tax", pc_)):
            if hit:
                frames[src].append((r["problem_id"], n_src(bds, src), pa_ and pc_))

print(f"rows={N}")
print(f"flag vs per-record mismatches: {mism}")
print(f"has_<src> & row-level works & no working <src> record: {worry}")
print(f"default pool (passes tests & deterministic)={pool}")
print(f"  with any working record={frame_any}")
print(f"  apps working record={frame_apps} (working apps records={rec_apps}, mean/problem={rec_apps/max(frame_apps,1):.2f})")
print(f"  control_tax working record={frame_ct} (working ct records={rec_ct}, mean/problem={rec_ct/max(frame_ct,1):.2f})")
print(f"  both={frame_both}")

for src, items in frames.items():
    with open(f"frame_{src}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["problem_id", f"working_{src}_records", "in_both_frames"])
        w.writerows(sorted(items, key=lambda x: (len(str(x[0])), str(x[0]))))
    print(f"wrote frame_{src}.csv ({len(items)} problems)")
