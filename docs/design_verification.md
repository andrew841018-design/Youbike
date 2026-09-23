# 設計改版驗證 — 2026-09-23

- 交付範圍：七項設計輸出、Phase 1 五切片、十階段路線、規則／記憶／plan／兩份 HTML 同步。停止在規劃。
- 四個獨立 Codex 有界工作：source_check 官方來源；design_check 契約；sync_audit 現行入口／記憶；plan_acceptance 需求完整度。未執行尚未完成產品的正式 code review。
- 契約審查發現失敗 raw／成功 replay 混淆與 body-before-manifest crash 缺口；已改獨立 attempt、成功 manifest 門檻、身份／checksum 核對及恢復驗收，兩名設計 reviewer 重讀後無重要問題。
- python3 ops/youbike_docs.py check：PASS，兩 HTML 與 Markdown 一致、本機 links／anchors、固定五片、未完成狀態。
- python3 ops/market_research_docs.py check：PASS，舊命令已轉接 YouBike，不能再生 BTC 頁面。
- python3 ops/agent_rules.py verify：PASS。
- question_memory reindex／validate：OK，673 entries；九筆市場專用記憶 retired，新決策可索引，通用教學偏好保留。
- Browser：localhost server 綁定被 sandbox 阻擋；本機 file URL 被 browser URL policy 阻擋，未繞過。未完成瀏覽器視覺驗證，只完成靜態文件檢查；不可宣稱 screenshot QA 通過。
- 產品：未跑正式產品 tests，未啟動 DB／pipeline／Airflow，兩個 YB1-1 Python 檔為空。文件工具不是學習驗收。
- 保留：simulate_trading 原 Python／tests／Git／私人設定／DB、歷史學習成果。修改前文件精確備份在 ../../ops/state/youbike_redesign_20260923/before；hash manifest 在同層 manifest.json，恢復時先確認沒有更新的使用者修改，不能整批覆寫。

chain: partial-stopped-at-plan
