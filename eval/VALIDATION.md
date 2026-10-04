# 公開整理驗證狀態（2026-10-04）

此檔記載整理時的驗證，不是模型成績；沒有新增模型推論、付費請求、權重下載或遠端寫入。

| 檢查 | 狀態 | 範圍 |
|---|---|---|
| 原CLI測試77項 | blocked | 9項通過，68項因執行環境禁止本機socket綁定而無法完成；不是整套通過 |
| 通用設定測試 | passed | 3項：loopback不自啟、OLLAMA_URL與JEV_ENDPOINTS優先序、範例digest釘選 |
| 檔案read-back與離線完整性 | passed | eval/verify_release.py：73個非空檔案，語法／JSON／連結；2587有效題與200個N27拒絕；數字錨點 |
| 隱私與祕密掃描 | passed | 逐項grep：個人IP／路徑／主機帳號／email／祕密／占位皆0；gitleaks dir輸出no leaks found；掃描公開工作樹，git身分metadata依指定另保留 |
| 素材唯讀 | passed | 405個素材檔SHA-256比對無變更；記錄在公開repo外 |
| 獨立唯讀審查 | passed | 獨立審查檔案、數字、授權、個人資訊與腳本；指揮者抽查數字與命令；移除合成題家目錄前綴 |

原套件完整保留所有77項測試與斷言，只通用化主機名、測試環境隔離變數；新增3項不連線的通用設定測試。
要在允許loopback socket的環境驗整套，執行README中的unittest命令。未刪除、跳過或放寬受阻測試。

目前可完整重現的資料範圍為已收錄MASSIVE與合成題；RSS只可重抓當前快照，其他未收語料不能完整歷史重播。
JevBench README已讀；CONTRIBUTING路徑無法取得，尚不能確認接受規則或格式；上游草稿保留此限制。

RSS建題離線pilot：19個合成feed，發布者類別、跨feed重複剔除、摘要頻道前綴剝除通過；不是抓取歷史新聞或模型驗證。

公開A彙整腳本以既有原始數值在repo外暫存重算：exp1／exp2／exp3與原summary.json完全一致；缺EmoBank時只跳過exp4，沒有新增推論。
