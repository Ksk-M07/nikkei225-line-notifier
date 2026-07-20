# 日経225 パーフェクトオーダー LINE通知ツール（無料・UI無し）

日経225の日足で
1. MA5 / MA20 / MA50 が同方向に並ぶ（パーフェクトオーダー）
2. その状態で終値がMA50を実体で上抜け/下抜けして確定

した瞬間にLINEへ通知します。MA200は「終値がMA200より上ならロング優勢、下ならショート優勢」という地合い情報として通知文に添えるだけで、発注トリガーには使いません。

料金はすべて無料枠内（GitHub Actions無料枠 + LINE公式アカウント無料プラン + Yahoo Financeの無料データ）。TradingViewは使わず、Pythonで完結させています。

> **免責事項**: 本ツールは特定の売買を推奨するものではなく、投資助言を目的としたものでもありません。移動平均線の機械的な判定結果を通知するだけであり、シグナルの正確性・完全性を保証しません。投資判断は必ずご自身の責任で行ってください。本ツールの利用によって生じたいかなる損害についても、作成者は責任を負いません。

### 必要なもの

- GitHubアカウント（無料）
- LINEアカウント（無料）
- セットアップ作業 15分程度

---

## 全体構成

```
GitHub Actions（毎営業日18:00 JST に自動実行）
   └─ notify_nikkei.py
        ├─ yfinanceで日経225(^N225)の日足を取得
        ├─ MA5/20/50/200を計算し、シグナル判定
        └─ シグナル成立時のみ LINE Messaging API へ送信
```

LINE Notify は2025年3月末で終了しているため、LINE公式アカウント（Messaging API）を使います。無料プランで作成できます。

---

## セットアップ手順

### 1. LINE公式アカウント & チャネルアクセストークンの取得

