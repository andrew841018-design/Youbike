# 官方來源核對 — 2026-09-23

本次僅做公開唯讀查證，沒有部署 pipeline。catalog 存在與真正月檔可處理是不同證據。

- 即時：[官方 catalog](https://data.gov.tw/dataset/137993) 與 [JSON](https://tcgbusfs.blob.core.windows.net/dotapp/youbike/v2/youbike_immediate.json)。每 1 分鐘更新；實際 `Quantity` 為大寫 Q。本次讀到的單站例子為 capacity 28、可借 2、可還 25，故三欄不應套加總等式；例子是一次查證，不是固定 fixture 或目前所有站點狀態。無 offset 的時間採 Asia/Taipei 是工程假設，正式擷取仍需記原字串與核對來源時鐘。
- 歷史：[官方 catalog](https://data.gov.tw/dataset/150635) 列 fileinfo／fileURL 與月份欄位；不定期更新。工具未成功下載實際月份 CSV，所以 grain、ID、encoding、覆蓋期與資料改版尚未通過。Phase 6 不可因 catalog 找到就勾完成。
- 氣象：[CWA 官方欄位文件](https://opendata.cwa.gov.tw/opendatadoc/Observation/O-A0001-001.pdf)。O-A0001-001 為逐時候選，O-A0003-001 為 10 分鐘綜觀；Now/Precipitation 是當日累積，不能直接相加。特殊值依欄位規範處理，包含缺測、故障與雨跡等。採 WGS84 座標；尚未建立 live API 連線或取得私人憑證。
- 日曆：[行政機關辦公日曆](https://data.gov.tw/dataset/14718)。官方有年度 CSV；是否放假 0＝上班、2＝放假。週末、政府放假與專案 rush-hour 定義分開；不是民間勞動日曆保證。

YouBike catalog 標示免費及政府資料開放授權第 1 版；日後發布資料／成果需保留來源歸屬，參見 [資料開放授權](https://data.gov.tw/license)。本次未核实無限制 quota、所有歷史月份一致性或永久可用性。
