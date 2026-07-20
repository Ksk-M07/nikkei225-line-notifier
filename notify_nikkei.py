"""
日経225 パーフェクトオーダー + 長期MA実体確定ブレイク → LINE通知

判定ロジック:
  1. パーフェクトオーダー: MA5 / MA20 / MA50 が同方向に並んでいる
       上昇: MA5 > MA20 > MA50
       下降: MA5 < MA20 < MA50
  2. トリガー: パーフェクトオーダーが成立している状態で、
     終値(実体)が長期MA(50)を当日に上抜け/下抜けして確定した瞬間
       上抜け確定: 前日終値 <= 前日MA50 かつ 当日終値 > 当日MA50
       下抜け確定: 前日終値 >= 前日MA50 かつ 当日終値 < 当日MA50
  3. 超長期MA(200)はロング/ショートの地合い判定のみに使用（発注トリガーには使わない）
       終値 > MA200 → ロング優勢
       終値 < MA200 → ショート優勢

毎営業日1回、GitHub Actionsから実行される想定。
直近バーのみを判定するため、状態ファイル無しで実行のたびに1回だけ通知される。
"""

import os
import sys
from datetime import datetime, timezone

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import pandas as pd
import requests
import yfinance as yf

TICKER = "^N225"
MA_SHORT = 5
MA_MID = 20
MA_LONG = 50
MA_SUPER = 200

LINE_API_BROADCAST = "https://api.line.me/v2/bot/message/broadcast"
LINE_API_PUSH = "https://api.line.me/v2/bot/message/push"


def fetch_data() -> pd.DataFrame:
    df = yf.download(TICKER, period="3y", interval="1d", auto_adjust=False, progress=False)
    if df.empty:
        raise RuntimeError("日経225のデータ取得に失敗しました（yfinanceが空データを返却）")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.dropna(subset=["Close"])
    return df


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["MA5"] = df["Close"].rolling(MA_SHORT).mean()
    df["MA20"] = df["Close"].rolling(MA_MID).mean()
    df["MA50"] = df["Close"].rolling(MA_LONG).mean()
    df["MA200"] = df["Close"].rolling(MA_SUPER).mean()
    return df


def evaluate_signal(df: pd.DataFrame) -> dict:
    if len(df) < MA_SUPER + 2:
        raise RuntimeError(f"MA200計算に必要なバー数が不足しています（{len(df)}本）")

    today = df.iloc[-1]
    prev = df.iloc[-2]

    if today[["MA5", "MA20", "MA50", "MA200"]].isna().any():
        raise RuntimeError("直近バーの移動平均が未確定です（データ不足）")

    perfect_up = today["MA5"] > today["MA20"] > today["MA50"]
    perfect_down = today["MA5"] < today["MA20"] < today["MA50"]

    cross_up = prev["Close"] <= prev["MA50"] and today["Close"] > today["MA50"]
    cross_down = prev["Close"] >= prev["MA50"] and today["Close"] < today["MA50"]

    signal_long = bool(perfect_up and cross_up)
    signal_short = bool(perfect_down and cross_down)

    bias200 = "ロング優勢" if today["Close"] > today["MA200"] else "ショート優勢"

    return {
        "date": df.index[-1].strftime("%Y-%m-%d"),
        "close": float(today["Close"]),
        "ma5": float(today["MA5"]),
        "ma20": float(today["MA20"]),
        "ma50": float(today["MA50"]),
        "ma200": float(today["MA200"]),
        "perfect_up": bool(perfect_up),
        "perfect_down": bool(perfect_down),
        "signal_long": signal_long,
        "signal_short": signal_short,
        "bias200": bias200,
    }


def build_message(result: dict) -> str:
    direction = "ロング" if result["signal_long"] else "ショート"
    action = "上抜け確定" if result["signal_long"] else "下抜け確定"
    return (
        f"【日経225 パーフェクトオーダー シグナル】\n"
        f"日付: {result['date']}\n"
        f"方向: {direction}（{action}）\n"
        f"終値: {result['close']:,.0f}\n"
        f"MA5: {result['ma5']:,.0f} / MA20: {result['ma20']:,.0f} / "
        f"MA50: {result['ma50']:,.0f}\n"
        f"200MA地合い: {result['bias200']}（MA200: {result['ma200']:,.0f}）\n"
        f"※本通知は投資助言ではありません。最終判断はご自身で行ってください。"
    )


def send_line(message: str) -> None:
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("環境変数 LINE_CHANNEL_ACCESS_TOKEN が未設定です")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {"messages": [{"type": "text", "text": message}]}

    mode = os.environ.get("LINE_TARGET_MODE", "broadcast").lower()

    if mode == "push":
        user_ids = [u.strip() for u in os.environ.get("LINE_USER_IDS", "").split(",") if u.strip()]
        if not user_ids:
            raise RuntimeError("LINE_TARGET_MODE=push の場合は LINE_USER_IDS が必要です")
        for uid in user_ids:
            resp = requests.post(
                LINE_API_PUSH, headers=headers, json={**payload, "to": uid}, timeout=15
            )
            if resp.status_code != 200:
                raise RuntimeError(f"LINE push失敗 (to={uid}): {resp.status_code} {resp.text}")
    else:
        resp = requests.post(LINE_API_BROADCAST, headers=headers, json=payload, timeout=15)
        if resp.status_code != 200:
            raise RuntimeError(f"LINE broadcast失敗: {resp.status_code} {resp.text}")


def main() -> None:
    df = compute_indicators(fetch_data())
    result = evaluate_signal(df)

    now = datetime.now(timezone.utc).isoformat()
    print(f"[{now}] date={result['date']} close={result['close']:.0f} "
          f"perfect_up={result['perfect_up']} perfect_down={result['perfect_down']} "
          f"signal_long={result['signal_long']} signal_short={result['signal_short']} "
          f"bias200={result['bias200']}")

    if result["signal_long"] or result["signal_short"]:
        message = build_message(result)
        print("--- シグナル検出。LINE通知を送信します ---")
        print(message)
        send_line(message)
    else:
        print("シグナルなし。通知は送信しません。")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