1. [LINE Developers](https://developers.line.biz/) に、**通知を受け取りたい自分のLINEアカウント**でログイン
2. 「プロバイダー」を新規作成
3. そのプロバイダー配下に「Messaging API」チャネルを新規作成（＝自分専用のLINE公式アカウントが作られる）
4. 作成したチャネルの「Messaging API設定」タブを開き、「チャネルアクセストークン（長期）」を発行してコピー
5. 同タブの「応答メッセージ」をオフ、「Webhookの利用」はオフのままでOK（今回は送信専用）
6. 同タブに表示されているQRコードを、**自分のスマホのLINEアプリ**で読み取り、この公式アカウントを友だち追加する（自分1人だけが友だちの状態になる）

> **自分ひとりで使う場合はこれで設定完了です。** 手順6で追加した「自分専用の公式アカウント」の友だちは自分しかいないため、下記2.のbroadcast（デフォルト設定のまま）で送っても届くのは自分のLINEだけです。他の設定（push・userId取得）は不要です。

### 2. 通知の届け方を決める（どちらか）

- **A: 全員に配信（broadcast・推奨）**
  「人に渡す」用途に最適です。相手にLINE公式アカウントのQRコードを送って友だち追加してもらえば、以後は自動で全員に届きます。
  - `LINE_TARGET_MODE` = `broadcast`（未設定でもデフォルトでbroadcast）
- **B: 特定の相手にだけ送る（push）**
  - `LINE_TARGET_MODE` = `push`
  - `LINE_USER_IDS` = 送りたい相手のuserId（カンマ区切りで複数可。取得にはWebhookの設定が別途必要になるためやや手間）

> 無料プランは月200通まで（configuration変更なしの初期枠）。broadcastは友だち全員へ1通ずつカウントされるので、友だち数×通知回数が200通/月を超えないか確認してください。超える場合は有料の追加メッセージ購入が必要です。

### 3. GitHubリポジトリを作成してこのフォルダの中身をpush

GitHubで新規リポジトリを作成（Public/Privateどちらでも可、Privateでも個人利用の範囲でActionsは無料枠内）。このフォルダ（`nikkei225_line_notifier/`）の中身をそのままリポジトリのルートとしてpushしてください。

```bash
cd nikkei225_line_notifier
git init
git add .
git commit -m "add nikkei225 line notifier"
git branch -M main
git remote add origin <あなたのリポジトリURL>
git push -u origin main
```

### 4. GitHub Secretsを設定

リポジトリの Settings → Secrets and variables → Actions → New repository secret で以下を登録：

| Secret名 | 値 |
|---|---|
| `LINE_CHANNEL_ACCESS_TOKEN` | 手順1で取得したトークン |
| `LINE_TARGET_MODE` | `broadcast` または `push` |
| `LINE_USER_IDS` | push時のみ。カンマ区切りのuserId |

### 5. 動作確認

Actions タブ → `Nikkei225 Perfect Order LINE Notifier` → `Run workflow` で手動実行し、ログでシグナル判定結果を確認できます（シグナルが出ていない日はLINE通知は届かず、ログに `シグナルなし` と出るのが正常です）。

以後は毎営業日18:00 JSTに自動実行され、シグナル成立時のみLINEに通知が届きます。

---

## ローカルでのテスト方法

```bash
cd nikkei225_line_notifier
pip install -r requirements.txt
set LINE_CHANNEL_ACCESS_TOKEN=xxxx   # PowerShellなら $env:LINE_CHANNEL_ACCESS_TOKEN="xxxx"
python notify_nikkei.py
```

---

## ロジックの調整ポイント（必要に応じて `notify_nikkei.py` を編集）

- `MA_SHORT` / `MA_MID` / `MA_LONG` / `MA_SUPER`：移動平均の期間（現状 5/20/50/200）
- パーフェクトオーダー判定とMA50実体クロスは**同じ日**に成立している必要がある実装です。パーフェクトオーダー成立後、数日〜数週間の押し目を経てからのクロスも拾いたい場合は、直近N日以内に`perfect_up`/`perfect_down`が成立していたかを状態として保持するロジックへの拡張が必要です（現状は状態ファイル無しのシンプル構成）。
- cron時刻はワークフローファイル内の `cron: "0 9 * * 1-5"`（UTC）。日本時間換算は+9時間。

---

## よくある質問

**Q. GitHub Actionsは本当に無料ですか？**
Publicリポジトリなら無制限無料。Privateリポジトリでも個人アカウントは月2,000分の無料枠があり、本ツール（1日1回・数十秒の実行）では全く足ります。

**Q. 通知が全く届きません**
まずActionsタブでワークフローが緑（成功）で終わっているか確認してください。赤（失敗）の場合はログを開き、`ERROR:`から始まる行を確認してください。多くは `LINE_CHANNEL_ACCESS_TOKEN` 未設定・入力ミスです。ワークフローが成功していて通知が来ない場合は、その日は単に「シグナルなし」（正常）です。ログの最後の行が `シグナルなし。通知は送信しません。` になっていれば正常動作です。

シグナル待ちとは切り離して「LINEに本当に届くか」だけをすぐ確認したい場合は、Actionsタブの`LINE Test Broadcast`を手動実行してください。固定のテストメッセージだけを送信します（トークンの有効性・友だち追加状況の確認用）。

**Q. 友だち追加してもらったのに届かない**
LINE公式アカウント側の「応答メッセージ」設定は通知の送受信には影響しません。届かない場合は、broadcastの送信上限（無料枠 月200通）を超えていないか、LINE Developersコンソールの「Messaging API設定」→「利用状況」で確認してください。

**Q. Actionsが自動実行されません**
GitHubの無料枠のリポジトリでは、60日間コミットが無いとscheduledワークフローが自動停止する仕様があります。その場合はActionsタブから手動で`Run workflow`すれば再度動き出します。

**Q. コードの中身を書き換えても大丈夫ですか？**
問題ありません。`notify_nikkei.py`はこのファイル単体で完結しています。移動平均の期間やcron時刻は自由に変更可能です。
