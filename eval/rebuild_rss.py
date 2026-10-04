"""Re-fetch publisher-labeled news into ignored local-data only; no inference."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request

CNA = {"politics":"政治","intworld":"國際","mainland":"兩岸","finance":"財經","technology":"科技","lifehealth":"生活","social":"社會","local":"地方","culture":"文化","sport":"運動","stars":"娛樂"}
LTN = {"politics":"政治","society":"社會","life":"生活","world":"國際","business":"財經","sports":"體育","entertainment":"娛樂","local":"地方"}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-dir", type=Path, help="Use an existing RSS XML snapshot; no downloads")
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    target=root/"local-data"/"rss"
    raw=target/"raw"
    data=target/"eval"
    raw.mkdir(parents=True,exist_ok=True)
    data.mkdir(parents=True,exist_ok=True)
    manifest=[]
    for publisher, feeds in (("cna", CNA),("ltn", LTN)):
        for feed, category in feeds.items():
            url=("https://feeds.feedburner.com/rsscna/"+feed if publisher=="cna"
                 else "https://news.ltn.com.tw/rss/"+feed+".xml")
            if args.from_dir:
                payload=(args.from_dir/(publisher+"_"+feed+".xml")).read_bytes()
            else:
                with urllib.request.urlopen(url,timeout=30) as response:
                    payload=response.read(4*1024*1024+1)
                if len(payload)>4*1024*1024:
                    raise ValueError("RSS response exceeds 4 MiB")
            dest=raw/(publisher+"_"+feed+".xml")
            if dest.exists():
                raise FileExistsError("Snapshot already exists; archive local-data/rss before rebuilding")
            dest.write_bytes(payload)
            manifest.append({"publisher":publisher,"feed":feed,"category":category,"url":url,
                "retrieved_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "sha256":hashlib.sha256(payload).hexdigest(),
                "mode":"snapshot-import" if args.from_dir else "live-rss"})
    environment=dict(os.environ,RSS_RAW_DIR=str(raw),RSS_DATA_DIR=str(data))
    subprocess.run([sys.executable,str(root/"eval"/"build_news.py")],env=environment,check=True)
    (target/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("RSS rebuilt into ignored local-data/rss; historical counts are not guaranteed.")

if __name__=="__main__":
    main()
