import csv, io, json

from pathlib import Path

ROOT = Path("c:/Users/yjd22/Desktop/python项目/GMV-LiveLens")
DATA_DIR = ROOT / "data"

raw = DATA_DIR.joinpath("shops.csv").read_bytes()
for enc in ("utf-8-sig", "gb18030", "utf-8", "gbk"):
    try:
        text = raw.decode(enc)
        break
    except:
        continue

print("=== shops.csv 完整映射 ===")
print(f"{'platform':8s} | {'companyshop_name':30s} | {'shop_name':15s}")
print("-" * 70)
for row in csv.DictReader(io.StringIO(text)):
    p = row["platform"].strip()
    c = row["companyshop_name"].strip()
    s = row["shop_name"].strip()
    print(f"{p:8s} | {c:30s} | {s:15s}")

print()
print("=== shop_name 是否唯一? ===")
from collections import Counter
cnt = Counter()
for row in csv.DictReader(io.StringIO(text)):
    cnt[row["shop_name"].strip()] += 1
for k, v in cnt.items():
    if v > 1:
        print(f"  ⚠ {k} 出现 {v} 次 (不唯一!!!)")
    else:
        print(f"  ✓ {k} 唯一")
