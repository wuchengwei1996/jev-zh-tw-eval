# Jev-class decision models: Traditional Chinese evaluation

## What this is

A local evaluation archive and reproducible harness for Jev-compatible typed decision models, focused on crh225/plumb-4b. It contains Traditional Chinese limits tests, adversarial checks, synthetic fixtures, and a portable CLI. It is an independent study, with no claim of endorsement by TypeSafe, Plumb or JevBench.

## Conclusion

Suitable for assistance and routing after workflow-specific calibration. Unsuitable as the sole automatic gate for high-risk actions: refunds, deletion, external sending, or tools with side effects. High answer probability still permits confident mistakes and injection attacks.

## Key numbers

| Measure | Existing result | Scope |
|---|---|---|
| Options N, names / descriptions | 2: 95/96%; 4: 92/93%; 8: 90/93%; 12: 87/89%; 16: 77/86%; 20: 82/85%; 26: 73/81% | MASSIVE zh-TW, same 100 items per condition; 27 rejected by CLI |
| 60-class strategies | top1 70%, top2 74%, knockout 65% | Description version, same 100 items |
| CNA news, title / title+summary | 70.8% / 71.9% | 192 items, 11 publisher categories |
| LTN news, title / title+summary | 61.9% / 65.9% | 320 items, 8 publisher categories |
| Positive-review noul | ChnSentiCorp 85.3%; Amazon zh 80.8% | Simplified Chinese, n=150 / 120 |
| Review score exact / within one level | Amazon 51.3% / 86.7%; Dianping 49.0% / 96.0% | Simplified Chinese, n=150 / 100 |
| Offensive-language noul | ToxiCN 73.3%; COLD 69.3% | Simplified Chinese, n=150 each |
| English topic classification / spam | AG News 86%; Yahoo 70%; DBpedia 97%; SMS Spam 88.7% | Topic n=100 each; spam n=150, balanced |
| THUCNews length curve | 50–4000 characters: 72.5–82.5% | 40 base articles, 6 lengths; ECE 0.085→0.178 |
| Cross-strait precision | 0.25 title; 0.34 title+summary | P(yes)≥0.5, exclusion clause, 18 positives / 192 |
| Taiwan agency false positives | 9/22 (40.9%); existing gpt-oss:20b control 3/22 | Taiwan negatives only; mainland controls excluded |
| Injection target reached | 7/18 (38.9%) disguised note; 4/18 (22.2%) second suite; 8/18 (44.4%) guard+JSON | Different suites/conditions; target match is distinct from any error |
| Batch drift, Q=4→64 vs single | Mean absolute ΔP 0.03415→0.10174; maxima 0.69547→0.88322 | 30 states; choice agreement at Q64 26/30; noul 1735/1890 |
| Paraphrase drift | Mean range 0.201; max 0.805; 5/27 decision flips | Four wordings per item, separate from batch drift |
| Parallel language slice | zh-TW 85.8–87.5%; zh-CN 88.3–89.2%; en-US 90.8% | Same 120 ids, N=8; two instruction languages |

Numbers are imported historical measurements, not new runs. Full denominators, confidence intervals and selective coverage are in results/A and results/B. See adversarial/REPORT.md for four reviewers' evidence and corrections. Maximum answer probability is distinct from the API confidence field and is not a guarantee of correctness.

## Test conditions

Ollama 0.35.0, native `/v1/systemone`; crh225/plumb-4b, pinned digest prefix `368717f114a9`; RTX 4070 Ti SUPER 16GB and Apple M4 24GB. Study dates: 2026-10-02 through 2026-10-04. Limits experiments were recorded October 3; October 4 includes recomputation and reporting. No fresh model inference was performed while assembling this repository.
Accuracy in A includes successful answers from both machines; A latency normally filters the GPU alias, while batch Q uses the faster of two recorded passes. B latency includes both machines, with GPU-only fields separately available. Shared GPU load prevents a clean performance comparison.

## Limitations

Synthetic fixtures are artificial and single-annotator labeled; public corpora retain their own labels. Public questions may have appeared in training. The author's 131-item test split was used for calibration and is not a contamination-free holdout. Small samples and overlapping publisher categories limit generalization. Several sentiment and safety corpora are Simplified Chinese, not Traditional Chinese. Thresholds observed on the evaluation sample have no independent validation. RSS changes over time; omitted copyrighted or unlicensed texts prevent full historical replay. Latency is affected by shared GPU load.

## Reproduce

Python 3.9+, standard library only, macOS/Linux/WSL. Use an already installed Ollama and model; scripts never download model weights. No paid service is required. Run from the repository root:

```bash
export JEV_CONFIG="$PWD/jev-cli/config.example.json"
export JEV_ENDPOINTS='local=http://127.0.0.1:11434'
python3 -m unittest discover -s jev-cli -p 'test_*.py'
python3 eval/verify_release.py
python3 jev-cli/jev --dry-run noul '請把款項退回' '是否要求退款？'
```

The following commands perform local inference when explicitly run:

```bash
python3 jev-cli/jev eval data/synthetic/business.jsonl
python3 eval/run_fixed.py data/massive/exp1_N8_desc.jsonl
python3 eval/run_exp2.py
python3 eval/run_synthetic.py --injection
python3 eval/negation_zh.py
```

Set OLLAMA_URL instead of JEV_ENDPOINTS for a single endpoint. Historical English instructions were anonymized from a role noun to speaker; exact historical wording differs. More procedures and omitted-data limits: [eval/README.md](eval/README.md). Validation status: [eval/VALIDATION.md](eval/VALIDATION.md).

