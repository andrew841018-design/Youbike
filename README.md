# Taipei YouBike Data Platform

建立可追溯、可重跑的 YouBike／Weather／Calendar 資料平台，讓 analyst 使用 analytics-ready marts。**Phase 1已完成，Airflow排程與有限重試已有真實運行證據；跨程序排他與後續整合仍在實作。**

- [MVP、architecture、schema、repository、風險與延後項](docs/platform_spec.md)
- [Phase 1 實作計畫、每日規劃與驗收](docs/phase1_plan.md)
- [專案資料流](docs/project_flow.html)
- [D1–D75 完整逐日時程／進度](../job_search/de_transition_plan.md) · [Dashboard](../job_search/de_transition_daily_dashboard.html)
- [架構決策](docs/adr.md) · [工程筆記](docs/engineering_challenges_log.md)

2026-10-08：核心Phase 1/8、核心驗收7/36；Phase 1 5/5、Phase 2 2/4，active D11／YB2-3排他與raw重播。D10實際故障run首次加4次重試後failed，5份attempt log與退避證據已核對；正常來源恢復後raw 1列／1813站入庫。Python／SQL／dbt／正式tests由Andrew實作，Codex負責建檔、文件紀錄及範圍內驗證。原始bytes保存於本機PostgreSQL（DB-only，未commit回應可能遺失）。

全案基準：核心 MVP 含 review／修正／重驗55學習日（45工作＋10緩衝，11週／330h）；加條件式歷史租借65日（53工作＋12緩衝，13週／390h）；再加選配雲端75日（62工作＋13緩衝，15週／450h）。每日6～8h、每週5天是規劃假設，工時以6h計，D1已確認為2026-09-23；每天列的是目標與證據要求，不代表已完成。

snapshot變動不能當作rental transaction。歷史租借來源已有官方入口，但尚待月檔及站點mapping驗證。本機PostgreSQL資料位於WD_BLACK；Airflow以30分鐘排程採樣、catchup=False、max_active_runs=1。Cloud部署仍為後期選配；未新增外送通知或遠端資源。開發／測試庫及raw_bytes／response已有驗證證據。

本機文件維護：於工作區根目錄使用 `python3 ops/youbike_docs.py build` 與 `python3 ops/youbike_docs.py check`。這是 Codex 文件工具，不能算產品正式測試或 Andrew 的實作成果。
