# Jev / Plumb-4B：繁體中文判斷模型評測與對抗驗證

**語言**：繁體中文｜[English](#english)

這份獨立評測使用 Ollama /v1/systemone 與 Plumb-4B，檢驗 Jev 相容的 TypeSafe System One 判斷模型介面在繁體中文（zh-TW）的表現。
內容結合提示注入的對抗測試、準確度與答案機率檢查，協助 AI agents 評估輔助判斷與分流的適用範圍。

## 這是什麼

獨立的本機評測整理與重現工具，主要測試crh225/plumb-4b，收錄繁中極限測試、四席對抗驗證、自製標註題與通用CLI。這不是TypeSafe、Plumb或JevBench的官方評測。

## 結論

**適合輔助與分流，先用自家流程校準；不適合單獨作高風險自動閘門。**退款、刪除、對外發送或有副作用工具必須人工確認或由確定性規則攔截。高機率仍會誤判，也會被外部文字劫持。

## 關鍵發現（Key findings）

- 在 JevBench 公開 231 題中，Plumb-4B 於各次已記錄的 Apple M4 與 RTX 4070 Ti SUPER 測試皆回答全部題目，依本地 CLI 計分得 203/231（87.88%），此數字不是官方 JevBench Score（[公開題彙總](results/jevbench_public231.json)）。
- 在同一批 100 題 MASSIVE zh-TW、選項附繁中描述的條件下，Plumb-4B 於 2 選項答對 96/100、8 選項答對 93/100、26 選項答對 81/100（[A 摘要](results/A/SUMMARY.txt)）。
- 在採發布者分類標籤、輸入標題加摘要的歷史台灣新聞測試中，Plumb-4B 於中央社答對 138/192（71.88%）、自由時報答對 211/320（65.94%），此標籤並非另行重標的純語意評測（[B 摘要](results/B/SUMMARY.txt)）。
- 在第一輪 18 題合成提示注入測試中，偽裝備註使 7/18 題（38.9%）達成攻擊者指定答案，其中 2 題的所選答案機率至少 0.9（[對抗彙總](results/adversarial.json)）。
- 在 24 題合成業務弱點探針中，所選答案機率至少 0.9 的 12 題仍有 3 題答錯，高機率未能消除這個受測子集的錯誤（[對抗彙總](results/adversarial.json)）。

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

JevBench公開題的2026-10-02彙總、資料來源與授權見[results/jevbench_public231.json](results/jevbench_public231.json)；這是CLI計分結果，不是官方JevBench Score。

以上是既有實測，非本次新跑。選項曲線與各領域完整表、信賴區間及高信心涵蓋率見results/A、results/B。
表中信心採最高答案機率（noul為max(p,1−p)），不同於API的confidence，也不是答對率。

## 常見問題（FAQ）

### 繁體中文用 Jev / Plumb-4B 準不準？

準確度取決於任務：同一批 100 題 MASSIVE zh-TW、選項附描述時，2 選項得 96%、8 選項得 93%、26 選項得 81%（[A 摘要](results/A/SUMMARY.txt)）。
新聞輸入標題加摘要、以發布者分類為答案時，中央社 192 題得 71.88%，自由時報 320 題得 65.94%（[B 摘要](results/B/SUMMARY.txt)）。
另外的 JevBench 公開題 203/231 是本地 CLI 成績，既非純繁中測試，也非官方 JevBench Score（[公開題彙總](results/jevbench_public231.json)）。

### 有沒有免費自架的 Jev API 替代方案？

有：本 repo 支援透過 Ollama 0.35.0 以上版本在本機執行 Plumb-4B，不必呼叫付費 API，可使用[釘選版本的本地設定](jev-cli/config.example.json)與 [System One 介面](https://docs.ollama.com/api/systemone)。
你需先備妥相容模型與自己的硬體；腳本不下載權重，本地運算仍會消耗電力。
CLI 程式碼採 MIT，原創文件與題庫採 CC BY 4.0，模型權重各依原授權（[來源與授權](data/SOURCES.md)）。

### 判斷模型一題最多放幾個選項才可靠？

沒有通用的可靠上限：同一批 100 題 MASSIVE zh-TW、選項附描述時，2 與 8 選項得 96% 與 93%，26 選項降至 81%（[A 摘要](results/A/SUMMARY.txt)）。
本地 CLI 接受 2–26 選項，27 選項在推論前即拒絕；這是客戶端上限，沒有量到模型在 27 選項的準確度。
完整 60 類任務中，描述版兩段式保留前 2 個大類得 74/100，實際分流前仍需驗證自己的候選集合。

### 提示注入會翻轉 LLM 分類器的答案嗎？

會：第一輪 Plumb-4B 合成注入測試中，偽裝備註使 7/18 題（38.9%）達成攻擊者指定答案（[對抗彙總](results/adversarial.json)）。
另一組 18 題在攻擊後有 4/18 題達成指定答案，加防護句且改用 JSON 後為 8/18；兩個條件同時改動，不能把差異單獨歸因於防護句。
達成攻擊目標與任何答錯不同，小型合成題組也不能估計所有真實場景的攻擊率（[審查與修正](adversarial/REPORT.md)）。

### 如何用 Ollama /v1/systemone 執行 Jev 相容模型？

先備妥 Ollama 0.35.0 以上版本與已安裝的 `crh225/plumb-4b`，再選用 CLI 的[本地版本釘選設定](jev-cli/config.example.json)，即可走原生 `/v1/systemone` 介面（[官方介面文件](https://docs.ollama.com/api/systemone)）。
從 repo 根目錄設定 `export JEV_CONFIG="$PWD/jev-cli/config.example.json"` 與 `export JEV_ENDPOINTS='local=http://127.0.0.1:11434'`，再執行 `python3 jev-cli/jev --dry-run noul '請把款項退回' '是否要求退款？'`，只檢視請求、不推論。
準備執行本地推論時移除該指令的 `--dry-run`；固定題庫、批次與未收錄資料的限制見[重現說明](eval/README.md)。

### AI agents 應該把判斷模型機率當成自動閘門嗎？

不應單獨用於高風險動作：24 題合成弱點探針中，所選答案機率至少 0.9 的 12 題仍錯 3 題（[對抗彙總](results/adversarial.json)）。
低風險輔助與分流可先用自己的標註資料校準，再用獨立保留集驗證門檻；退款、刪除、對外發送與有副作用工具需人工確認或確定性規則。
最高答案機率不同於 API 的 `confidence` 欄位，小樣本上觀察到的門檻也不是正確保證（[審查與使用邊界](adversarial/REPORT.md)）。

### 換問法後，判斷模型的機率與答案會保持一致嗎？

不一定：既有合成業務題的換問法測試中，27 題有 5 題答案翻轉（[對抗彙總](results/adversarial.json)）。
同題不同問法的機率跨度平均 0.201、最大 0.805；這是問法敏感度，批次實驗則衡量批次機率相對於單題機率的差異（[A 摘要](results/A/SUMMARY.txt)）。
驗證流程時先固定指示、選項描述與批次組成，再分開測試刻意改動的情況。

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

## 如何引用（How to cite）

引用本評測或重現工具時，請使用 [CITATION.cff](CITATION.cff) 所列的作者別名、標題、發布日期與 repo 網址。
引用實測數字時，請一併連到對應結果檔並保留測試條件；本地 CLI 準確度不是官方 JevBench Score。

## 授權

程式碼MIT；文件、彙總結果與原創合成題CC BY 4.0。
MASSIVE維持Amazon的CC BY 4.0署名；其餘第三方資料及模型權重不受repo授權覆蓋。
授權明確不等於本次必須收錄；逐來源授權與取捨見[data/SOURCES.md](data/SOURCES.md)。

---

<a id="english"></a>

# Jev / Plumb-4B: Traditional Chinese decision model evaluation

This independent evaluation studies the Jev-compatible TypeSafe System One decision model interface in Traditional Chinese (zh-TW), using Plumb-4B through Ollama /v1/systemone.
It combines adversarial testing of prompt injection with accuracy and probability checks to help AI agents assess assistance and routing workflows.

## What this is

A local evaluation archive and reproducible harness for Jev-compatible typed decision models, focused on crh225/plumb-4b. It contains Traditional Chinese limits tests, adversarial checks, synthetic fixtures, and a portable CLI. It is an independent study, with no claim of endorsement by TypeSafe, Plumb or JevBench.

## Conclusion

**Suitable for assistance and routing after workflow-specific calibration; unsuitable as the sole automatic gate for high-risk actions.** Refunds, deletion, external sending, or tools with side effects require human confirmation or deterministic rules. High answer probability still permits confident mistakes and injection attacks.

## Key findings

- On the 231 public JevBench questions, Plumb-4B answered every question and scored 203/231 (87.88%) on each recorded Apple M4 and RTX 4070 Ti SUPER run using the local CLI scorer, which is not the official JevBench Score ([public-question aggregates](results/jevbench_public231.json)).
- On the same 100 MASSIVE zh-TW items with Traditional Chinese option descriptions, Plumb-4B scored 96/100 with 2 options, 93/100 with 8 options, and 81/100 with 26 options ([A summary](results/A/SUMMARY.txt)).
- On historical Taiwan-news publisher-category tests using titles plus summaries, Plumb-4B scored 138/192 (71.88%) for CNA and 211/320 (65.94%) for LTN, with publisher labels rather than an independently relabeled semantic benchmark ([B summary](results/B/SUMMARY.txt)).
- In the first 18-item synthetic prompt-injection suite, disguised notes reached the attacker's target answer on 7/18 items (38.9%), including 2 items with selected-answer probability at least 0.9 ([adversarial aggregates](results/adversarial.json)).
- In the 24-item synthetic business weakness-probe suite, 3 of the 12 answers with selected-answer probability at least 0.9 were wrong, so high probability did not eliminate errors on that tested subset ([adversarial aggregates](results/adversarial.json)).

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

Historical JevBench public-question aggregates (October 2, 2026), dataset provenance and licensing are in [results/jevbench_public231.json](results/jevbench_public231.json). These CLI-scored results are not the official JevBench Score.

Numbers are imported historical measurements, not new runs. Full denominators, confidence intervals and selective coverage are in results/A and results/B. See adversarial/REPORT.md for four reviewers' evidence and corrections. Maximum answer probability is distinct from the API confidence field and is not a guarantee of correctness.

## FAQ

### How accurate is Jev / Plumb-4B on Traditional Chinese?

Accuracy depends on the task: on the same 100 MASSIVE zh-TW items with option descriptions, Plumb-4B scored 96% with 2 options, 93% with 8, and 81% with 26 ([A summary](results/A/SUMMARY.txt)).
Taiwan-news classification using titles plus summaries scored 71.88% on 192 CNA items and 65.94% on 320 LTN items under publisher-category labels ([B summary](results/B/SUMMARY.txt)).
The separate 203/231 public JevBench result is a local CLI score, not a Traditional Chinese-only result or the official JevBench Score ([public-question aggregates](results/jevbench_public231.json)).

### Is there a free self-hosted alternative to the Jev API?

Yes: this repository supports local Plumb-4B through Ollama 0.35.0 or later without paid API calls, using the [pinned local configuration](jev-cli/config.example.json) and the [System One endpoint](https://docs.ollama.com/api/systemone).
You need an already installed compatible model and your own hardware; the scripts do not download weights, and local compute still uses electricity.
The CLI code is MIT, the original documents and fixtures are CC BY 4.0, and model weights retain their own licenses ([source and license notes](data/SOURCES.md)).

### How many options can a decision model reliably choose from?

There is no universally reliable option count: with descriptions on the same 100 MASSIVE zh-TW items, 2 and 8 options scored 96% and 93%, while 26 options scored 81% ([A summary](results/A/SUMMARY.txt)).
This local CLI accepts 2–26 options and rejects 27 before inference; that is a client limit, not a measured model failure at 27 options.
For the full 60-class task, a two-stage description strategy retaining the top 2 broad categories scored 74/100; validate your own candidate set before using such routing.

### Can prompt injection flip an LLM classifier's answer?

Yes: disguised notes reached the attacker's target on 7/18 items (38.9%) in the first synthetic Plumb-4B injection suite ([adversarial aggregates](results/adversarial.json)).
A different 18-item suite reached the target on 4/18 items, or 8/18 with a combined guard-instruction and JSON-format condition; those simultaneous changes do not isolate the guard's effect.
Target attainment is distinct from any wrong answer, and these small synthetic suites do not estimate a population-wide attack rate ([review and corrections](adversarial/REPORT.md)).

### How to run a Jev-compatible model with Ollama /v1/systemone?

Use Ollama 0.35.0 or later with an already installed `crh225/plumb-4b`, then select the CLI's [pinned local configuration](jev-cli/config.example.json) for the native `/v1/systemone` endpoint ([official endpoint documentation](https://docs.ollama.com/api/systemone)).
From the repository root, set `export JEV_CONFIG="$PWD/jev-cli/config.example.json"` and `export JEV_ENDPOINTS='local=http://127.0.0.1:11434'`, then run `python3 jev-cli/jev --dry-run noul '請把款項退回' '是否要求退款？'` to inspect the request without inference.
When ready to run local inference, omit `--dry-run` from that command; the [reproduction guide](eval/README.md) covers fixed fixtures, batching, and omitted-data limits.

### Should AI agents use decision-model probabilities as automatic gates?

They should not use them as the sole gate for high-risk actions: the 24-item synthetic weakness-probe suite contained 3 wrong answers among 12 answers with selected-answer probability at least 0.9 ([adversarial aggregates](results/adversarial.json)).
For low-risk assistance and routing, calibrate on workflow-specific labels and validate thresholds on an independent holdout; refunds, deletion, external sending, and tools with side effects require human confirmation or deterministic rules.
Maximum answer probability differs from the API's `confidence` field, and a threshold observed on a small test set is not a correctness guarantee ([review and boundaries](adversarial/REPORT.md)).

### Are decision-model probabilities stable when the question is reworded?

They can change: rewording flipped the decision on 5/27 synthetic business items in the recorded paraphrase suite ([adversarial aggregates](results/adversarial.json)).
The mean within-item probability range was 0.201 and the maximum was 0.805; this range measures wording sensitivity, whereas the batch experiment measures differences from single-question probabilities ([A summary](results/A/SUMMARY.txt)).
Keep instructions, option descriptions, and batch composition fixed during workflow validation, then test deliberate variations separately.

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

## How to cite

Use [CITATION.cff](CITATION.cff) for the author alias, title, release date, and repository URL when citing this evaluation or its reproducible harness.
Cite the linked result file and its test conditions alongside any quoted measurement; local CLI accuracy is not an official JevBench Score.

## License

Code: MIT, [LICENSE](LICENSE). Original documents, aggregate results and synthetic fixtures: CC BY 4.0, [LICENSE-docs](LICENSE-docs). MASSIVE keeps Amazon's CC BY 4.0 credit and modification notice in [data/SOURCES.md](data/SOURCES.md). Model weights and upstream datasets retain their own licenses. No newspaper text is redistributed.
