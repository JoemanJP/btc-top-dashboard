# BTC Top Dashboard

牛市逃頂信號清單（Top Dashboard）模組 v1。前端 `index.html` 顯示 10 項頂部風險指標，資料來源為 `data.json`，透過 `update_data.py` 自動更新，並可搭配 GitHub Actions 定時執行。

## 專案結構
- `index.html`：前端儀表板，讀取 `data.json` 並呈現各項指標與進度條。
- `data.json`：指標資料檔，含名稱、類別、當前值、參考值、方向、單位、強度。
- `update_data.py`：自動抓取外部資料並更新 `data.json` 的腳本。
- `.github/workflows/update-dashboard.yml`：每日執行更新與自動推送的 GitHub Actions workflow。

## 資料格式
`data.json` 為 10 個指標的陣列，欄位：
- `name`：指標名稱
- `category`：分類
- `current`：最新值
- `ref`：參考線／臨界值
- `direction`：`higher_worse`（高於 ref 越接近頂部）或 `lower_worse`（低於 ref 越接近頂部）
- `unit`：單位（可為空字串）
- `strength`：信號可信度（0–1）

範例模板（完整內容請參見檔案本身）：
```json
{
  "name": "全球流動性模型（RRP + TGA + Fed BS）",
  "category": "流動性",
  "current": 0,
  "ref": -1.0,
  "direction": "lower_worse",
  "unit": "",
  "strength": 0.7
}
```

## 使用方式
1. 安裝依賴（本地手動執行腳本時）：
   ```bash
   pip install requests yfinance
   ```
2. 執行更新並輸出新版 `data.json`：
   ```bash
   python update_data.py
   ```
3. 開啟 `index.html` 即可在瀏覽器查看儀表板。

## 更新邏輯（摘要）
- **load_data / save_data**：讀寫 `data.json`。
- **find_indicator**：用關鍵字找到指定指標。
- **update_liquidity_indicator**：FRED RRPONTSYD、WTREGEN、WALCL YoY 組合，映射為 -2 ~ +2 流動性分數（目標 ref = -1）。
- **update_stablecoin_growth**：CoinGecko Tether、USDC 90 日市值成長率加權平均。
- **update_fear_greed**：Alternative.me FNG 指數。
- **update_global_risk**：DXY、VIX Z-score 平均，估算全球風險熱度。

## GitHub Actions
- 排程：每日 09:00 UTC（`cron: "0 9 * * *"`）。
- 步驟：設定 Python 3.10 → 安裝依賴 → 執行 `update_data.py` → git commit & push 變更。

## 注意事項
- 部分資料源（特別是 FRED）可能需要 API Key。可在環境變數中設定 `FRED_API_KEY`。
- 網路或來源異常時，腳本會保留現有資料並在終端顯示警告。
- 進度條邏輯：`higher_worse` 以 `current/ref` 對應 0–100%；`lower_worse` 在低於 ref 時按差值比例累進，超過 100% 時會被截斷。

## 後續規劃
- 依實際需求微調權重、對指標進行平滑處理。
- 增加測試或監控（例如 Slack / Telegram 通知）。
