# Taipei YouBike Data Platform — 設計規格

## 2026-09-23 現行方向：遠端PostgreSQL保存原始body

Andrew明確要求：建立遠端PostgreSQL，本機YouBike程式連線，把HTTP response body的原始bytes保存進去。requests的對應屬性為response.content；資料庫body欄位使用bytea。流程為官方YouBike API → 本機Python擷取 → 遠端PostgreSQL raw保存並commit → 後續解析／載入。平台未指定時由Codex先查證並推薦；目前以Neon Free提供建庫引導，尚未回報採用，不自行選用付費資源或部署到未知帳戶。遠端DB是當前Phase 1需求，不得以Phase 10尚未開始為由延後，也不代表整套pipeline已授權雲端部署。

下一步直接以Neon Free推薦提供建庫、SQL Editor唯讀驗證與Connect資訊取得引導，不等Andrew再次說引導；應用程式接入時再配置TLS與適當權限；之後才進正式raw表SQL、psycopg參數化寫入與新連線讀回驗證。密碼／完整DSN不貼進對話、不寫入文件。正式SQL／Python／tests仍Andrew實作。DB寫入失敗是否保留本機備援仍是獨立待決項，不阻擋平台確認與建庫引導。

上一回合的本機bytea獨立練習已撤回，不再派作或計入前置門檻。專用暫存PostgreSQL已停止，未刪除資料；既有venv可供遠端連線使用，空練習檔保留但不要求完成。未建立或連線遠端DB，沒有新增產品驗收；D1 0/4、Phase1 0/5、核心0/8、驗收0/36、本次／今日+0維持。原檔案保存／不連DB的YB1-1教學及其檔案專屬驗收已退休，正式raw schema／lineage／replay新契約待平台與故障政策釐清後同步，不可照舊指引派作。


版本：2026-09-23。依 Andrew 本次 project brief 重設專案；狀態是**設計完成、功能待實作**。本輪停在 spec／plan，不代寫 Python、SQL、dbt 或正式 tests。技術選擇中的數值是可驗證的工程預設，不是官方 SLA。

## 1. Goal 與 MVP scope

為 Junior／Career-switch Data Engineer portfolio 建立可靠、可重跑的資料平台，讓 analyst 直接查詢標準化且可追溯的 marts。重點是 ingestion、資料建模、多源整合、增量、冪等、品質與故障恢復；不以統計推論、預測或機器學習為驗收。

分兩個可獨立交付的層次：

- **Phase 1 最小垂直切片**：手動取得一次臺北 YouBike 2.0 JSON，原樣保存 raw，驗證及轉型後寫入 PostgreSQL，能查詢兩次快照並重播而不重複。只需 Python、HTTP client、PostgreSQL／psycopg、pytest。
- **本機 portfolio MVP**：Phases 1–5、7–9，共 8 個核心階段；加上每 5 分鐘 Airflow ingestion、dbt availability marts、Weather／Calendar enrichment、品質／quarantine／觀測、Docker Compose 與小型 Metabase demo。
- **Phase 6 條件式擴充**：官方歷史租借入口已找到；真實檔案可讀、粒度與欄位確認後才加入獨立 batch pipeline。未取得時保持「待來源驗證」，不得標完成，也不阻擋 snapshot MVP。
- **Phase 10 選配**：Cloud deployment，非 MVP 必要條件。S3、RDS、EC2 或 GCP 產品在量測及帳戶／費用確認後再選。

首版不加入 Spark、Hadoop、Kafka、Flink、Kubernetes、Terraform、ML、預測、自製查詢 API 或複雜前端。Metabase 僅證明 marts 可用；履歷只描述實際完成且有證據的功能。

## 2. Architecture 與責任

