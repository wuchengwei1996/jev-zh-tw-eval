# 重現範圍與操作

所有指令從repo根目錄執行。Python 3.9以上、標準函式庫、macOS/Linux/WSL。
本次整理不推論；下列模型指令留給後續明確執行。已有結果在results/，新結果只寫local-results/。

## 先設本機endpoint與版本釘選

```bash
export JEV_CONFIG="$PWD/jev-cli/config.example.json"
export JEV_ENDPOINTS='local=http://127.0.0.1:11434'
# 或不設JEV_ENDPOINTS而設OLLAMA_URL，預設仍為本機。
```

多endpoint可用逗號分隔；Q與adaptive用同一份環境指定列表。若量延遲，只指定一個endpoint並設JEV_LATENCY_ENDPOINT為其name。
common.py尋找repo內jev-cli/jev；可用JEV_CLI覆寫。JEV_RESULTS_DIR覆寫原始輸出目錄，預設local-results/A。
若只設OLLAMA_URL，CLI的served_by名稱是127.0.0.1，彙整延遲請另設 `export JEV_LATENCY_ENDPOINT=127.0.0.1`；否則預設local找不到對應延遲樣本，準確度仍按全部成功答案計。
原CLI保留付費後端功能與假服務測試，eval腳本一律用預設local，沒有切換付費後端。

## MASSIVE固定題與大類策略

原先test各2974列、三語id完全對齊，seed=42。公開data/massive包含來源整理檔、既有抽題和固定criteria。
為避免覆寫題庫，可把資料複製到local-data/massive後指定JEV_DATA_DIR，再執行build_massive.py。
英文角色名詞通用化，繁中原題與人工標籤保留。build_massive會生成N=27超限探測，不放進正常準確度計分。

```bash
python3 eval/run_fixed.py data/massive/exp1_N2_name.jsonl data/massive/exp1_N2_desc.jsonl
python3 eval/run_fixed.py data/massive/exp1_N4_name.jsonl data/massive/exp1_N4_desc.jsonl
python3 eval/run_fixed.py data/massive/exp1_N8_name.jsonl data/massive/exp1_N8_desc.jsonl
python3 eval/run_fixed.py data/massive/exp1_N12_name.jsonl data/massive/exp1_N12_desc.jsonl
python3 eval/run_fixed.py data/massive/exp1_N16_name.jsonl data/massive/exp1_N16_desc.jsonl
python3 eval/run_fixed.py data/massive/exp1_N20_name.jsonl data/massive/exp1_N20_desc.jsonl
python3 eval/run_fixed.py data/massive/exp1_N26_name.jsonl data/massive/exp1_N26_desc.jsonl
python3 eval/run_fixed.py data/massive/exp1_twostage_stage1_name.jsonl data/massive/exp1_twostage_stage1_desc.jsonl
python3 eval/run_adaptive.py
python3 eval/run_exp2.py
python3 eval/run_fixed.py data/massive/exp3_*.jsonl
python3 eval/summarize_a.py
```

run_exp2送兩輪Q=1/4/8/16/32/64與同64題單題對照；固定只有兩題noul正例，所以整體準確度不能解讀成批次提升能力。
兩輪取較快延遲，準確度不重複計題。多段信心是組合指標，不能沿用單段門檻。
summarize_a只彙整已有輸出；EmoBank題未收錄時跳過exp4，不把缺資料當0分。

## 合成業務、否定句、注入

```bash
python3 jev-cli/jev eval data/synthetic/pilot.jsonl
python3 jev-cli/jev eval data/synthetic/business.jsonl
python3 jev-cli/jev eval data/synthetic/hard.jsonl
python3 jev-cli/jev eval data/synthetic/probe.jsonl
python3 eval/negation_zh.py
python3 eval/negation_en.py
python3 eval/run_synthetic.py --injection
```

injection.json中網址、帳號與訊息均為原測試的合成內容，不是真實詐騙證據。只送文字給已備妥模型，不訪問其中網址、不執行其中指令。
第二輪防護條件同時改指令與JSON格式，不能歸因單一改動。run_synthetic不覆寫既有結果，請先自行歸檔local-results。
兩岸上游草稿的三句是整理時新寫的最小示例，尚未推論，不能視為已復現原錯例。

## RSS與未收錄語料

```bash
python3 eval/rebuild_rss.py
# 有既有XML快照時可不連網：
python3 eval/rebuild_rss.py --from-dir raw
python3 jev-cli/jev eval local-data/rss/eval/cna_choice_titlesum.jsonl
```

重建只從官方feed下載，manifest記錄來源、時間、類別及SHA-256。剔除跨分類重複、自由時報摘要移除頻道前綴並截200字。
當前RSS不保證原192/320題、順序或比例；原新聞文字未再發布。其他HF語料需另取原檔與授權，沒有完整B歷史重現包。
EmoBank、COLD、DBpedia雖有公開授權，這次也只保留統計；不要把未收錄當成授權禁止。
