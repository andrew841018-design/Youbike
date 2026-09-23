# Architecture decisions

2026-09-23，狀態：本次規劃採用，待實作與量測。

| ID | 決策 | 理由與代價 | 重新考慮條件 |
|---|---|---|---|
| ADR-001 | Phase 1 Python＋PostgreSQL，不加入 Spark／Kafka | 單機可先測得工作量；少運維。沒有分散式吞吐保證 | 固定硬體下 ETL、storage、query latency 超過明示預算且索引／批次優化不足 |
| ADR-002 | Raw bytes 先保存，typed data 再載入 | drift／失敗可追查；需要管理磁碟與 replay | raw size 量測後再選 object storage，不先加雲 |
| ADR-003 | station_id＋採樣 observed_at 作 snapshot key | 保留每次採樣；source 更新時間另存 | 多來源站點時加入 source identity；不能靜默改舊鍵 |
| ADR-004 | Phase 1 單表／整批 transaction | 最少可用結構，錯列不污染資料；一列錯可阻擋整批 | Phase 7 quarantine 引入可觀測的 rejected 狀態與明確發布門檻 |
| ADR-005 | Airflow Phase 2、dbt Phase 3 | 先證明手動 pipeline，再解決排程／模型管理 | 有實測需求再擴部署架構 |
| ADR-006 | 本機 MVP 與條件式歷史租借／雲端分開 | snapshot availability 可獨立交付；不拿缺資料假裝零租借 | 月檔驗證通過，或另有明確 cloud 授權 |
| ADR-007 | Metabase 作 downstream demo | 避免自製 API／UI 擴張 scope；只展示可用 marts | 下游真有 API consumer，再定契約 |

沒有 measurement 前，不能把「PostgreSQL 足夠」寫成已驗證效能結論，只是目前架構假設。

## ADR-008 草案：raw body移入PostgreSQL

2026-09-23 raw保存改版待定：Andrew要求將response.body存入DB。方向為PostgreSQL保存原始bytes，技術建議body欄位使用bytea，來源／時間／狀態／checksum等metadata同存；raw獨立commit後才解析與載入station_snapshot。待Andrew選定DB寫入失敗時採本機暫存補入，或DB-only並接受未落地body可能遺失。此項尚未完成契約切換；原YB1-1檔案保存／不連DB教學暫停派作，不要求依舊方式新增實作。正式SQL／Python／tests仍Andrew實作，未建立或改動DB。下一步先定故障保存政策，再一次同步raw表schema、lineage、重播、失敗測試及Phase1順序；固定完成數不變，新增DB前置的工期須重估，不能直接承諾D1原工時。

## 2026-09-23 現行方向：遠端PostgreSQL保存原始body

Andrew明確要求：建立遠端PostgreSQL，本機YouBike程式連線，把HTTP response body的原始bytes保存進去。requests的對應屬性為response.content；資料庫body欄位使用bytea。流程為官方YouBike API → 本機Python擷取 → 遠端PostgreSQL raw保存並commit → 後續解析／載入。平台未指定時由Codex先查證並推薦；目前以Neon Free提供建庫引導，尚未回報採用，不自行選用付費資源或部署到未知帳戶。遠端DB是當前Phase 1需求，不得以Phase 10尚未開始為由延後，也不代表整套pipeline已授權雲端部署。

下一步直接以Neon Free推薦提供建庫、SQL Editor唯讀驗證與Connect資訊取得引導，不等Andrew再次說引導；應用程式接入時再配置TLS與適當權限；之後才進正式raw表SQL、psycopg參數化寫入與新連線讀回驗證。密碼／完整DSN不貼進對話、不寫入文件。正式SQL／Python／tests仍Andrew實作。DB寫入失敗是否保留本機備援仍是獨立待決項，不阻擋平台確認與建庫引導。

上一回合的本機bytea獨立練習已撤回，不再派作或計入前置門檻。專用暫存PostgreSQL已停止，未刪除資料；既有venv可供遠端連線使用，空練習檔保留但不要求完成。未建立或連線遠端DB，沒有新增產品驗收；D1 0/4、Phase1 0/5、核心0/8、驗收0/36、本次／今日+0維持。原檔案保存／不連DB的YB1-1教學及其檔案專屬驗收已退休，正式raw schema／lineage／replay新契約待平台與故障政策釐清後同步，不可照舊指引派作。
