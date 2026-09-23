# Phase 1 — YouBike API → PostgreSQL

## 2026-09-23 現行方向：遠端PostgreSQL保存原始body

Andrew明確要求：建立遠端PostgreSQL，本機YouBike程式連線，把HTTP response body的原始bytes保存進去。requests的對應屬性為response.content；資料庫body欄位使用bytea。流程為官方YouBike API → 本機Python擷取 → 遠端PostgreSQL raw保存並commit → 後續解析／載入。平台未指定時由Codex先查證並推薦；目前以Neon Free提供建庫引導，尚未回報採用，不自行選用付費資源或部署到未知帳戶。遠端DB是當前Phase 1需求，不得以Phase 10尚未開始為由延後，也不代表整套pipeline已授權雲端部署。

下一步直接以Neon Free推薦提供建庫、SQL Editor唯讀驗證與Connect資訊取得引導，不等Andrew再次說引導；應用程式接入時再配置TLS與適當權限；之後才進正式raw表SQL、psycopg參數化寫入與新連線讀回驗證。密碼／完整DSN不貼進對話、不寫入文件。正式SQL／Python／tests仍Andrew實作。DB寫入失敗是否保留本機備援仍是獨立待決項，不阻擋平台確認與建庫引導。

上一回合的本機bytea獨立練習已撤回，不再派作或計入前置門檻。專用暫存PostgreSQL已停止，未刪除資料；既有venv可供遠端連線使用，空練習檔保留但不要求完成。未建立或連線遠端DB，沒有新增產品驗收；D1 0/4、Phase1 0/5、核心0/8、驗收0/36、本次／今日+0維持。原檔案保存／不連DB的YB1-1教學及其檔案專屬驗收已退休，正式raw schema／lineage／replay新契約待平台與故障政策釐清後同步，不可照舊指引派作。


版本 2026-09-23；設計／驗收目標，尚未實作。依 [spec §1–4](platform_spec.md)。全局核心 Phase 0/8；Phase 1 子任務 0/5；active **YB1-1，原始擷取，第 1/5 項**。本次／今日學習驗收 +0；本次成果是新版教學引導與規則同步；完整 D1–D75 主排程與核心／延伸分支見 [全案學習計畫](../../job_search/de_transition_plan.md)。

## 固定子任務與相依

| ID | Outcome | Acceptance | 狀態 |
|---|---|---|---|
| YB1-1 | 一次 HTTP 擷取與 raw 保存 | 有界請求、原始 bytes／manifest 可追溯；raw-first；timeout／HTTP 錯誤可診斷；改存遠端DB，新契約待同步 | 目前，遠端建庫引導 |
| YB1-2 | 快照解析與驗證 | 精確欄位／型別／UTC；負數、缺欄、空 array、重複站點拒絕；Quantity 大小寫與額外欄位政策明確 | 未開始 |
| YB1-3 | PostgreSQL schema 與隔離 | 依 spec 建 station_snapshot、PK／約束；test DB 與私人 DB 隔離，合法／非法資料有正式測試 | 未開始 |
| YB1-4 | 冪等批次 load 與查詢 | 同 raw 重播 count 不變；新 observed_at 增加歷史；同鍵異值整批 rollback；可查兩次快照 | 未開始 |
| YB1-5 | 故障重播與證據交付 | timeout／壞 JSON／DB 失敗無假成功；raw 保留；commit 後重試無第二效果；真實樣本及手算小 fixture、README 限制完整 | 未開始 |

順序 YB1-1 → 2 → 3 → 4 → 5。每片由 Andrew 寫正式程式／tests，Codex 安全驗證後同步證據，再引導下一片。這不是要求本回合寫完整 pipeline。

每日與每次驗收後以todo回報，D1的YB1-1.A–D四項內部進度、完成證據及超前／延遲算法統一見[學習計畫](../../job_search/de_transition_plan.md)。片內完成不另增Phase切片分母；2026-09-23日內為按期0天，當日尚未到期，並非已完成D1。

## 每日規劃：Phase 1 七個學習日

沿用每天 6～8 小時、每週 5 天的先前規劃假設；本次不是重新承諾投入。以每日 6 小時：0.5h 看驗收、3h 實作、1.5h 測試除錯、1h 對帳紀錄；額外時間是緩衝。5 工作日＋2 緩衝日＝42h 基準，不保證當日通關。YB1-1 實測後校準。

| 學習日 | 對應 ID | 目標／證據 | 目標累積 |
|---|---|---|---|
| D1 | YB1-1 | mock HTTP 邊界＋一次有界真實 raw capture | 1/5 |
| D2 | YB1-2 | 正常／非法 fixture 與欄位映射證據 | 2/5 |
| D3 | YB1-3 | isolated schema／PK／constraints 驗收 | 3/5 |
| D4 | YB1-4 | 同 raw／新採樣／衝突，SQL count 對帳 | 4/5 |
| D5 | YB1-5 | 故障恢復與端到端 evidence、說明交付 | 5/5 |
| D6 | 緩衝 | 修缺口、重驗，未通過不增加完成數 | 5/5（目標） |
| D7 | 緩衝 | 量測並校準已排定的全案時程與 Phase 2 目標 | 5/5（目標） |

