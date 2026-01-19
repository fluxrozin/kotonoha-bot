# ヘルスチェック - Kotonoha Discord Bot

Kotonoha Bot のヘルスチェック機能についてのドキュメント

## 目次

1. [概要](#概要)
2. [Docker ヘルスチェック](#docker-ヘルスチェック)
3. [HTTP ヘルスチェックエンドポイント](#http-ヘルスチェックエンドポイント)
4. [使用方法](#使用方法)
5. [設定](#設定)
6. [トラブルシューティング](#トラブルシューティング)

---

## 概要

Kotonoha Bot は 2 種類のヘルスチェック機能を提供しています：

1. **Docker ヘルスチェック**: Docker が自動的にコンテナの状態を監視
2. **HTTP ヘルスチェックエンドポイント**: アプリケーションの詳細な状態を HTTP で確認

### ヘルスチェックの目的

- コンテナの正常性を自動監視
- アプリケーションの状態を確認
- 障害の早期検出
- 自動再起動のトリガー

---

## Docker ヘルスチェック

Docker が定期的にコンテナの状態を確認し、正常性を判定します。

### Docker ヘルスチェックの設定

#### docker-compose.yml

`docker-compose.yml` で設定されています：

```yaml
healthcheck:
  test:
    [
      "CMD",
      "python",
      "-c",
      "import urllib.request; "
      "urllib.request.urlopen('http://localhost:8080/health', timeout=5).read()",
    ]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 15s
```

**実装箇所**: `docker-compose.yml` (41-52 行目)

**注意**: `Dockerfile` には `HEALTHCHECK` ディレクティブは設定されていません。
`docker-compose.yml` でのみ設定されています。

### パラメータ説明

| パラメータ     | 値  | 説明                                                 |
| -------------- | --- | ---------------------------------------------------- |
| `interval`     | 30s | ヘルスチェックの実行間隔（30 秒ごと）                |
| `timeout`      | 10s | ヘルスチェックのタイムアウト時間                     |
| `retries`      | 3   | 連続失敗回数（3 回連続失敗で `unhealthy` になる）    |
| `start_period` | 15s | 起動後の猶予期間（この間は失敗してもカウントしない） |

### チェック内容

1. **HTTP エンドポイント `/health` にアクセス**
   - 成功: アプリケーションが正常に動作している
   - 失敗: HTTP サーバーが無効な場合はエラーになる

**注意**: 現在の実装では、HTTP サーバーが無効な場合のフォールバック
（Python プロセスの存在確認）は実装されていません。

### 状態の確認

#### コンテナの状態を確認

```bash
# コンテナの状態を確認（STATUS列に healthy/unhealthy が表示される）
docker ps

# 例:
# CONTAINER ID   IMAGE              STATUS                    NAMES
# abc123def456   kotonoha-bot:latest   Up 2 minutes (healthy)   kotonoha-bot
```

#### 詳細なヘルスチェック情報を確認

```bash
# JSON形式で詳細情報を取得
docker inspect kotonoha-bot | grep -A 20 Health

# または jq を使用（より見やすく）
# 注意: jq は JSON 処理用のコマンドラインツールです。
# インストール方法: apt install jq (Debian/Ubuntu) または brew install jq (macOS)
docker inspect --format='{{json .State.Health}}' kotonoha-bot | jq
```

**jq について**:

- `jq` は JSON データを処理するためのコマンドラインツールです（ライブラリではありません）
- JSON の整形、フィルタリング、検索などが可能
- インストール方法:
  - Debian/Ubuntu: `apt install jq`
  - macOS: `brew install jq`
  - または [公式サイト](https://stedolan.github.io/jq/) からダウンロード

**jq がインストールされていない場合**:

```bash
# jq なしでも確認可能（JSON がそのまま表示される）
docker inspect --format='{{json .State.Health}}' kotonoha-bot
```

#### ヘルスチェックログの確認

```bash
# ヘルスチェックの履歴を確認（jq を使用）
docker inspect --format='{{json .State.Health}}' kotonoha-bot | jq '.Log'

# jq がインストールされていない場合
docker inspect --format='{{json .State.Health}}' kotonoha-bot | \
  python3 -m json.tool | grep -A 10 Log
```

### 状態の種類

| 状態        | 説明                             |
| ----------- | -------------------------------- |
| `starting`  | 起動中（`start_period` 内）      |
| `healthy`   | 正常（ヘルスチェックが成功）     |
| `unhealthy` | 異常（`retries` 回連続で失敗）   |
| `none`      | ヘルスチェックが設定されていない |

---

## HTTP ヘルスチェックエンドポイント

アプリケーション内で HTTP サーバーを起動し、詳細な状態情報を提供します。

### HTTP ヘルスチェックの設定

`.env` ファイルで設定：

```env
# ヘルスチェックサーバーを有効化（デフォルト: true）
HEALTH_CHECK_ENABLED=true

# 注意: ポート番号は固定（8080）です。
# Config.HEALTH_CHECK_PORT で設定されています。
```

**実装箇所**: `src/kotonoha_bot/health.py`, `src/kotonoha_bot/config.py`

### エンドポイント

#### `/health` または `/` - ヘルスチェック

アプリケーション全体の状態を確認します。

**実装箇所**: `src/kotonoha_bot/health.py` (33-51 行目)

**リクエスト例:**

```bash
curl http://localhost:8080/health
# または
curl http://localhost:8080/
```

**レスポンス例（正常時）:**

```json
{
  "status": "healthy",
  "discord": "connected",
  "sessions": 5
}
```

**レスポンス例（起動中）:**

```json
{
  "status": "starting",
  "discord": "disconnected",
  "sessions": 0
}
```

**HTTP ステータスコード:**

- `200 OK`: アプリケーションが正常に動作している（`status` が `"healthy"`）
- `503 Service Unavailable`: アプリケーションが起動中または異常（`status` が `"starting"`）
- `500 Internal Server Error`: エラーが発生した場合

**ステータスの判定基準:**

- `status`: Discord Bot が接続済み（`bot.is_ready()`）の場合は `"healthy"`、それ以外は `"starting"`
- `discord`: Discord Bot が接続済みの場合は `"connected"`、それ以外は `"disconnected"`
- `sessions`: 現在のアクティブセッション数

#### `/ready` - レディネスチェック

Discord への接続状態を確認します。

**実装箇所**: `src/kotonoha_bot/health.py` (53-71 行目)

**リクエスト例:**

```bash
curl http://localhost:8080/ready
```

**レスポンス例（接続済み）:**

```json
{
  "ready": true
}
```

**レスポンス例（未接続）:**

```json
{
  "ready": false
}
```

**HTTP ステータスコード:**

- `200 OK`: Discord に接続済み（`ready` が `true`）
- `503 Service Unavailable`: Discord に未接続（`ready` が `false`）
- `500 Internal Server Error`: エラーが発生した場合

**判定基準:**

- `ready`: Discord Bot が接続済み（`bot.is_ready()`）の場合は `true`、それ以外は `false`

### ポートの公開

HTTP ヘルスチェックエンドポイントに外部からアクセスするには、
`docker-compose.yml` でポートを公開する必要があります：

```yaml
services:
  kotonoha-bot:
    # ... 他の設定 ...
    ports:
      - "127.0.0.1:8081:8080" # ホスト:コンテナ（ローカルホストのみ）
      # または
      - "8080:8080" # ホスト:コンテナ（すべてのインターフェース）
```

**実装箇所**: `docker-compose.yml` (38-39 行目)

**注意**: セキュリティ上の理由から、本番環境ではリバースプロキシ（nginx など）を通してアクセスすることを推奨します。

### サーバーの起動

ヘルスチェックサーバーは、Bot の起動前に起動されます。
これにより、Bot の状態に関わらずヘルスチェックに応答できます。

**実装箇所**: `src/kotonoha_bot/main.py` (111 行目)

```python
# ヘルスチェックサーバーを先に起動
# （Botの状態に関わらずヘルスチェックに応答するため）
health_server.start()
```

---

## 使用方法

### 1. コンテナの状態確認

```bash
# コンテナの状態を確認
docker ps

# 詳細情報を確認
docker inspect kotonoha-bot | grep -A 20 Health
```

### 2. HTTP エンドポイントへのアクセス

#### コンテナ内から

```bash
# コンテナ内で実行
docker exec kotonoha-bot curl http://localhost:8080/health
```

#### 外部から（ポート公開時）

```bash
# ヘルスチェック
curl http://localhost:8080/health

# レディネスチェック
curl http://localhost:8080/ready
```

#### Synology NAS にデプロイしている場合

現在の設定（`docker-compose.yml`）では、ポートは `127.0.0.1:8081:8080` にバインドされているため、
**ローカルホスト（127.0.0.1）からのみアクセス可能**です。

**アクセス方法**:

1. **SSH で NAS に接続してアクセス（推奨）**

   ```bash
   # SSH で NAS に接続
   ssh admin@nas-ip-address

   # プロジェクトディレクトリに移動
   cd /volume1/docker/kotonoha-bot

   # ヘルスチェック（ポート 8081 を使用）
   curl http://localhost:8081/health

   # レディネスチェック
   curl http://localhost:8081/ready
   ```

2. **ポート設定を変更して外部からアクセス可能にする（非推奨）**

   `docker-compose.yml` の `ports` セクションを変更：

   ```yaml
   ports:
     - "8081:8080" # すべてのインターフェースからアクセス可能
   ```

   **注意**: セキュリティ上の理由から、この方法は非推奨です。
   外部から直接アクセスできるようになるため、適切な認証やファイアウォール設定が必要です。

3. **Synology のリバースプロキシを使用（推奨）**

   Synology の Control Panel > Application Portal > Reverse Proxy で設定：

   - **Source**: `https://your-nas-domain.com/health`（外部からアクセスする URL）
   - **Destination**: `http://localhost:8081/health`（コンテナのポート）
   - **SSL 証明書**: Let's Encrypt などを設定

   これにより、HTTPS で安全にアクセスできます。

**現在の設定でのアクセス**:

- **NAS 内から**: `http://localhost:8081/health`（SSH 経由でアクセス）
- **外部から**: 直接アクセス不可（リバースプロキシを使用する必要がある）

### 3. モニタリングツールとの連携

#### Prometheus との連携例

```yaml
# prometheus.yml
scrape_configs:
  - job_name: "kotonoha-bot"
    static_configs:
      - targets: ["localhost:8080"]
    metrics_path: "/health"
```

#### シェルスクリプトでの監視例

```bash
#!/bin/bash
# health_monitor.sh

HEALTH_URL="http://localhost:8080/health"
MAX_RETRIES=3
RETRY_INTERVAL=10

for i in $(seq 1 $MAX_RETRIES); do
    response=$(curl -s -o /dev/null -w "%{http_code}" $HEALTH_URL)

    if [ "$response" = "200" ]; then
        echo "Health check passed"
        exit 0
    fi

    echo "Health check failed (attempt $i/$MAX_RETRIES)"
    sleep $RETRY_INTERVAL
done

echo "Health check failed after $MAX_RETRIES attempts"
exit 1
```

---

## 設定

### ヘルスチェックの無効化

HTTP ヘルスチェックサーバーを無効化する場合：

```env
HEALTH_CHECK_ENABLED=false
```

この場合、HTTP サーバーは起動せず、Docker ヘルスチェックは失敗します。

**実装箇所**: `src/kotonoha_bot/health.py` (90-92 行目)

```python
if not Config.HEALTH_CHECK_ENABLED:
    logger.info("Health check server is disabled")
    return
```

### ポートの変更

HTTP ヘルスチェックサーバーのポートを変更する場合：

**注意**: ポート番号は `Config.HEALTH_CHECK_PORT` で固定（8080）です。
変更する場合は `src/kotonoha_bot/config.py` を手動で更新し、
`docker-compose.yml` の `ports` と `healthcheck` も更新してください。

### ヘルスチェック間隔の変更

`docker-compose.yml` で変更：

```yaml
healthcheck:
  interval: 60s # 60秒ごとにチェック
  timeout: 15s # タイムアウトを15秒に
  retries: 5 # 5回連続失敗で unhealthy
  start_period: 30s # 起動後30秒間は猶予
```

---

## トラブルシューティング

### 問題: コンテナが `unhealthy` になる

**症状:**

```bash
$ docker ps
CONTAINER ID   IMAGE              STATUS
abc123def456   kotonoha-bot:latest   Up 5 minutes (unhealthy)
```

**原因と解決方法:**

1. **HTTP サーバーが起動していない**

   - `.env` で `HEALTH_CHECK_ENABLED=true` を確認
   - ログで HTTP サーバーの起動を確認: `docker logs kotonoha-bot | grep "Health check server"`
   - コンテナを再起動: `docker compose restart kotonoha-bot`

2. **ポートが使用できない**

   - ポート 8080 が他のプロセスで使用されていないか確認
   - ポートを変更する場合は `config.py` と `docker-compose.yml` を手動で更新

3. **アプリケーションがクラッシュしている**
   - ログを確認: `docker logs kotonoha-bot`
   - エラーメッセージを確認

### 問題: HTTP エンドポイントにアクセスできない

**症状:**

```bash
$ curl http://localhost:8080/health
curl: (7) Failed to connect to localhost port 8080: Connection refused
```

**原因と解決方法:**

1. **ポートが公開されていない**

   - `docker-compose.yml` で `ports` セクションを確認
   - ポートマッピングを追加: `"127.0.0.1:8081:8080"`

2. **HTTP サーバーが無効**

   - `.env` で `HEALTH_CHECK_ENABLED=true` を確認
   - コンテナを再起動: `docker compose restart kotonoha-bot`

3. **コンテナが起動していない**
   - `docker ps` でコンテナの状態を確認
   - ログを確認: `docker logs kotonoha-bot`

### 問題: ヘルスチェックが頻繁に失敗する

**症状:**

ヘルスチェックが `healthy` と `unhealthy` を繰り返す

**原因と解決方法:**

1. **タイムアウトが短すぎる**

   - `timeout` を増やす（例: 10s → 15s）

2. **アプリケーションの起動に時間がかかる**

   - `start_period` を増やす（例: 15s → 30s）

3. **リソース不足**
   - メモリや CPU の使用状況を確認
   - `docker stats kotonoha-bot` で確認

### 問題: ヘルスチェックが常に `starting` のまま

**症状:**

```bash
$ docker ps
CONTAINER ID   IMAGE              STATUS
abc123def456   kotonoha-bot:latest   Up 10 minutes (health: starting)
```

**原因と解決方法:**

1. **`start_period` が長すぎる**

   - `start_period` を短くする（例: 30s → 15s）

2. **アプリケーションが起動に失敗している**
   - ログを確認: `docker logs kotonoha-bot`
   - エラーメッセージを確認
   - Discord トークンが正しく設定されているか確認

---

## ベストプラクティス

1. **定期的な監視**

   - ヘルスチェックの状態を定期的に確認
   - モニタリングツールと連携

2. **適切な間隔設定**

   - 過度に短い間隔は負荷を増やす
   - 過度に長い間隔は障害検出が遅れる
   - 30 秒〜60 秒が推奨

3. **ログの確認**

   - ヘルスチェックの失敗時は必ずログを確認
   - エラーパターンを記録

4. **アラート設定**
   - `unhealthy` 状態になったら通知
   - モニタリングツールと連携

---

## 実装の詳細

### ヘルスチェックサーバーの実装

**実装箇所**: `src/kotonoha_bot/health.py`

**主要クラス**:

- `HealthCheckHandler`: HTTP リクエストハンドラー
- `HealthCheckServer`: ヘルスチェックサーバー

**サーバーの起動**:

- デーモンスレッドで HTTP サーバーを起動
- Bot の起動前に起動される（`main.py` の 111 行目）
- Bot の状態に関わらずヘルスチェックに応答可能

**ステータス取得コールバック**:

- `main.py` で `get_health_status()` 関数を設定
- Discord Bot の接続状態とセッション数を返す

### エンドポイントの実装

**`/health` エンドポイント**:

- `HealthCheckHandler._handle_health()` で処理
- ステータス取得コールバックから状態を取得
- `status` が `"healthy"` の場合は 200、それ以外は 503 を返す

**`/ready` エンドポイント**:

- `HealthCheckHandler._handle_ready()` で処理
- Discord Bot の接続状態のみを確認
- `discord` が `"connected"` の場合は 200、それ以外は 503 を返す

**`/` エンドポイント**:

- `/health` と同じ処理（`self.path == "/"` の場合も `/health` として処理）

---

**作成日**: 2026 年 1 月 14 日  
**最終更新**: 2026 年 1 月（現在の実装に基づいて改訂）  
**バージョン**: 2.0  
**作成者**: kotonoha-bot 開発チーム
