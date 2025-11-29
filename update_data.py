"""Auto-update indicators for BTC Top Dashboard v2.

指標只保留 7 個核心項目：
1. RRP 逆回購餘額 YoY（%）
2. TGA 財政部帳戶 YoY（%）
3. Fed 資產負債表 YoY（%）
4. Net Liquidity 綜合指標 YoY（%）
5. 穩定幣供應 90 日成長（USDT+USDC, %）
6. USDT.D 穩定幣市佔率（%） – 4% 近頂 / 6% 近底
7. 比特幣現貨 ETF 5 日淨流量（美元）

依賴：
- requests
- yfinance
- pandas（yfinance 依賴中已包含）
- 環境變數：FRED_API_KEY（沒有也可以，只是 FRED API 會有限制）

執行：
    python update_data.py
"""

from __future__ import annotations

import pandas as pd
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import yfinance as yf
import pandas as pd  # 用來處理 MultiIndex 欄位

# ---------------- 基本設定 ----------------

ROOT = Path(__file__).parent
DATA_PATH = ROOT / "data.json"

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"
COINGECKO_BASE = "https://api.coingecko.com/api/v3"
SOSO_ETF_URL = "https://api.sosovalue.com/data/v1/etf/spotBTC?limit=40"


# ---------------- IO helpers ----------------


def load_data(path: Path = DATA_PATH) -> List[Dict[str, Any]]:
    """讀取 data.json，失敗時回傳空陣列。"""
    if not path.exists():
        print(f"[warn] {path} not found; return empty list")
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        print(f"[error] failed to load {path}: {exc}")
        return []


def save_data(data: List[Dict[str, Any]], path: Path = DATA_PATH) -> None:
    """覆寫寫回 data.json。"""
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved {path}")


def find_indicator(data: List[Dict[str, Any]], keyword: str) -> Optional[Dict[str, Any]]:
    """用名稱關鍵字找到對應指標物件。"""
    key = keyword.lower()
    for item in data:
        if key in item.get("name", "").lower():
            return item
    return None


# ---------------- 通用計算工具 ----------------


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _fred_series(
    series_id: str, start: dt.date, api_key: Optional[str]
) -> List[Tuple[dt.date, float]]:
    """抓 FRED series，回傳 (date, value) list。"""
    params = {
        "series_id": series_id,
        "file_type": "json",
        "observation_start": start.isoformat(),
    }
    if api_key:
        params["api_key"] = api_key

    resp = requests.get(FRED_BASE, params=params, timeout=20)
    resp.raise_for_status()
    observations = resp.json().get("observations", [])

    out: List[Tuple[dt.date, float]] = []
    for obs in observations:
        val = obs.get("value")
        if val in (None, "", "."):
            continue
        try:
            d = dt.date.fromisoformat(obs["date"])
            out.append((d, float(val)))
        except Exception:
            continue
    return out


def _value_near(series: List[Tuple[dt.date, float]], target: dt.date) -> Optional[float]:
    if not series:
        return None
    closest = min(series, key=lambda p: abs((p[0] - target).days))
    return closest[1]


def _yoy(series: List[Tuple[dt.date, float]]) -> Optional[float]:
    """回傳 YoY（倍數），例如 0.1 代表 +10%。"""
    if not series:
        return None
    latest_date, latest_val = series[-1]
    year_ago = latest_date - dt.timedelta(days=365)
    prev = _value_near(series, year_ago)
    if prev is None or prev == 0:
        return None
    return (latest_val - prev) / abs(prev)


def _change_vs_days_ago(
    series: List[Tuple[dt.date, float]], days: int
) -> Optional[float]:
    """回傳與 N 日前相比的變化比例。"""
    if not series:
        return None
    latest_date, latest_val = series[-1]
    ref_date = latest_date - dt.timedelta(days=days)
    prev = _value_near(series, ref_date)
    if prev is None or prev == 0:
        return None
    return (latest_val - prev) / abs(prev)


# ---------------- 1) RRP YoY ----------------


def update_rrp_yoy(data: List[Dict[str, Any]]) -> None:
    indicator = find_indicator(data, "RRP 逆回購")
    if not indicator:
        print("[warn] RRP YoY indicator not found")
        return

    api_key = os.getenv("FRED_API_KEY")
    start = dt.date.today() - dt.timedelta(days=800)

    try:
        series = _fred_series("RRPONTSYD", start, api_key)
        print(f"[info] fetched FRED RRP (RRPONTSYD) with {len(series)} points")
    except Exception as exc:
        print(f"[warn] FRED RRP fetch failed: {exc}")
        return

    yoy = _yoy(series)
    if yoy is None:
        print("[warn] RRP YoY missing; skip")
        return

    yoy_pct = yoy * 100
    indicator["current"] = round(yoy_pct, 2)
    indicator.setdefault("meta", {})
    indicator["meta"].update(
        {
            "source": "FRED RRPONTSYD",
            "last_date": series[-1][0].isoformat(),
        }
    )
    indicator["detail"] = (
        f"RRP YoY = {yoy_pct:+.2f}%：數值越高代表更多資金停在貨幣市場，"
        "流動性被抽走，對風險資產偏空。"
    )
    print(f"[info] RRP YoY updated: {yoy_pct:+.2f}%")


