# -*- coding: utf-8 -*-
"""API 功能测试：health + convert + batch"""
import json, urllib.request, time, os, glob

BASE = "http://127.0.0.1:8890"

def post(path, data):
    req = urllib.request.Request(BASE+path, data=json.dumps(data).encode(),
                                 headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.load(r)

# 1) health
with urllib.request.urlopen(BASE+"/health", timeout=5) as r:
    print("HEALTH:", r.read().decode()[:200])

# 2) convert 一个小PDF
small = "E:/works-doc/技术学习/图灵AI面试核心点/11-其他/5.如何实现15分钟未支付自动取消订单.pdf"
if not os.path.exists(small):
    import glob
    # 找最小的pdf
    cands = glob.glob("E:/works-doc/技术学习/图灵AI面试核心点/**/*.pdf", recursive=True)
    small = min(cands, key=lambda p: os.path.getsize(p))
print("\n转换:", os.path.basename(small))
t0=time.time()
r = post("/convert", {"pdf": small, "out": "E:/works-doc/技术学习/图灵AI面试核心点/_api_test", "save_md": True})
print(f"convert: ok={r.get('ok')} chars={len(r.get('md','')) if isinstance(r.get('md'),str) else '?'} 耗时={round(time.time()-t0,1)}s")
if r.get("md"):
    print("内容预览:", r["md"][:200].replace("\n"," | "))

# 3) batch
print("\nbatch: 2个PDF")
r2 = post("/batch", {"pdfs": [small], "out": "E:/works-doc/技术学习/图灵AI面试核心点/_api_test"})
for res in r2.get("results", []):
    print(f"  {os.path.basename(res.get('pdf',''))}: ok={res.get('ok')} chars={res.get('chars')}")