```text
Phase 1
YouBike API → 本機Python fetch → 遠端PostgreSQL raw bytes（bytea）＋metadata／commit
                              ↓ validate / normalize
                         PostgreSQL station_snapshot → SQL 驗收

本機 MVP（逐階段增加）
YouBike / Weather / Calendar → 各自 Python ingestion → raw files
                                                  ↓ PostgreSQL landing tables
                                                  ↓ dbt staging
                                                  ↓ intermediate mapping / hourly integration
                                                  ↓ analytics marts → Metabase
Airflow：排程、有限 retry、相依順序與 run 狀態
Docker Compose：Phase 8 重建整個本機環境
Historical rentals：Phase 6 驗證來源後走獨立 batch，不混成 snapshot
```

收到 body 後**先 save_raw，再 validate_schema**。原稿先驗 schema 再存 raw 會失去 drift 的錯誤證據，因此調整順序。raw 寫入失敗不得繼續載入 DB；無 HTTP body 時只保存錯誤 metadata，不虛構原始檔。Phase 1 不引入通用 connector、ORM、訊息佇列或多層 class framework。

Phase 2 排程只包裝已可手動執行的步驟；Phase 3 才接 dbt。Airflow metadata DB、warehouse 與 Metabase metadata 分開配置；BI 角色唯讀 marts。Phase 8 的 dbt 是任務執行環境，不是需要長駐的伺服器。Phase 1依最新要求連線遠端PostgreSQL；本機DB容器不作當前替代交付。

## 3. 來源事實、假設與待核實項

查證日：2026-09-23；來源連結見文末。公開資料查證不等於已建立 ingestion。

| 來源 | 已查證 | 專案決策／待驗證 |
|---|---|---|
| 臺北 YouBike 2.0 即時 | 官方列每 1 分鐘更新；JSON current snapshot；欄位含 Quantity、available_rent_bikes、available_return_bikes | 每 5 分鐘採樣是工程設定；不是全量租借事件。來源可用性、延遲與時間欄位需保存樣本驗證 |
| 臺北 YouBike 2.0 租借紀錄 | 官方提供月份檔案索引，更新不定期；備註列借還時間／站點、時長、車種、日期 | 真正月檔可達性、CSV 編碼、覆蓋期、去識別化與 ID 待驗證；不假設每天有新檔 |
| CWA 氣象 | 官方有測站觀測欄位規格 | 使用 O-A0001-001 為候選；下載方式／授權、站點與時間覆蓋在 Phase 4 確認。不要保存或展示 API key |
| 行政機關辦公日曆 | 官方提供 CSV；上班／放假日與備註 | 表示政府辦公日，不等於所有產業休假；支援補班日，假日名稱只取有來源的備註 |

### 3.1 Phase 1 欄位映射

endpoint：`https://tcgbusfs.blob.core.windows.net/dotapp/youbike/v2/youbike_immediate.json`。

| 原始欄位 | 標準欄位 | 解析契約 |
|---|---|---|
| sno | station_id | 非空文字，保留前導零，不轉整數 |
| sna / sarea | station_name / area | 非空文字，保留來源名稱 |
| latitude / longitude | latitude / longitude | 有限數值；緯度 -90～90、經度 -180～180；臺北範圍異常另作警示，不憑名稱裁切資料 |
| Quantity | capacity | 非負整數，拒絕 bool／小數；大小寫須精確，不默默把 quantity 當 alias |
| available_rent_bikes | available_bikes | 非負整數 |
| available_return_bikes | available_docks | 非負整數 |
| act | station_active | 僅字串 0／1 → false／true；其他值拒絕 |
| srcUpdateTime | source_update_time | 必填、可解析來源時間；來源未含 offset 時按 Asia/Taipei 解讀並在 manifest 註記假設 |
| mday / infoTime / infoDate / updateTime | raw 保留 | 不與 srcUpdateTime 混同；未核實語意前不任選為事件時間 |

counts 若來源採十進位整數字串，僅接受完整非負整數字面值，不能四捨五入或用真值轉型。JSON body 須為非空 array，每列 object。required 欄位缺失、非法型別或批內 station_id 重複，Phase 1 整批失敗。額外欄位保存在 raw 並記錄 schema warning，不能自動改欄位映射；必要欄位改名／移除一律停止 typed load。

**不設 bikes + docks = capacity 的硬性等式**；三欄各自有效不代表必定相加一致。停用站仍保留 station_active=false，不把站點消失當成零車位或刪站。