# ---------------- 2) TGA YoY ----------------


def update_tga_yoy(data: List[Dict[str, Any]]) -> None:
    indicator = find_indicator(data, "TGA 財政部帳戶")
    if not indicator:
        print("[warn] TGA YoY indicator not found")
        return

    api_key = os.getenv("FRED_API_KEY")
    start = dt.date.today() - dt.timedelta(days=800)

    try:
        series = _fred_series("WTREGEN", start, api_key)
        print(f"[info] fetched FRED TGA (WTREGEN) with {len(series)} points")
    except Exception as exc:
        print(f"[warn] FRED TGA fetch failed: {exc}")
        return

    yoy = _yoy(series)
    if yoy is None:
        print("[warn] TGA YoY missing; skip")
        return

    yoy_pct = yoy * 100
    indicator["current"] = round(yoy_pct, 2)
    indicator.setdefault("meta", {})
    indicator["meta"].update(
        {
            "source": "FRED WTREGEN",
            "last_date": series[-1][0].isoformat(),
        }
    )
    indicator["detail"] = (
        f"TGA YoY = {yoy_pct:+.2f}%：TGA 上升代表財政部把錢收回國庫，"
        "從市場抽走美元流動性；對風險資產偏空。"
    )
    print(f"[info] TGA YoY updated: {yoy_pct:+.2f}%")


# ---------------- 3) Fed BS YoY ----------------


def update_fed_bs_yoy(data: List[Dict[str, Any]]) -> None:
    indicator = find_indicator(data, "Fed 資產負債表")
    if not indicator:
        print("[warn] Fed BS YoY indicator not found")
        return

    api_key = os.getenv("FRED_API_KEY")
    start = dt.date.today() - dt.timedelta(days=800)

    try:
        series = _fred_series("WALCL", start, api_key)
        print(f"[info] fetched FRED BS (WALCL) with {len(series)} points")
    except Exception as exc:
        print(f"[warn] FRED BS fetch failed: {exc}")
        return

    yoy = _yoy(series)
    if yoy is None:
        print("[warn] Fed BS YoY missing; skip")
        return

    yoy_pct = yoy * 100
    indicator["current"] = round(yoy_pct, 2)
    indicator.setdefault("meta", {})
    indicator["meta"].update(
        {
            "source": "FRED WALCL",
            "last_date": series[-1][0].isoformat(),
        }
    )
    indicator["detail"] = (
        f"Fed 資產負險表 YoY = {yoy_pct:+.2f}%：YoY 越負代表 QT 越強，"
        "長期對 BTC / 風險資產偏空。"
    )
    print(f"[info] Fed BS YoY updated: {yoy_pct:+.2f}%")


# ---------------- 4) Net Liquidity YoY & Impulse ----------------


def _merge_net_liquidity(
    rrp: List[Tuple[dt.date, float]],
    tga: List[Tuple[dt.date, float]],
    bs: List[Tuple[dt.date, float]],
) -> List[Tuple[dt.date, float]]:
    """Net = BS - RRP - TGA（簡化版）"""
    all_dates = {d for d, _ in rrp} | {d for d, _ in tga} | {d for d, _ in bs}
    out: List[Tuple[dt.date, float]] = []
    for d in sorted(all_dates):
        r = _value_near(rrp, d) or 0.0
        t = _value_near(tga, d) or 0.0
        b = _value_near(bs, d) or 0.0
        net = b - r - t
        out.append((d, net))
    return out


