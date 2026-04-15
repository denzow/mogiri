# mogiri

ローカルで動作するシンプルなジョブ管理ツール。Web UIからジョブの作成・スケジュール実行・ログ閲覧ができます。

## Features

- **スケジュール実行** — cron式による定期実行、日時指定による一回実行
- **コマンド実行** — 任意のシェルコマンドを実行
- **環境変数** — ジョブごとにカスタム環境変数を設定可能
- **実行ログ** — stdout/stderrを保存し、Web UIから閲覧
- **ログローテーション** — 日数・件数ベースで古いログを自動削除
- **YAML設定** — `~/.mogiri/config.yaml` で設定を管理
- **Web UI** — モダンなUIでジョブ管理（htmx による部分更新）

## Requirements

- Python 3.10+

## Installation

```bash
pip install -e .
```

## Quick Start

```bash
# 設定ファイルの生成（オプション）
mogiri init

# サーバー起動
mogiri serve
```

ブラウザで http://127.0.0.1:8899 にアクセスしてください。

## Usage

### サーバー起動

```bash
# デフォルト (127.0.0.1:8899)
mogiri serve

# ポート・ホスト指定
mogiri serve --host 0.0.0.0 --port 9000

# 設定ファイルを指定
mogiri serve --config /path/to/config.yaml
```

### 設定ファイル

`mogiri init` で `~/.mogiri/config.yaml` にサンプルが生成されます。

```yaml
server:
  host: "127.0.0.1"
  port: 8899

log:
  # 指定日数より古い実行ログを削除 (0 = 無期限保持)
  retention_days: 30
  # ジョブごとの最大保持件数 (0 = 無制限)
  max_per_job: 100
```

環境変数で上書きすることもできます:

| 環境変数 | 説明 |
|---|---|
| `MOGIRI_DATA_DIR` | データディレクトリ (default: `~/.mogiri`) |
| `MOGIRI_LOG_RETENTION_DAYS` | ログ保持日数 |
| `MOGIRI_LOG_MAX_PER_JOB` | ジョブごとの最大保持件数 |

設定の優先順位: デフォルト値 < YAML < 環境変数 < CLIフラグ

### cron式の例

| 式 | 意味 |
|---|---|
| `* * * * *` | 毎分 |
| `*/5 * * * *` | 5分ごと |
| `0 * * * *` | 毎時0分 |
| `0 0 * * *` | 毎日0時 |
| `0 0 * * 0` | 毎週日曜0時 |
| `0 0 1 * *` | 毎月1日0時 |

## Development

```bash
# 開発用依存もインストール
pip install -e ".[dev]"

# テスト実行
pytest tests/ -v

# Lint
ruff check src/ tests/
```

### DBマイグレーション

スキーマ変更時は Flask-Migrate (Alembic) でマイグレーションを管理します。

```bash
# モデル変更後にマイグレーションファイルを生成
FLASK_APP=mogiri.app flask db migrate -m "add new column"

# マイグレーションを適用
FLASK_APP=mogiri.app flask db upgrade
```

`mogiri serve` 起動時に未適用のマイグレーションは自動で適用されます。

## Data

すべてのデータは `~/.mogiri/` に保存されます:

- `mogiri.db` — SQLiteデータベース（ジョブ定義・実行履歴）
- `config.yaml` — 設定ファイル

## License

MIT
