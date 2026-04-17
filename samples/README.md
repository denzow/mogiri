# mogiri Sample Scripts

Job creation に使えるサンプルスクリプト集です。
各スクリプトはそのまま mogiri のジョブとして登録できます。

## Samples

### [slack_thread_post.py](slack_thread_post.py) - Slack スレッド投稿

Slack にメッセージを投稿し、スレッドで詳細を返信します。
ワークフローのチェーンと組み合わせて、前段ジョブの結果を自動投稿できます。

| 環境変数 | 必須 | 説明 |
|---|---|---|
| `SLACK_BOT_TOKEN` | Yes | Slack Bot Token (`xoxb-...`) |
| `SLACK_CHANNEL` | Yes | チャンネルID (`C01234567`) |
| `SLACK_TITLE` | No | 親メッセージ (デフォルト: 自動生成) |
| `SLACK_BODY` | No | スレッド返信内容 (デフォルト: 親ジョブの stdout) |

### [db_backup.py](db_backup.py) - データベースバックアップ

PostgreSQL / MySQL のバックアップを gzip 圧縮で保存。古いバックアップの自動ローテーション付き。

| 環境変数 | 必須 | 説明 |
|---|---|---|
| `DB_TYPE` | Yes | `postgres` or `mysql` |
| `DB_NAME` | Yes | データベース名 |
| `DB_HOST` | No | ホスト (default: `localhost`) |
| `DB_USER` | No | ユーザー名 |
| `DB_PASSWORD` | No | パスワード |
| `BACKUP_DIR` | No | 保存先 (default: `/tmp/mogiri-backups`) |
| `BACKUP_KEEP` | No | 保持世代数 (default: `7`) |

### [http_health_check.py](http_health_check.py) - HTTP ヘルスチェック

複数 URL の死活監視。レスポンスコードと応答時間を記録し、異常時はエラー終了します。

| 環境変数 | 必須 | 説明 |
|---|---|---|
| `CHECK_URLS` | Yes | カンマ区切りの URL リスト |
| `CHECK_TIMEOUT` | No | タイムアウト秒 (default: `10`) |

### [pushover_notify.py](pushover_notify.py) - Pushover プッシュ通知

Pushover API 経由でスマホにプッシュ通知を送信します。
ワークフローのチェーンで failure/success 条件と組み合わせてアラートに使えます。

| 環境変数 | 必須 | 説明 |
|---|---|---|
| `PUSHOVER_TOKEN` | Yes | Pushover Application API Token |
| `PUSHOVER_USER` | Yes | Pushover User Key |
| `PUSHOVER_TITLE` | No | 通知タイトル (デフォルト: 自動生成) |
| `PUSHOVER_MESSAGE` | No | 通知本文 (デフォルト: 親ジョブの stdout) |
| `PUSHOVER_PRIORITY` | No | 優先度 -2〜2 (default: `0`) |
| `PUSHOVER_SOUND` | No | 通知音 |
| `PUSHOVER_DEVICE` | No | 送信先デバイス (default: 全デバイス) |

### [claude_usage_check.py](claude_usage_check.py) - Claude Code 使用量チェック

Claude Code の5時間ウィンドウ制限の残量を推定します。
CLI の `rate_limit_event` でリセット時刻を取得し、`ccusage` のコストデータと組み合わせて使用率・残りバジェット・バーンレートを表示します。

前提: `claude` CLI と `npx` (Node.js) がインストール済みであること。

| 環境変数 | 必須 | 説明 |
|---|---|---|
| `CLAUDE_MODEL` | No | チェック対象モデル (default: CLI のデフォルト) |
| `CLAUDE_5H_LIMIT_USD` | No | 5時間ウィンドウの推定コスト上限 (default: `148`) |

出力例:
```
5-Hour Window:
  Status: OK
  Resets: 14:00 JST (3h 44m)

Current Window Usage (estimated limit: $148):
  Cost:      $9.38 / $148 (6.3% used)
  Remaining: $138.62 (93.7%)
  Burn Rate: $14.21/hour
  At this rate, budget lasts: 9.8 hours
```

### [ai_summarize.sh](ai_summarize.sh) - AI 出力要約 (Claude CLI)

前段ジョブの stdout を `claude -p` で要約します。
ワークフロー内で中間処理として使い、要約結果を次のジョブ (Slack通知等) に渡せます。

| 環境変数 | 必須 | 説明 |
|---|---|---|
| `AI_PROMPT` | No | カスタムプロンプト (default: 要約指示) |
| `AI_SYSTEM` | No | システムプロンプト |
| `AI_MAX_INPUT` | No | 入力最大文字数 (default: `8000`) |

### [ai_log_analyzer.py](ai_log_analyzer.py) - AI ログ分析 (Claude CLI)

ログファイルを `claude -p` で分析し、エラーや異常を検出します。
日次 cron ジョブとして設定し、アプリケーションログの定期レビューに使えます。

| 環境変数 | 必須 | 説明 |
|---|---|---|
| `LOG_FILE` | Yes | 分析対象のログファイルパス |
| `LOG_TAIL` | No | 分析する末尾行数 (default: `200`) |
| `LOG_PATTERNS` | No | 注目パターン (default: `error,warn,fail,exception`) |
| `AI_PROMPT` | No | カスタムプロンプト |
| `AI_SYSTEM` | No | システムプロンプト |

### [disk_usage_alert.sh](disk_usage_alert.sh) - ディスク使用量アラート

ディスク使用率が閾値を超えたらアラートを出力しエラー終了します。

| 環境変数 | 必須 | 説明 |
|---|---|---|
| `DISK_THRESHOLD` | No | 閾値% (default: `80`) |
| `DISK_TARGET` | No | 対象マウントポイント (default: 全FS) |

## ワークフロー例

### 障害通知

```
[http_health_check] --failure--> [slack_thread_post]
```

ヘルスチェックが失敗したら Slack に通知するワークフロー:
1. `http_health_check.py` を `CHECK_URLS=https://example.com` で作成
2. `slack_thread_post.py` を作成 (SLACK_BOT_TOKEN, SLACK_CHANNEL を設定)
3. ワークフローで health_check → slack_thread_post を **failure** 条件で接続

### AI 要約 → 通知

```
[any-job] --any--> [ai_summarize] --success--> [slack_thread_post]
```

任意のジョブの出力を Claude で要約し、Slack にスレッド投稿:
1. 分析対象のジョブを作成 (例: `disk_usage_alert.sh`)
2. `ai_summarize.sh` をチェーンに追加 (**any** 条件)
3. `slack_thread_post.py` を最後に接続 (**success** 条件)

### 日次ログ分析

```
[ai_log_analyzer] --failure--> [pushover_notify]
```

ログにエラーが見つかったら Pushover で通知:
1. `ai_log_analyzer.py` を `LOG_FILE=/var/log/app.log` で cron 設定 (`0 9 * * *`)
2. `pushover_notify.py` を **failure** 条件でチェーン