def _compute_beta_vs_btc(net_series: List[Tuple[dt.date, float]]) -> Optional[float]:
    """用過去一年日資料粗略估算 Net Liquidity 對 BTC 價格的 beta。"""
    if not net_series:
        return None

    end_date = net_series[-1][0]
    start_date = end_date - dt.timedelta(days=365)

    # 這裡明確設 auto_adjust=False，避免未來 yfinance 預設值變動
    btc = yf.download(
        "BTC-USD",
        start=start_date.isoformat(),
        end=(end_date + dt.timedelta(days=1)).isoformat(),
        interval="1d",
        progress=False,
        auto_adjust=False,
    )
    if btc.empty:
        return None

    # 若是 MultiIndex 欄位（某些版本/參數組合會這樣），先攤平成單層欄位名
    if isinstance(btc.columns, pd.MultiIndex):
        btc = btc.copy()
        btc.columns = [c[-1] if isinstance(c, tuple) else c for c in btc.columns]

    # 優先用 Adj Close，沒有就改用 Close
    price_col = None
    for cand in ("Adj Close", "Close"):
        if cand in btc.columns:
            price_col = cand
            break

    if price_col is None:
        # 找不到價格欄就直接放棄算 beta（不影響其它指標）
        return None

    price = {idx.date(): float(row[price_col]) for idx, row in btc.iterrows()}

    xs, ys = [], []
    for d, net in net_series:
        if d < start_date or d > end_date:
            continue
        p = price.get(d)
        if p is None:
            continue
        xs.append(net)
        ys.append(p)

    if len(xs) < 20:
        return None

    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / len(xs)
    var_x = sum((x - mean_x) ** 2 for x in xs) / len(xs)
    if var_x == 0:
        return None
    return cov / var_x


def update_net_liquidity(data: List[Dict[str, Any]]) -> None:
    indicator = find_indicator(data, "Net Liquidity 綜合指標")
    if not indicator:
        print("[warn] Net Liquidity indicator not found")
        return

    api_key = os.getenv("FRED_API_KEY")
    start = dt.date.today() - dt.timedelta(days=800)

    try:
        rrp = _fred_series("RRPONTSYD", start, api_key)
        tga = _fred_series("WTREGEN", start, api_key)
        bs = _fred_series("WALCL", start, api_key)
        print(
            f"[info] fetched FRED Net Liquidity components: "
            f"RRP={len(rrp)}, TGA={len(tga)}, BS={len(bs)}"
        )
    except Exception as exc:
        print(f"[warn] FRED Net Liquidity fetch failed: {exc}")
        return

    net = _merge_net_liquidity(rrp, tga, bs)
    yoy = _yoy(net)
    impulse = _change_vs_days_ago(net, 90)
    beta = _compute_beta_vs_btc(net)

    if yoy is None:
        print("[warn] Net Liquidity YoY missing; skip")
        return

    yoy_pct = yoy * 100
    impulse_pct = impulse * 100 if impulse is not None else None

    indicator["current"] = round(yoy_pct, 2)
    indicator.setdefault("meta", {})
    indicator["meta"].update(
        {
            "source": "FRED WALCL/RRPONTSYD/WTREGEN",
            "last_date": net[-1][0].isoformat(),
            "impulse_90d_pct": round(impulse_pct, 2) if impulse_pct is not None else None,
            "beta_vs_btc": round(beta, 3) if beta is not None else None,
        }
    )

    beta_str = "N/A" if beta is None else f"{beta:.2f}"
    impulse_str = (
        "N/A" if impulse_pct is None else f"{impulse_pct:+.2f}%（近 90 日加速度）"
    )

    indicator["detail"] = (
        f"Net = BS - RRP - TGA · YoY = {yoy_pct:+.2f}%；"
        f"{impulse_str}；Beta(BTC) ≈ {beta_str}。YoY 越負代表系統性流動性在收縮。"
    )

    print(
        f"[info] Net Liquidity YoY updated: {yoy_pct:+.2f}% "
        f"(Impulse90d={impulse_str}, Beta={beta_str})"
    )


# ---------------- 5) Stablecoin 90d growth ----------------


def _coingecko_growth(coin_id: str, days: int = 120) -> Optional[float]:
    url = f"{COINGECKO_BASE}/coins/{coin_id}/market_chart"
    params = {"vs_currency": "usd", "days": days, "interval": "daily"}
    resp = requests.get(url, params=params, timeout=20)
    resp.raise_for_status()
    mkt_caps = resp.json().get("market_caps", [])
    if len(mkt_caps) < 2:
        return None

    now_ts, last_val = mkt_caps[-1]
    target_ts = now_ts - 90 * 24 * 3600 * 1000
    start_val = None
    for ts, cap in mkt_caps:
        if ts >= target_ts:
            start_val = cap
            break
    if start_val is None:
        start_val = mkt_caps[0][1]

    if start_val <= 0:
        return None
    return (last_val - start_val) / start_val * 100


def update_stablecoin_growth(data: List[Dict[str, Any]]) -> None:
    indicator = find_indicator(data, "穩定幣供應 90 日成長")
    if not indicator:
        print("[warn] Stablecoin growth indicator not found")
        return

    growths = []
    for coin_id in ("tether", "usd-coin"):
        try:
            g = _coingecko_growth(coin_id)
            if g is not None:
                growths.append(g)
        except Exception as exc:
            print(f"[warn] CoinGecko growth failed for {coin_id}: {exc}")

    if not growths:
        print("[warn] Stablecoin growth missing; skip")
        return

    avg_growth = sum(growths) / len(growths)
    indicator["current"] = round(avg_growth, 2)
    indicator.setdefault("meta", {})
    indicator["meta"].update(
        {
            "source": "CoinGecko market_chart",
            "coins": ["tether", "usd-coin"],
            "sample_growth": [round(g, 2) for g in growths],
        }
    )
    indicator["detail"] = (
        f"USDT+USDC 90 日供應成長 ≈ {avg_growth:+.2f}%：成長過快通常對應牛市中後段，"
        "代表場內槓桿與風險偏好升溫。"
    )
    print(f"[info] stablecoin 90d growth updated: {avg_growth:+.2f}%")