### 3.2 三種時間與 snapshot grain

- `observed_at`：本次採樣的邏輯時間，初次 fetch 前固定為 aware UTC。重播必須沿用 raw manifest 值；不是租借發生時間。
- `fetched_at`：收到 body 的實際 aware UTC 時间。
- `source_update_time`：source 宣稱的更新時間，解析後存 aware UTC；原字串仍在 raw。來源時區未有明確證據前，Asia/Taipei 是已標明的工程假設，樣本檢查若矛盾就停止而非悄悄轉換。
- `ingested_at`：首次成功載入 DB 的時間，replay 不覆寫。

Phase 2 observed_at 對齊 5 分鐘排程 slot，fetched_at 保留真實取得時間。只有完整 HTTP 200、成功 manifest 與 checksum 通過的 artifact 才能 replay；HTTP 失敗或未完成 body 只屬 attempt 證據，可在下一次執行有限重新 fetch。Realtime catchup 關閉；過期 slot 沒有保存 raw 就記 missing，不能拿現在 snapshot 填成過去觀測。錯過的 realtime 時段不能從 current API 重建。

## 4. Database schema（設計表，不是已建立 DDL）

### 4.1 Phase 1：一張表＋本機 raw

`landing.station_snapshot`：一列 = 一站 × 一次採樣。PRIMARY KEY `(station_id, observed_at)`；不需要先拆 station dimension。

| 欄位 | PostgreSQL 型別 | 約束／用途 |
|---|---|---|
| station_id | text | NOT NULL，非空，PK part |
| observed_at | timestamptz | NOT NULL，PK part |
| station_name / area | text | NOT NULL，非空 |
| latitude / longitude | double precision | NOT NULL，有限且通過地理範圍檢查 |
| capacity / available_bikes / available_docks | integer | NOT NULL，>=0 |
| station_active | boolean | NOT NULL |
| source_update_time / fetched_at / ingested_at | timestamptz | NOT NULL，各自時間不可混用 |
| pipeline_run_id | uuid | NOT NULL，指向 raw manifest |
| raw_object_path | text | NOT NULL，相對 raw 根目錄的路徑，不保存私人絕對路徑 |
| raw_sha256 | char(64) | NOT NULL，完整 body checksum |

以 PK 支援 station＋時間區間查询；全站時間掃描的額外索引待 query plan／實測再加。設定使用新專案獨立 DSN 與 test DB，不讀 simulate_trading/.env。

raw 目錄 `data/raw/youbike/<UTC-date>/<run_id>/` 下每次請求建立獨立 `attempts/<attempt_id>/response.body` 與 attempt metadata；只有完整 HTTP 200 才可在 run 根目錄原子寫入 `manifest.json`，body_path 指向該成功 attempt。先寫同 filesystem 暫存檔再 rename，manifest 最後才宣告 artifact 可用。失敗、截斷或 body 已落地但 manifest 前 crash 的 attempt 保留且不重播，下次建立新 attempt，不覆寫舊 body。Phase 1 同 run 限單 writer；Phase 2 再加跨程序鎖／slot 排他保護。成功 manifest 已存在則校驗 run_id、observed_at 與輸入及 body checksum；任何不一致拒絕，不重新 fetch 覆蓋。失敗 attempt 的 run_id／observed_at 也必須與重試輸入一致。body 保留原始 bytes，JSONB 不能替代它。

manifest schema：`manifest_version=1`、`source=taipei_youbike_v2`、`run_id`、`observed_at`、`fetched_at`、`source_url`、`http_status`、`content_type`、`body_path`、`body_sha256`、`byte_count`、`source_timezone_assumption=Asia/Taipei`。沒有 body 的網路錯誤記獨立 attempt log，不建立成功 manifest。raw 與 DB 不是同一 transaction：允許 raw 已存在但尚未入庫，透過 replay 恢復。

### 4.2 Idempotency 與失敗邊界