## License

Code: MIT, [LICENSE](LICENSE). Original documents, aggregate results and synthetic fixtures: CC BY 4.0, [LICENSE-docs](LICENSE-docs). MASSIVE keeps Amazon's CC BY 4.0 credit and modification notice in [data/SOURCES.md](data/SOURCES.md). Model weights and upstream datasets retain their own licenses. No newspaper text is redistributed.

---

# Jev 類 decision model：繁體中文實測與對抗驗證

## 這是什麼

獨立的本機評測整理與重現工具，主要測試crh225/plumb-4b，收錄繁中極限測試、四席對抗驗證、自製標註題與通用CLI。這不是TypeSafe、Plumb或JevBench的官方評測。

## 結論

適合輔助與分流，先用自家流程校準；不適合單獨作高風險自動閘門。退款、刪除、對外發送或有副作用工具必須人工確認或由確定性規則攔截。高機率仍會誤判，也會被外部文字劫持。

## 關鍵數字

| 指標 | 既有結果 | 範圍 |
|---|---|---|
| 選項數N：名稱／描述 | 2: 95/96%; 4: 92/93%; 8: 90/93%; 12: 87/89%; 16: 77/86%; 20: 82/85%; 26: 73/81% | MASSIVE繁中，各條件同100題；27選項由CLI拒絕 |
| 60類策略 | top1 70%, top2 74%, knockout 65% | 描述版，同100題 |
| 中央社：標題／標題加摘要 | 70.8% / 71.9% | 192則，11個發布者類別 |
| 自由時報：標題／標題加摘要 | 61.9% / 65.9% | 320則，8個發布者類別 |
| 正負評noul | ChnSentiCorp 85.3%; Amazon zh 80.8% | 簡中，150／120題 |
| 評論score：完全命中／±1級內 | Amazon 51.3% / 86.7%; Dianping 49.0% / 96.0% | 簡中，150／100題 |
| 冒犯語言noul | ToxiCN 73.3%; COLD 69.3% | 簡中，各150題 |
| 英文主題／垃圾簡訊 | AG News 86%; Yahoo 70%; DBpedia 97%; SMS Spam 88.7% | 主題各100題；垃圾簡訊150題，平衡抽樣 |
| THUCNews長度曲線 | 50–4000字：72.5–82.5% | 40篇基底，6種長度；ECE 0.085→0.178 |
| 兩岸題精確率 | 標題0.25；標題加摘要0.34 | P(是)≥0.5，含排除句；192則含18個正例 |
| 台灣機關假陽性 | 9/22（40.9%）；既有gpt-oss:20b對照3/22 | 只計台灣負例，不含大陸對照 |
| 注入達成攻擊者目標 | 偽裝備註7/18（38.9%）；第二組4/18（22.2%）；防護句加JSON為8/18（44.4%） | 不同題組／條件；達成target不等於任何答錯 |
| 批次Q=4→64對單題漂移 | 平均絕對ΔP 0.03415→0.10174；最大0.69547→0.88322 | 30則；Q64的choice同答26/30，noul同側1735/1890 |
| 換問法漂移 | 平均跨度0.201，最大0.805，5/27題答案翻轉 | 每題四種問法，與批次漂移分開 |
| 平行語言切片 | zh-TW 85.8–87.5%; zh-CN 88.3–89.2%; en-US 90.8% | 相同120個id，8選1；兩種指示語言 |

以上是既有實測，非本次新跑。選項曲線與各領域完整表、信賴區間及高信心涵蓋率見results/A、results/B。
表中信心採最高答案機率（noul為max(p,1−p)），不同於API的confidence，也不是答對率。

## 測試條件

Ollama 0.35.0、原生/v1/systemone、crh225/plumb-4b、模型digest前綴368717f114a9。
硬體RTX 4070 Ti SUPER 16GB與Apple M4 24GB；測試期間2026-10-02至10-04。
極限實驗在10月3日執行，10月4日包括重算與整理；建repo沒有新增模型推論。
A準確度涵蓋兩台成功回答，延遲通常只算GPU；批次Q取兩輪較快延遲。B延遲涵蓋兩台並另列GPU欄位，不能直接因果比較。

## 限制

合成題與單人標註不等於真實業務分布；公開資料則沿用上游標籤。公開題可能已被模型看過，作者131題test也曾用來校準。
情緒、安全、長文部分資料為簡中，不能冒稱繁中成績。小樣本、新聞分類邊界與同樣本挑門檻限制外推。
延遲受GPU共用影響。RSS會變動，版權或授權不明原文沒有收錄，歷史整輪無法完全重現。

## 怎麼重現

Python 3.9以上，只用標準函式庫；支援macOS/Linux/WSL。預先備妥Ollama與指定模型，腳本不自行下載權重。
從repo根目錄執行英文段的離線檢查；推論指令需另外明確執行。endpoint由JEV_ENDPOINTS或OLLAMA_URL指定，預設127.0.0.1。
RSS重建執行 `python3 eval/rebuild_rss.py`，只抓資料、不推論，輸出在git忽略的local-data/rss，類別取發布者feed。
固定抽樣、60類策略與批次重現步驟見[eval/README.md](eval/README.md)。

## 授權

程式碼MIT；文件、彙總結果與原創合成題CC BY 4.0。
MASSIVE維持Amazon的CC BY 4.0署名；其餘第三方資料及模型權重不受repo授權覆蓋。
授權明確不等於本次必須收錄；逐來源授權與取捨見[data/SOURCES.md](data/SOURCES.md)。
