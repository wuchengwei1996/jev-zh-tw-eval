# 資料來源與再發布決定

核對日：2026-10-04。只對列明的公開卡片作來源核對，未把鏡像的授權欄當作原文權利證明。
本 repo 的文件與結果採 CC BY 4.0；第三方內容保留原授權，不被 MIT 或文件授權覆蓋。

| 資料集與 URL | 授權核對 | 收錄 | 理由 |
|---|---|---|---|
| [Amazon MASSIVE 1.1](https://huggingface.co/datasets/AmazonScience/massive)；[官方下載](https://amazon-massive-nlu-dataset.s3.amazonaws.com/amazon-massive-dataset-1.1.tar.gz) | 官方 CC BY 4.0 | 是，data/massive/ | 三語 test 語句與人工標籤、固定抽樣題、選項表，允許附署名再發布 |
| [MTEB MASSIVE intent 鏡像](https://huggingface.co/datasets/mteb/amazon_massive_intent) | 鏡像 Apache 2.0；語句依原始 CC BY 4.0 | 是，上列檔案實際來源 | 使用 test/zh-TW.json.gz、zh-CN.json.gz、en.json.gz；不把鏡像授權改套原內容 |
| 自製中英合成題 | 原創題目 CC BY 4.0 | 是，data/synthetic/ | 30 題 pilot、77 題業務、52 題困難、24 題探針、兩組配對與 context；非真實客戶或新聞 |
| [EmoBank](https://github.com/JULIELab/EmoBank) | CC BY-SA 4.0 | 否，只保留133句的彙總 | 可依原授權分享；本次縮小資料包，不另發布需同授權的衍生語料 |
| [中央社 RSS](https://feeds.feedburner.com/rsscna/politics) | 內容屬中央社；再發布條款未查明 | 否，只有重建程式 | 所有新聞原文、標題、摘要、XML、逐題錯例均排除；由 feed 決定標準類別 |
| [自由時報 RSS](https://news.ltn.com.tw/rss/politics.xml) | 內容屬自由時報；再發布條款未查明 | 否，只有重建程式 | 同上；剝除摘要開頭頻道標籤，避免洩漏答案 |
| [ChnSentiCorp](https://huggingface.co/datasets/lansinuote/ChnSentiCorp) | 卡片未列授權；原始研究語料權利未查明 | 否 | 不能確認再發布 |
| [Amazon Reviews Multi](https://huggingface.co/datasets/mteb/amazon_reviews_multi) | 鏡像卡片未列授權；原資料非商業研究條款未完整確認 | 否 | 不把研究用途當作可公開授權 |
| [yf_dianping](https://huggingface.co/datasets/dirtycomputer/yf_dianping) | 卡片未列授權 | 否 | 不能確認再發布 |
| [ToxiCN](https://huggingface.co/datasets/JunyuLu/ToxiCN) | 卡片明列 CC BY-NC-ND 4.0 | 否 | 非商業及禁止改作；不重新包裝語料納入通用開源資料包 |
| [COLD](https://huggingface.co/datasets/thu-coai/cold) | 卡片 Apache 2.0 | 否 | 授權允許分享；本次只收 MASSIVE 與原創題，減少額外原文與授權檔 |
| [UCI SMS Spam HF 鏡像](https://huggingface.co/datasets/ucirvine/sms_spam) | 卡片 unknown；未逐份對照原始檔案授權 | 否 | 不依 UCI 平台通則推定鏡像內容權利 |
| [AG News](https://huggingface.co/datasets/fancyzhx/ag_news) | unknown | 否 | 新聞原文及權利未確認 |
| [Yahoo Answers Topics](https://huggingface.co/datasets/community-datasets/yahoo_answers_topics) | unknown | 否 | 問答原文及權利未確認 |
| [DBpedia 14](https://huggingface.co/datasets/fancyzhx/dbpedia_14) | 卡片 CC BY-SA 3.0，正文另列 GFDL | 否 | 可依相應授權分享；本次不收需另處理同授權與 GFDL 的資料 |
| [THUCNewsText](https://huggingface.co/datasets/oyxy2019/THUCNewsText) | 卡片未列授權；源自新聞 | 否 | 不收任何新聞原文，原權利未確認 |
| [Plumb decisions](https://huggingface.co/datasets/crh225/plumb-decisions) | 卡片 Apache 2.0 | 否 | test 被作者用於校準，131題不是完全未見的獨立保留集；本次只留既有摘要 |
| [JevBench](https://github.com/fstandhartinger/jevbench) | README：程式與72題original public為MIT；其他來源另依原授權 | 否 | 不把整套231題一律視為MIT；只引用既有準確度，不複製題目 |

## MASSIVE 必要署名與變更

Amazon MASSIVE, FitzGerald et al. (2022), *MASSIVE: A 1M-Example Multilingual Natural Language Understanding Dataset with 51 Typologically-Diverse Languages*。
內容由 Amazon 釋出，依 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) 使用；提供內容不代表背書，無保證。
本 repo 把來源欄位整理成 id/label/text/lang，seed=42 抽樣及建立干擾選項；保留來源 id 和人工標籤。
繁中 criteria 為測試前固定的 AI 撰寫說明；不是人工標準答案。
英文指示中的角色名詞已通用化成 speaker；合成業務題ag02移除家目錄前綴，人工標籤不變；公開題面與原實驗存在字詞差異。
原始三語 test 各2974列，60類選項池、test實際59類，18個scenario；詳細抽樣方法見 eval/build_massive.py。

## RSS 重建範圍

eval/rebuild_rss.py 從官方 feed 重新下載，記錄來源URL、抓取時間、來源類別及內容雜湊。
輸出一律放 local-data/rss/（git 忽略），不把原文帶進公開檔案。
RSS 隨時間變動，不能完全重現2026-10-03的192／320則快照。
原標籤採發布者頻道，不能當成純語意相關性的無爭議答案。
未收錄來源要另行取得資料與授權，repo 不提供不明授權語料的自動抓取。