Phase 1 一批資料先完整驗證，再於單一 DB transaction 寫入。相同鍵、相同標準化 source 欄位為 no-op；相同鍵不同 source 欄位為 conflict，整批 rollback。判定相同時不比較新執行的 run_id／ingested_at，也不能只用整份 body hash 判定單列。批內重複 station_id 一律拒絕，不偷偷選最後一列。

同 raw 重播只增加獨立的 attempt log，不增加有效 snapshot 或更新既有 lineage。下一次採樣即使 source_update_time 未改仍是新 observed_at。DB 斷線／commit 回應遺失時 raw 保留，重播後不得產生第二效果。這是冪等結果，不宣稱跨 filesystem／DB 的 exactly-once transaction。

Realtime endpoint 每次可能傳完整站點集合；「增量」指 append 新採樣歷史，不承諾來源支援只抓變動資料。Phase 1 先不實作自動 retry，失敗非零退出；Phase 2 加有限 retry。

### 4.3 後续 schema 與 grain

| Phase | Table／model | Grain 與關鍵欄位 |
|---|---|---|
| 2 | ops.pipeline_runs | run_id；source、scheduled_at、status、started_at、finished_at、inserted/skipped/rejected count、duration、retry_count、error_code；status 僅 running/succeeded/failed/missing |
| 3 | stg_youbike_snapshot | 同 snapshot PK；統一命名／型別／null／重複政策，保留 lineage |
| 3 | int_station_hourly_availability | station_id × UTC hour；sample_count、avg/min/max bikes、avg docks、coverage |
| 3 | mart_station_hourly | 同 station-hour；availability＋quality／freshness，先不提供 rental_count |
| 4 | landing.weather_observation / stg_weather | weather_station_id × observation_time；temperature、humidity、wind_speed、pressure、precipitation 原語意及單位 |
| 4 | int_station_weather_mapping | bike_station_id × effective_from；weather_station_id、distance_km、effective_to、mapping_version；有效期不得重疊 |
| 5 | dim_date | local_date PK；weekday、is_weekend、is_holiday、holiday_name、is_workday、year/month/quarter、source_version |
| 6 | landing.rental_file / stg_rental | artifact_id＋source_row 作技術定位；沒有官方 trip ID 時不能用全欄 hash 任意去重真實重複旅次 |
| 6 | mart_daily_usage | local_date × station_id；rentals 按借出時間／站、returns 按歸還時間／站分別聚合後 join，避免乘積 |
| 6 | mart_station_flow | origin_id × destination_id × rental local_date；僅在有 OD 配對及穩定 station mapping 時提供 trip_count |
| 7 | ops.quarantine_records | artifact_id＋source_row＋rule_version；raw reference、error_type、error_message、run_id、ingestion_time |

Phase 3 可全量處理第一個小 fixture，正式驗收需具備 incremental model：只選新增 ingestion 批次，重新算所有受影響 station-hour；保留 watermark 邊界重疊＋冪等 merge 或 committed batch ledger，不能單用 observed_at > max 漏 late arrivals。checkpoint 只在模型與品質通過後前進；失敗不得把部分新結果呈現為完成。初版 mart 可先建候選表、驗證後 transaction 替換受影響區間，不做通用發布平台。

availability 平均是已收到採樣的簡單平均，不是完整時間加權平均。小時區間為 UTC `[hour,hour+1h)`，台北顯示轉 Asia/Taipei。5 分鐘完整小時預期 12 slots；未滿小時／起始收集不足需標 partial；source stale 另外呈現，不因採樣數足夠就宣稱新鮮。missing slot 不補 0、不前填。

Weather join 在每個 station-hour 至多匹配一個測站及一個 hour-level 結果。初版候選為最近有資格測站，距離最多 20km；nearest-distance tie 用 weather_station_id 排序，無符合則 NULL＋unmatched。觀測用該小時結束前最新一筆，最大 age 90 分鐘；距離／age 是待 Phase 4 實測校準的工程預設。mapping 帶版本與有效期，站點搬遷需重算而非改寫歷史。驗收 join 前後 station-hour 筆數不膨脹。

