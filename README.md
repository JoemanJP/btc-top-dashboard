📘 BTC Top Dashboard v2

（牛市逃頂儀表板 · 7 指標精簡版）

本模組提供 比特幣市場頂部風險的統一量化儀表板，整合「全球流動性」「場內穩定幣」「ETF 資金流」等七大高信度週期訊號。

👉 可視化網址（本機）

http://localhost:8000/index.html


👉 資料來源（API auto-fetch）

FRED

CryptoCompare / CoinGecko

TradingView / SoSoValue ETF API

Yahoo Finance

👉 自動化流程

update_data.py  → 更新 data.json  
index.html      → 前端顯示儀表板

🧩 1. 模組檔案結構
btc-top-dashboard/
├── index.html       # 儀表板前端
├── data.json        # 7 指標的最新 value（update_data.py 自動更新）
├── update_data.py   # 後端：抓 API & 寫入 data.json
└── README.md        # 本說明文件（v2）

📊 2. 七大高信度頂部指標（v2 Final）

以下是 只留下真正有效 & 實戰參考度最高 的指標。
（其他雜訊指標全部移除）

1）RRP YoY（Reverse Repo Year-over-Year）

來源 API：FRED – RRPONTSYD
解讀：越低越鬆、越高越緊

RRP = 商業銀行把資金存回 Fed 的工具。

YoY 大幅下降 → 銀行不再把錢停泊在 Fed → 流動性釋放 → Risk-On

YoY 快速上升 → 銀行躲避風險 → Risk-Off → BTC Vulnerable

儀表板：

direction = lower_worse（因為 RRP 過高會擠壓市場）

2）TGA YoY（Treasury General Account）

來源 API：FRED – WTREGEN
TGA = 美國財政部在 Fed 的戶頭。

TGA 上升 → 財政部把錢收回國庫 → 市場流動性變少 → Risk-Off

TGA 下滑 → 發薪水 + 支出 → 市場得到資金 → Risk-On

方向：

higher_worse

3）Fed Balance Sheet YoY（Fed BS YoY）

來源：FRED – WALCL

Fed BS YoY 增加 = QE → Risk-On

Fed BS YoY 減少 = QT → Risk-Off

方向：

lower_worse（縮表越多，風險越高）

4）Net Liquidity YoY（合成流動性）

來源：FRED 合成公式 = BS - TGA - RRP

最重要的流動性終極指標
用於反映金融市場的整體流動性方向。

Net Liquidity YoY 上升 → BTC 長期牛市旺盛期

Net Liquidity YoY 下降 → 牛市末段 / 震盪 / 準備派貨

儀表板另外提供：

Net Liquidity Impulse（近 90 日加速度）

BTC Beta vs Net Liquidity（可選）

方向：

lower_worse

5）Stablecoin Supply Growth（USDT+USDC 90 日成長率）

來源：CoinGecko market_caps

+20% / +30%：牛市末段、高 FOMO、接近頂部

0% ~ 10%：牛市中段

<0%：熊市後期 / 無人加倉

方向：

higher_worse

6）USDT.D（USDT Dominance）— 4% / 6% 區間

來源：TradingView USDT.D（由 yfinance TRX-USD + USDT 市值計算）

📌 大多數週期的明確區間：

USDT.D 4% = 市場過熱、USDT 幾乎全進場 → 接近頂部（TOP Band）

USDT.D 6% = 市場恐慌、大家躺 USDT → 接近底部（Bottom Band）

方向（反向）：

lower_worse（USDT.D 越低越 FOMO → 越接近頂）

儀表板特別標示：

地板（6%）

天花板（4%）

提示：

4% = 市場過熱

6% = 市場偏冷

7）ETF Net Flow（5 日總流量）

來源：SoSoValue BTC ETF API（官方公開 API）

數值：過去 5 天所有美國現貨 BTC ETF 的淨流入美元總和。

解讀：

5 日大幅淨流出 → 牛市末期典型信號

5 日中性 / 小幅淨流入 → 中段行情

5 日大幅暴力流入（> +$1B） → 牛市主升段

方向：

higher_worse（ETF 大幅流出越危險）

🧮 3. data.json 結構

每個指標是一個物件：

{
  "name": "RRP YoY（逆回購）",
  "category": "Global Liquidity",
  "current": -98.5,
  "ref": -20,
  "direction": "higher_worse",
  "unit": "%",
  "strength": 0.8
}


參數說明：

欄位	說明
name	指標名稱
category	分類（Liquidity / Stablecoin / ETF）
current	最新數值（update_data.py 寫入）
ref	臨界值（前端判斷是否達頂）
direction	higher_worse 或 lower_worse
unit	顯示單位
strength	信號強度（0–1）
🖥️ 4. 前端（index.html）

前端執行流程：

fetch("data.json")

計算

進度（0–100%）

是否命中頂部

顯示 7 個卡片

顯示總體風險

平均進度

建議持倉 / 減倉比例

USDT.D 顯示 4% / 6% 提示

⚙️ 5. 後端（update_data.py）

自動流程：

抓 FRED（RRP / TGA / BS）

計算 YoY 與 Net Liquidity / Impulse

CoinGecko 抓 USDT / USDC 市值

TradingView 抓 USDT.D

SoSoValue API 抓 ETF Flow

覆寫 data.json

執行方式：

python update_data.py


成功後會看到：

[info] stablecoin 90d growth updated: +8.2%
[info] USDT.D updated: 5.78%
[info] ETF Net Flow updated: +350,000,000 USD
Saved data.json

🌐 6. GitHub Pages + GitHub Actions（可選）

你可以讓儀表板變成公開網頁：

push repo 至 GitHub

在 Settings → Pages → root → index.html

加以下 workflow：

.github/workflows/update.yml

name: Update Dashboard

on:
  schedule:
    - cron: "0 */6 * * *"
  workflow_dispatch:

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.10"
      - run: pip install requests yfinance
      - run: python btc-top-dashboard/update_data.py
      - uses: stefanzweifel/git-auto-commit-action@v4
        with:
          commit_message: "Auto update data.json"


這樣你的儀表板 每 6 小時自動刷新一次，變成自己的 Coinglass。

📎 7. v2 Final：這七指標為什麼是最強組合？

因為它們涵蓋：

類別	指標	週期信度	作用
流動性	RRP YoY	高	市場總風險偏好
	TGA YoY	中高	財政部收縮 vs 釋放資金
	Fed BS YoY	中	QE/QT 對 BTC 的實質影響
	Net Liquidity YoY / Impulse	最高	牛/熊主循環核心來源
場內資金	Stablecoin Growth	高	投機力道 / 新資金進場速度
	USDT.D（4–6%）	極高	牛頂 / 熊底傳統經驗值
機構資金	ETF 5 日 Flow	極高	ETF 是 2024+ 最強週期來源

這七個一起看，可以達到：

✔ 剔除雜訊
✔ 統整全球流動性 → 穩定幣 → 機構資金
✔ 一眼看到市場在牛市哪個階段