# mogiri

ローカルで動作するシンプルなジョブ管理ツール。Web UIからジョブの作成・スケジュール実行・ログ閲覧ができます。

## Features

- **スケジュール実行** — cron式による定期実行、日時指定による一回実行
- **コマンド実行** — 任意のシェルコマンドを実行
- **環境変数** — ジョブごとにカスタム環境変数を設定可能
- **実行ログ** — stdout/stderrを保存し、Web UIから閲覧
- **ログローテーション** — 日数・件数ベースで古いログを自動削除
- **ワークフロー** — 複数ジョブをDAGで連結し、成功/失敗条件で分岐実行
- **AI アシスタント** — ジョブ作成画面でClaude/Gemini CLIによるスクリプト生成支援
- **REST API** — ジョブ・ワークフロー・実行履歴・設定のJSON API
- **CLI クライアント** — `mogiricli` コマンドでターミナルからジョブ管理
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

## CLI クライアント (mogiricli)

mogiriサーバーの REST API をラップした CLI ツールです。ターミナルや Claude Code からジョブ・ワークフローを操作できます。

```bash
# サーバーURLの設定（デフォルト: http://127.0.0.1:8899）
export MOGIRI_URL=http://127.0.0.1:8899
```

### ジョブ管理

```bash
# 一覧
mogiricli jobs list

# 詳細
mogiricli jobs get <id>

# 作成
mogiricli jobs create --name "バックアップ" --command "pg_dump mydb" --command-type shell
mogiricli jobs create --name "ヘルスチェック" --command "$(cat script.py)" --command-type python

# 更新
mogiricli jobs update <id> --name "新しい名前" --schedule-type cron --schedule-value "0 * * * *"

# 削除
mogiricli jobs delete <id> --yes

# 即時実行
mogiricli jobs run <id>
```

### ワークフロー管理

```bash
mogiricli workflows list
mogiricli workflows create --name "監視フロー"
mogiricli workflows run <id>
mogiricli workflows delete <id> --yes
```

### 実行履歴

```bash
# 直近の実行一覧
mogiricli executions list --limit 10

# 特定ジョブの実行履歴
mogiricli executions list --job-id <id>

# 実行詳細（stdout/stderr含む）
mogiricli executions get <execution-id>
```

### 設定

```bash
mogiricli settings get ai_provider
mogiricli settings set ai_provider gemini
```

### JSON 出力

`--json` フラグで JSON 形式の出力に切り替えられます。スクリプトや Claude Code との連携に便利です。

```bash
mogiricli --json jobs list
mogiricli --json executions get <id>
```

## REST API

mogiriサーバーは JSON API を提供しています。`mogiricli` はこの API のラッパーです。

| メソッド | パス | 説明 |
|----------|------|------|
| `GET` | `/api/jobs` | ジョブ一覧 |
| `GET` | `/api/jobs/<id>` | ジョブ詳細 |
| `POST` | `/api/jobs` | ジョブ作成 |
| `PATCH` | `/api/jobs/<id>` | ジョブ更新 |
| `DELETE` | `/api/jobs/<id>` | ジョブ削除 |
| `POST` | `/api/jobs/<id>/run` | ジョブ即時実行 |
| `GET` | `/api/workflows` | ワークフロー一覧 |
| `GET` | `/api/workflows/<id>` | ワークフロー詳細 |
| `POST` | `/api/workflows` | ワークフロー作成 |
| `PATCH` | `/api/workflows/<id>` | ワークフロー更新 |
| `DELETE` | `/api/workflows/<id>` | ワークフロー削除 |
| `POST` | `/api/workflows/<id>/run` | ワークフロー実行 |
| `GET` | `/api/executions` | 実行履歴一覧 (`?job_id=`, `?workflow_id=`, `?limit=`) |
| `GET` | `/api/executions/<id>` | 実行詳細 (stdout/stderr含む) |
| `GET` | `/api/settings/<key>` | 設定取得 |
| `PUT` | `/api/settings/<key>` | 設定更新 |

## Data

すべてのデータは `~/.mogiri/` に保存されます:

- `mogiri.db` — SQLiteデータベース（ジョブ定義・実行履歴）
- `config.yaml` — 設定ファイル

## License

MIT