CWA 累積降水不得直接 SUM；先按官方語意處理日重置、缺值與異常，只有取得可驗證的區間降水才提供 rainfall_hourly／daily total。否則保存 rainfall_daily_cumulative 並標示口徑，不假稱小時雨量。不同天的累積值不可跨午夜直接相減。

Calendar 以台北當地日期 join。weekday ISO 1–7、weekend 為六日；政府放假與補班分開。is_rush_hour 在 station-hour 推導，展示預設為 workday 的 07:00–09:00 及 17:00–19:00（半開區間），不是 dim_date 的單一布林。

Historical rental 先保存檔案版本＋checksum；同檔同版重跑 skip/replay，新版本重建受影響月份／分區並處理刪列。不以 checksum 大小判新舊。站名不能直接當永久 ID：另建具有效期的 alias 對照，未知保持 unmatched。avg_duration 只對合法、有時長的借出旅次取平均，列分母及排除數。租借未接入時 count 欄位不提供；接入後缺批用 NULL／unavailable，只有確認資料完整的零活動才為 0。

## 5. Repository structure（依 phase 漸進建立）

```text
taipei-youbike-data-platform/
  README.md
  docs/platform_spec.md           本次建立：產品／資料契約
  docs/phase1_plan.md             本次建立：實作計画／驗收
  docs/project_flow.html          本次建立：設計資料流
  docs/adr.md                     本次建立：決策與取捨
  docs/engineering_challenges_log.md  本次建立：後續累積筆記入口
  src/extract/youbike.py          本次只建空檔：YB1-1
  tests/unit/test_youbike_extract.py  本次只建空檔：YB1-1
  src/validation/                 YB1-2 開始才建
  src/load/                      YB1-4 開始才建
  sql/                           YB1-3 schema 及後續驗收查詢
  tests/integration/             YB1-3 起逐片建立
  data/raw/                      真正擷取時建立，gitignored
  dags/                          Phase 2；Weather/Calendar/Rental 各自在其 phase 增加
  dbt/models/{staging,intermediate,marts}/   Phase 3
  dbt/tests/                     Phase 3
  docker/、docker-compose.yml    Phase 8
  requirements.txt              YB1-1 開始時選版本並建立，不先虛構安裝狀態
  .github/workflows/             後續選配 CI，非 Phase 1
```

目錄目前只有設計文件與當前切片空檔；樹中的後續項不是已實作功能。不一次建立未用的 models／utils framework。Python／SQL／dbt／正式 tests 由 Andrew 填寫；Codex 建檔、文件／HTML、安全驗證。

## 6. Technical risks 與延後項

| 風險 | 對策／驗收位置 |
|---|---|
| API 中斷或錯過 slot | Phase 1 有 timeout／失敗輸出；Phase 2 有限 retry，缺歷史不得回填目前值 |
| schema drift、metadata 與 live 名稱不一致 | raw-first；固定 Quantity 等 mapping；缺必要欄位 fail closed，Phase 7 故障 fixture |
| 時區／stale source | 分離四種時間；aware UTC；顯示 source age，樣本核對無 offset 的假設 |
| 假 rental inference | snapshot 只表示供給；rental／return／OD 只用已核實交易來源 |
| 歷史月檔過大或無穩定 ID | 先一檔量測 bytes/rows/memory；streaming、checksum、分區替換；不 hash 去重合法同值旅次 |
| station 搬遷／改名、weather fanout | ID 作鍵，alias/mapping 版本化；unmatched 保留，驗證 grain |
| 氣象累積／缺值污染 | 依 CWA 字典轉型；累積雨量不相加；缺資料不補零 |
| raw 成長／DB 查詢變慢 | 量測每天約 N站×288樣本；保存實際 bytes/rows、磁碟預算；先索引，量測後才 partition／object storage |
| Airflow 過早耗費環境時間 | Phase 1 CLI 先跑通；Phase 2 才 orchestration；Compose 全棧 Phase 8 |

可延後：SCD2 全站維度、PostGIS、全站內插天氣、通用 ingestion framework、CDC、即時串流、分散式處理、自動接受 schema evolution、外部 Slack／Discord／Email 通知、CI/CD 部署與 IaC。Phase 7 先做本機可查的 alert event；實際外送待明确授權。基本 validation、raw preservation、PK／transaction 不能一起延到 Phase 7。

