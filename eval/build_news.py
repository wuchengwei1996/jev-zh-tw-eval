# 由 raw/ 的中央社、自由時報 RSS 產生題目 jsonl（標準答案＝發布者自己的分類＝來源 feed）。
import collections, html, json, os, re, xml.etree.ElementTree as ET

B = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.environ["RSS_RAW_DIR"]
DATA = os.environ["RSS_DATA_DIR"]
os.makedirs(DATA, exist_ok=True)


def clean(s):
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()


def parse(prefix, feeds):
    items, seen = [], collections.Counter()
    for code, label in feeds.items():
        root = ET.parse(os.path.join(RAW, "%s_%s.xml" % (prefix, code))).getroot()
        for it in root.findall("channel/item"):
            link = (it.findtext("link") or "").strip()
            items.append({"feed": code, "label": label, "title": clean(it.findtext("title")),
                          "desc": clean(it.findtext("description")), "link": link,
                          "pubDate": it.findtext("pubDate")})
            seen[link] += 1
    dup = {l for l, c in seen.items() if c > 1}
    kept = [x for x in items if x["link"] not in dup]
    return items, kept, dup


def write(name, rows, comment):
    p = os.path.join(DATA, name)
    with open(p, "w", encoding="utf-8") as f:
        f.write("// " + comment + "\n")
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(name, len(rows))


# ---------- 中央社 ----------
CNA = {"politics": "政治", "intworld": "國際", "mainland": "兩岸", "finance": "財經", "technology": "科技",
       "lifehealth": "生活", "social": "社會", "local": "地方", "culture": "文化", "sport": "運動", "stars": "娛樂"}
CNA_CRIT = {
    "政治": "台灣國內政治：總統府、行政院、立法院、政黨、選舉、國防與外交政策",
    "國際": "其他國家或國際組織發生的事（不涉及中國大陸、港澳與兩岸關係）",
    "兩岸": "中國大陸內部的事、港澳、兩岸關係與往來",
    "財經": "經濟、股市匯市、產業、企業經營、經濟數據",
    "科技": "科技產業、半導體、AI、資訊通訊、科學研究",
    "生活": "醫藥健康、天氣、交通、消費、教育等日常生活",
    "社會": "犯罪、司法案件、詐騙、意外事故",
    "地方": "台灣各縣市地方政府的施政與地方活動",
    "文化": "藝文、出版、展覽、宗教、文化資產",
    "運動": "體育賽事與運動員",
    "娛樂": "影視、音樂、明星藝人",
}
allc, cna, dup = parse("cna", CNA)
print("CNA raw", len(allc), "dup links dropped", len(dup), "kept", len(cna), collections.Counter(x["label"] for x in cna))
Q_CHOICE = "這則中央社新聞屬於哪一個新聞分類？"
Q_NOUL = "這則新聞的主題是否與中國大陸或兩岸關係有關？主要內容是台灣國內事務、或與中國無關的其他國家事務，都算否。"
rows = {"cna_choice_title": [], "cna_choice_titlesum": [], "cna_noul_title": [], "cna_noul_titlesum": []}
for i, x in enumerate(cna):
    meta = {"feed": x["feed"], "label": x["label"], "link": x["link"], "pubDate": x["pubDate"]}
    st_t = x["title"]
    st_ts = "【標題】%s【摘要】%s" % (x["title"], x["desc"])
    rows["cna_choice_title"].append({"id": "cna%03d_ct" % i, "type": "choice", "state": st_t, "instructions": Q_CHOICE,
                                     "criteria": CNA_CRIT, "expected": x["label"], "meta": meta})
    rows["cna_choice_titlesum"].append({"id": "cna%03d_cs" % i, "type": "choice", "state": st_ts, "instructions": Q_CHOICE,
                                        "criteria": CNA_CRIT, "expected": x["label"], "meta": meta})
    rows["cna_noul_title"].append({"id": "cna%03d_nt" % i, "type": "noul", "state": st_t, "instructions": Q_NOUL,
                                   "expected": x["label"] == "兩岸", "meta": meta})
    rows["cna_noul_titlesum"].append({"id": "cna%03d_ns" % i, "type": "noul", "state": st_ts, "instructions": Q_NOUL,
                                      "expected": x["label"] == "兩岸", "meta": meta})
for k, v in rows.items():
    write(k + ".jsonl", v, "中央社 RSS 重建抓取，%d 則（跨分類重複的 %d 則已剔除），標準答案＝中央社自己的分類 feed；只供內部測試，不轉載" % (len(v), len(dup)))

# ---------- 自由時報（第二來源，只做 choice；摘要開頭的〔XX頻道／報導〕會洩漏分類，已剝除） ----------
LTN = {"politics": "政治", "society": "社會", "life": "生活", "world": "國際", "business": "財經", "sports": "體育",
       "entertainment": "娛樂", "local": "地方"}
LTN_CRIT = {
    "政治": "台灣政治：政府、國會、政黨、選舉、國防外交、兩岸政策",
    "社會": "犯罪、司法案件、詐騙、意外事故",
    "生活": "天氣、交通、醫療健康、消費、教育等日常生活",
    "國際": "外國與中國大陸發生的事、國際關係",
    "財經": "經濟、股市、產業、企業、房市、稅務",
    "體育": "體育賽事與運動員",
    "娛樂": "影視、音樂、明星藝人",
    "地方": "台灣各縣市地方政府施政與地方新聞",
}
alll, ltn, dupl = parse("ltn", LTN)
print("LTN raw", len(alll), "dup dropped", len(dupl), "kept", len(ltn), collections.Counter(x["label"] for x in ltn))
Q_LTN = "這則自由時報新聞屬於哪一個新聞分類？"
lt, ls = [], []
for i, x in enumerate(ltn):
    desc = re.sub(r"^\s*〔[^〕]{0,40}〕", "", x["desc"]).strip()
    desc = desc[:200]
    meta = {"feed": x["feed"], "label": x["label"], "link": x["link"], "pubDate": x["pubDate"]}
    lt.append({"id": "ltn%03d_ct" % i, "type": "choice", "state": x["title"], "instructions": Q_LTN, "criteria": LTN_CRIT,
               "expected": x["label"], "meta": meta})
    ls.append({"id": "ltn%03d_cs" % i, "type": "choice", "state": "【標題】%s【摘要】%s" % (x["title"], desc),
               "instructions": Q_LTN, "criteria": LTN_CRIT, "expected": x["label"], "meta": meta})
write("ltn_choice_title.jsonl", lt, "自由時報 RSS 重建抓取，8 分類，跨分類重複剔除；標準答案＝自由時報自己的分類；只供內部測試")
write("ltn_choice_titlesum.jsonl", ls, "同上，加摘要前 200 字（已剝除開頭〔頻道／報導〕標籤以免洩漏答案）")
