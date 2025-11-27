"""Auto-update indicators for BTC Top Dashboard.

Data is written to data.json according to the provided v1 spec.
Dependencies: requests, yfinance
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

import requests
import yfinance as yf

DATA_PATH = Path(__file__).parent / "data.json"
FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"
COINGECKO_BASE = "https://api.coingecko.com/api/v3"
FNG_API = "https://api.alternative.me/fng/"


# ---------- IO helpers ----------
def load_data(path: Path = DATA_PATH) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data: List[Dict[str, Any]], path: Path = DATA_PATH) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved {path}")


# ---------- utils ----------
def find_indicator(data: List[Dict[str, Any]], keyword: str) -> Optional[Dict[str, Any]]:
    key = keyword.lower()
    for item in data:
        if key in item.get("name", "").lower():
            return item
    return None


def _fred_series(series_id: str, start: dt.date, api_key: Optional[str]) -> List[Tuple[dt.date, float]]:
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
    series: List[Tuple[dt.date, float]] = []
    for obs in observations:
        val = obs.get("value")
        if val in (None, "", "."):
            continue
        try:
            series.append((dt.date.fromisoformat(obs["date"]), float(val)))
        except (ValueError, TypeError):
            continue
    return series


def _value_near(series: List[Tuple[dt.date, float]], target: dt.date) -> Optional[float]:
    if not series:
        return None
    # pick the point closest to target date
    closest = min(series, key=lambda p: abs((p[0] - target).days))
    return closest[1]


def _yoy(series: List[Tuple[dt.date, float]]) -> Optional[float]:
    if not series:
        return None
    latest_date, latest_val = series[-1]
    year_ago = latest_date - dt.timedelta(days=365)
    prev = _value_near(series, year_ago)
    if prev is None or prev == 0:
        return None
    return (latest_val - prev) / abs(prev)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


# ---------- indicator updaters ----------
def update_liquidity_indicator(data: List[Dict[str, Any]]) -> None:
    indicator = find_indicator(data, "流動性模型")
    if not indicator:
        print("[warn] liquidity indicator not found")
        return

    api_key = os.getenv("FRED_API_KEY")
    start = dt.date.today() - dt.timedelta(days=800)
    series_ids = ["RRPONTSYD", "WTREGEN", "WALCL"]
    yoy_values = []

    for sid in series_ids:
        try:
            series = _fred_series(sid, start, api_key)
            yoy = _yoy(series)
            if yoy is not None:
                yoy_values.append(yoy)
        except Exception as exc:  # network/parse errors are non-fatal
            print(f"[warn] FRED fetch failed for {sid}: {exc}")

    if not yoy_values:
        print("[warn] liquidity yoy missing; skip update")
        return

    avg_yoy = sum(yoy_values) / len(yoy_values)
    score = _clamp(avg_yoy * 4, -2, 2)  # map YoY range roughly to -2~2

    indicator["current"] = round(score, 3)
    indicator.setdefault("meta", {})
    indicator["meta"].update({
        "source": "FRED",
        "series": series_ids,
        "yoy_values": [round(v, 4) for v in yoy_values],
    })
    print(f"[info] liquidity score updated: {score:.3f}")


def _coingecko_growth(coin_id: str, days: int = 120) -> Optional[float]:
    url = f"{COINGECKO_BASE}/coins/{coin_id}/market_chart"
    params = {"vs_currency": "usd", "days": days, "interval": "daily"}
    resp = requests.get(url, params=params, timeout=20)
    resp.raise_for_status()
    market_caps = resp.json().get("market_caps", [])
    if len(market_caps) < 2:
        return None

    now_ts, latest = market_caps[-1]
    target_ts = now_ts - (90 * 24 * 3600 * 1000)

    past_val = None
    for ts, cap in market_caps:
        if ts >= target_ts:
            past_val = cap
            break
    if past_val is None:
        past_val = market_caps[0][1]

    if past_val <= 0:
        return None
    return (latest - past_val) / past_val * 100


def update_stablecoin_growth(data: List[Dict[str, Any]]) -> None:
    indicator = find_indicator(data, "USDT")
    if not indicator:
        print("[warn] stablecoin indicator not found")
        return

    growths = []
    for coin in ("tether", "usd-coin"):
        try:
            g = _coingecko_growth(coin)
            if g is not None:
                growths.append(g)
        except Exception as exc:
            print(f"[warn] CoinGecko fetch failed for {coin}: {exc}")

    if not growths:
        print("[warn] stablecoin growth missing; skip update")
        return

    avg_growth = sum(growths) / len(growths)
    indicator["current"] = round(avg_growth, 3)
    indicator.setdefault("meta", {})
    indicator["meta"].update({
        "source": "CoinGecko",
        "coins": ["tether", "usd-coin"],
        "growth_samples": [round(v, 3) for v in growths],
    })
    print(f"[info] stablecoin growth updated: {avg_growth:.2f}%")


def update_fear_greed(data: List[Dict[str, Any]]) -> None:
    indicator = find_indicator(data, "恐慌貪婪")
    if not indicator:
        print("[warn] fear & greed indicator not found")
        return

    try:
        resp = requests.get(FNG_API, params={"limit": 1}, timeout=10)
        resp.raise_for_status()
        payload = resp.json().get("data", [])
        value = int(payload[0]["value"]) if payload else None
    except Exception as exc:
        print(f"[warn] FNG fetch failed: {exc}")
        return

    if value is None:
        print("[warn] FNG value missing; skip update")
        return

    indicator["current"] = value
    indicator.setdefault("meta", {})
    indicator["meta"].update({"source": "Alternative.me"})
    print(f"[info] FNG updated: {value}")


def _zscore(series: List[float]) -> float:
    if not series:
        return 0.0
    mean = sum(series) / len(series)
    var = sum((v - mean) ** 2 for v in series) / len(series)
    std = var ** 0.5
    if std == 0:
        return 0.0
    return (series[-1] - mean) / std


def update_global_risk(data: List[Dict[str, Any]]) -> None:
    indicator = find_indicator(data, "全球風險")
    if not indicator:
        print("[warn] global risk indicator not found")
        return

    try:
        df = yf.download(["DX-Y.NYB", "^VIX"], period="1y", interval="1d", progress=False, group_by="ticker")
    except Exception as exc:
        print(f"[warn] yfinance download failed: {exc}")
        return

    zscores = []
    for ticker in ("DX-Y.NYB", "^VIX"):
        try:
            series = df[ticker]["Adj Close"].dropna().tolist()
            if not series:
                continue
            zscores.append(_zscore(series))
        except Exception:
            continue

    if not zscores:
        print("[warn] global risk zscore missing; skip update")
        return

    avg_z = sum(zscores) / len(zscores)
    indicator["current"] = round(avg_z, 3)
    indicator.setdefault("meta", {})
    indicator["meta"].update({
        "source": "Yahoo Finance",
        "tickers": ["DX-Y.NYB", "^VIX"],
        "zscores": [round(z, 3) for z in zscores],
    })
    print(f"[info] global risk updated: {avg_z:.3f}")


# ---------- main ----------
def main() -> None:
    data = load_data()
    if not data:
        print("[warn] data.json is empty or missing")
        return

    update_liquidity_indicator(data)
    update_stablecoin_growth(data)
    update_fear_greed(data)
    update_global_risk(data)

    save_data(data)


if __name__ == "__main__":
    main()