舊 BTC 的 60 日計畫已退出現行課程，保留歷史備份；不把新 scope 強塞到舊日曆。全案各 Phase 已有逐日目標與驗收證據規劃，詳見 [完整時程](../../job_search/de_transition_plan.md)。核心 MVP 含 review／修正／重驗為55學習日（45工作＋10緩衝，11週／330h基準）；納入條件式歷史租借為65日（53工作＋12緩衝，13週／390h），再納入選配雲端為75日（62工作＋13緩衝，15週／450h）。工時以6h／日、每週5天計；已確認2026-09-23為D1，依台北日期、週一至週五計算，未另扣國定假日／請假。來源／授權未就緒的延伸不阻擋核心MVP，也不算已完成。

## Phase 1 完整驗收案例

1. 小型 fixture 兩個不同 station、單 observed_at → 2 rows，每列可找到 raw checksum／manifest。
2. 同 raw 重播兩次 → 仍 2 rows，既有 ingested_at／lineage 不改。
3. 同兩站、下一 observed_at、source_update_time 不变 → 共 4 rows；不是按來源更新時間去掉新的採樣。
4. 同 station＋observed_at、不同 bike count → conflict，整批不更新；不可 blanket DO NOTHING。
5. missing sno、Quantity 負數／bool、無效 timestamp、批內 duplicate → 明確失敗、DB 增量 0、raw 可查。
6. bikes+docks 與 capacity 不相等，但每欄合法 → 不因未證實的等式拒絕。
7. HTTP timeout／503、空 response、破損 JSON → 非零失敗；收到的 body 先保留，沒收到 body 就只有錯誤 log。
8. DB 交易中斷 → 無部分寫入；raw 可 replay；commit 回應遺失重試後無重複結果。
9. 存檔時區為 aware UTC；顯示台北日界正確；不依執行主機 local timezone。
10. HTTP 503 body 已保存 → 手動同 run 再執行得到 200：失敗 attempt 保留，只有後者可 replay；body 寫完但 manifest 寫失敗也可由新 attempt 恢復。成功 manifest 的 run_id／observed_at 與輸入不符必須拒絕。
11. 一次官方真實樣本與 fixture 驗收分開，記 bytes、rows、耗時及來源更新時間；查詢能還原兩次採樣。不得把 mock PASS 當作 live integration PASS。

後續驗證命令（環境及測試建立後才可執行）：在專案根目錄 `python -m pytest tests/unit/test_youbike_extract.py -q` 驗 YB1-1；整個 Phase 1 使用 `python -m pytest tests/unit tests/integration -q`。Codex 執行安全驗證並紀錄實際 interpreter；目前沒有安裝新環境、沒有已通過的產品測試。

## 當前引導入口

依頁首遠端PostgreSQL要求，平台未指定時直接交付Neon Free推薦引導。舊檔案保存與本機bytea練習教學已撤回。正式入口仍為src/extract/youbike.py及tests/unit/test_youbike_extract.py；遠端DDL檔名待schema定案後由Codex建立，不派作sql/practice/raw_bytes.sql或tests/integration/test_raw_bytes_roundtrip.py。

## Neon Free遠端建庫引導（2026-09-23）

本輪只要求建庫、SQL Editor驗證與找到Connect資訊。這是查證後的教學推薦，尚未代建帳號或確認使用者採用。

1. Andrew開啟https://console.neon.tech/登入或註冊，使用Free。
2. New Project：名稱youbike，Region選AWS Asia Pacific (Singapore)，若能選Postgres版本則用16；只啟用Postgres。
3. 保留預設branch／database；目前官方為production／neondb，以console實際顯示為準。project名稱不是database名稱。
4. SQL Editor清除附帶sample SQL，執行SELECT current_database(), current_user, version();。這是唯讀環境診斷，成功不等於本機psycopg已連通。
5. Connect選同一branch／database；本輪單程序可關閉Connection pooling取得direct endpoint，保留TLS參數。只先找到設定，不將密碼或完整DSN貼進對話。下一片由Codex先建必要安全設定檔再引導本機連線。

所需概念：託管PostgreSQL由平台管理server；Project包含branch，branch包含database與role；DSN由帳號、密碼、host、port、database及TLS選項組成。之後才引導正式raw表SQL與psycopg參數化保存response.content，正式實作仍Andrew完成。

官方Free額度每project 0.5GB資料庫儲存、每月100CU-hours，無需信用卡。適合先手動寫入少量樣本；既有944391-byte樣本每5分鐘一份，未壓縮body約272MB/day，不能承諾長期免費保存。實際DB大小受壓縮與索引等影響，持續排程前量測容量並確認保留政策，不自動刪raw或升級。

來源：https://neon.com/pricing 、https://neon.com/docs/manage/projects 、https://neon.com/docs/introduction/regions 、https://neon.com/docs/get-started/signing-up 、https://neon.com/docs/connect/connect-from-any-app 。

進度仍D1 0/4、Phase1 0/5、核心0/8、驗收0/36，本次／今日+0。教學交付與文件同步不計建庫驗收。
