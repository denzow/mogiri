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

### [disk_usage_alert.sh](disk_usage_alert.sh) - ディスク使用量アラート

ディスク使用率が閾値を超えたらアラートを出力しエラー終了します。

| 環境変数 | 必須 | 説明 |
|---|---|---|
| `DISK_THRESHOLD` | No | 閾値% (default: `80`) |
| `DISK_TARGET` | No | 対象マウントポイント (default: 全FS) |

## ワークフロー例

```
[http_health_check] --failure--> [slack_thread_post]
```

ヘルスチェックが失敗したら Slack に通知するワークフロー:
1. `http_health_check.py` を `CHECK_URLS=https://example.com` で作成
2. `slack_thread_post.py` を作成 (SLACK_BOT_TOKEN, SLACK_CHANNEL を設定)
3. ワークフローで health_check → slack_thread_post を **failure** 条件で接続