教學方式（2026-09-23）：引導先清楚描述任務，直接給資料來源URL、HTTP方法／認證／參數、資料樣貌及輸入輸出位置，再逐項列完成任務所需技術、用途及對應的不同情境實際語法短例；不以流程或契約清單取代技術教學，數量依當前任務需要；不用虛擬碼，不以換名或拼接方式提供專案完整解答。此為教學交付變更，產品契約與驗收維持；正式實作由 Andrew 完成。

Phase 1 的計畫、逐項 acceptance 與第一步見 [Phase 1 plan](phase1_plan.md)；完整階段入口見 [學習計畫](../../job_search/de_transition_plan.md)。

## 7. 全案時程與進度政策

逐日唯一主表為 [D1–D75 學習計畫](../../job_search/de_transition_plan.md)，Dashboard 由此產生；本節只規定時程口徑，不變更上述功能／資料契約。每天以 outcome、驗收證據及狀態追蹤，不以文件改版或經過天數增加學習完成數。現行核心0/8、Phase 1為0/5、active YB1-1，本次／今日學習驗收+0。

- 2026-09-23起採每日互動及每次任務驗收後todo回報，顯示當日片內進度、固定分母、本次／今日增量與超前／延遲學習日；完整算法及日期快照見[學習計畫](../../job_search/de_transition_plan.md)。日內只把今天以前未完成目標算逾期，今日尚未到期不提前判延遲；不新增外部通知。
- 核心 MVP：55學習日＝45工作＋10緩衝；含8個核心Phase及其後正式review、修正、重驗與交付，11週／330h基準。
- 本機含條件式歷史租借：65日＝53工作＋12緩衝，13週／390h；Phase 6先驗證真實來源，未通過則延後、不標完成。若納入交付，須一起驗收及review。
- 全案再含選配雲端：75日＝62工作＋13緩衝，15週／450h；Phase 10需帳戶／成本／權限授權，未授權不執行雲端部署。
- 每日6～8小時、每週5天是沿用的規劃假設，工時以6h／日計；已確認2026-09-23為D1，依台北日期及週一至週五計，未另扣國定假日／請假；不是完工保證。Phase 1保持7日（5工作＋2緩衝），D7以實測校準已排好的全案。
- Phase 1–10依次預算為7／6／8／7／4／10（條件式）／7／6／5／10（選配）日；另列本機正式review／修正／重驗5日。核心8個Phase均有驗收證據才進正式review；Phase 6及10不構成核心MVP門檻。

## 8. 官方參考

- [YouBike 即時資料集與欄位](https://data.gov.tw/dataset/137993)
- [即時 JSON](https://tcgbusfs.blob.core.windows.net/dotapp/youbike/v2/youbike_immediate.json)
- [YouBike 歷史租借資料集](https://data.gov.tw/dataset/150635)
- [CWA 觀測資料說明](https://opendata.cwa.gov.tw/opendatadoc/Observation/O-A0001-001.pdf)
- [行政機關辦公日曆](https://data.gov.tw/dataset/14718)

## Raw保存變更提案（待故障政策決定）

2026-09-23 raw保存改版待定：Andrew要求將response.body存入DB。方向為PostgreSQL保存原始bytes，技術建議body欄位使用bytea，來源／時間／狀態／checksum等metadata同存；raw獨立commit後才解析與載入station_snapshot。待Andrew選定DB寫入失敗時採本機暫存補入，或DB-only並接受未落地body可能遺失。此項尚未完成契約切換；原YB1-1檔案保存／不連DB教學暫停派作，不要求依舊方式新增實作。正式SQL／Python／tests仍Andrew實作，未建立或改動DB。下一步先確認遠端平台並引導建庫與連線；故障保存政策另行確認後同步raw表schema、lineage、重播、失敗測試及Phase1順序；固定完成數不變，新增DB前置的工期須重估，不能直接承諾D1原工時。
