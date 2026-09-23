# Taipei YouBike Data Platform

建立可追溯、可重跑的 YouBike／Weather／Calendar 資料平台，讓 analyst 使用 analytics-ready marts。**目前只有設計文件與當前切片空檔，沒有已可執行的 pipeline。**

- [MVP、architecture、schema、repository、風險與延後項](docs/platform_spec.md)
- [Phase 1 實作計畫、每日規劃與驗收](docs/phase1_plan.md)
- [專案資料流](docs/project_flow.html)
- [D1–D75 完整逐日時程／進度](../job_search/de_transition_plan.md) · [Dashboard](../job_search/de_transition_daily_dashboard.html)
- [架構決策](docs/adr.md) · [工程筆記](docs/engineering_challenges_log.md)

核心 Phase 0/8，Phase 1 0/5，active YB1-1；本次文件交付不計學習完成。Python／SQL／dbt／正式 tests 由 Andrew 實作，Codex 負責建檔、文件／前端及安全驗證。先做手動 YouBike API → 本機Python → 遠端PostgreSQL raw bytes，不一次生成全專案。

全案基準：核心 MVP 含 review／修正／重驗55學習日（45工作＋10緩衝，11週／330h）；加條件式歷史租借65日（53工作＋12緩衝，13週／390h）；再加選配雲端75日（62工作＋13緩衝，15週／450h）。每日6～8h、每週5天是規劃假設，工時以6h計，未確認日曆起日；每天列的是目標與證據要求，不代表已完成。

snapshot 變動不能當作 rental transaction。歷史租借來源已有官方入口，但尚待月檔及站點 mapping 驗證。遠端PostgreSQL已是Phase 1需求，平台待定；整套Cloud部署仍為後期選配。未啟動排程、外送通知或遠端資源；誤建本機練習DB已停止。

本機文件維護：於工作區根目錄使用 `python3 ops/youbike_docs.py build` 與 `python3 ops/youbike_docs.py check`。這是 Codex 文件工具，不能算產品正式測試或 Andrew 的實作成果。