# ---------------- 6) USDT.D dominance (4%~6% band) ----------------


def fetch_usdt_dominance() -> Optional[float]:
    """使用 CoinGecko global 拿 USDT 市佔率。"""
    try:
        url = f"{COINGECKO_BASE}/global"
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        dom = resp.json()["data"]["market_cap_percentage"].get("usdt")
        if dom is None:
            return None
        return float(dom)
    except Exception as exc:
        print(f"[warn] USDT dominance fetch failed: {exc}")
        return None


def update_usdt_d_dominance(data: List[Dict[str, Any]]) -> None:
    indicator = find_indicator(data, "USDT.D 穩定幣市佔率")
    if not indicator:
        print("[warn] USDT.D indicator not found")
        return

    dom = fetch_usdt_dominance()
    if dom is None:
        print("[warn] USDT dominance missing; skip")
        return

    indicator["current"] = round(dom, 3)
    # 若 data.json 已寫 band，用它；否則預設 4–6
    floor = indicator.get("meta", {}).get("band_floor", 4.0)
    ceil = indicator.get("meta", {}).get("band_ceiling", 6.0)

    indicator.setdefault("meta", {})
    indicator["meta"].update(
        {
            "source": "CoinGecko /global market_cap_percentage.usdt",
            "band_floor": floor,
            "band_ceiling": ceil,
        }
    )

    indicator["detail"] = (
        f"USDT.D ≈ {dom:.3f}%：約 {floor:.1f}% 左右代表市場極度風險偏好、"
        "穩定幣佔比偏低（接近牛市頂部）；約 "
        f"{ceil:.1f}% 則代表穩定幣佔比偏高，市場保守、接近底部區間。"
    )

    print(f"[info] USDT.D dominance updated: {dom:.3f}%")


# ---------------- 7) ETF Net Flow 5d (SoSoValue) ----------------


def fetch_sosovalue_etf_flows() -> Optional[float]:
    """
    從 SoSoValue API 取回所有 BTC Spot ETF 流量，回傳最近 5 天的淨流量總和（美元）。
    """
    try:
        resp = requests.get(SOSO_ETF_URL, timeout=20)
        resp.raise_for_status()
        raw = resp.json()
    except Exception as exc:
        print(f"[warn] SoSoValue ETF fetch failed: {exc}")
        return None

    items = raw.get("data", {}).get("items", [])
    if not items:
        return None

    # 依日期加總
    daily: Dict[str, float] = {}
    for item in items:
        day = item.get("date")
        flow = float(item.get("flow", 0) or 0)
        if day is None:
            continue
        daily[day] = daily.get(day, 0.0) + flow

    days = sorted(daily.keys())[-5:]
    total_5d = sum(daily[d] for d in days)
    return total_5d


def update_etf_net_flow_5d(data: List[Dict[str, Any]]) -> None:
    indicator = find_indicator(data, "ETF 5 日淨流量")
    if not indicator:
        print("[warn] ETF Net Flow indicator not found")
        return

    total5d = fetch_sosovalue_etf_flows()
    if total5d is None:
        print("[warn] SoSoValue ETF data missing; skip update")
        return

    indicator["current"] = round(total5d, 2)
    indicator.setdefault("meta", {})
    indicator["meta"].update(
        {
            "source": "SoSoValue Spot BTC ETF API",
            "window": "last 5 days",
        }
    )

    indicator["detail"] = (
        f"最近 5 日比特幣現貨 ETF 累計淨流量 ≈ {total5d:,.0f} USD。"
        "持續大額淨流出（負值）代表機構在減倉，比特幣上漲動能轉弱。"
    )

    print(f"[info] ETF Net Flow 5d updated: {total5d:,.0f} USD")


# ---------------- main ----------------


def main() -> None:
    data = load_data()
    if not data:
        print("[warn] data.json is empty or missing; nothing to update")
        return

    update_rrp_yoy(data)
    update_tga_yoy(data)
    update_fed_bs_yoy(data)
    update_net_liquidity(data)
    update_stablecoin_growth(data)
    update_usdt_d_dominance(data)
    update_etf_net_flow_5d(data)

    save_data(data)


if __name__ == "__main__":
    main()
