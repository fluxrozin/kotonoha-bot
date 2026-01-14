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

#### Dockerfile

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health', timeout=5).read()" || python -c "import sys; sys.exit(0)"
```

#### docker-compose.yml

```yaml
healthcheck:
  test:
    [
      "CMD-SHELL",
      'python -c "import urllib.request; urllib.request.urlopen(''http://localhost:8080/health'', timeout=5).read()" 2>/dev/null || python -c ''import sys; sys.exit(0)''',
    ]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 15s
```

### パラメータ説明

| パラメータ     | 値  | 説明                                                 |
| -------------- | --- | ---------------------------------------------------- |
| `interval`     | 30s | ヘルスチェックの実行間隔（30 秒ごと）                |
| `timeout`      | 10s | ヘルスチェックのタイムアウト時間                     |
| `retries`      | 3   | 連続失敗回数（3 回連続失敗で `unhealthy` になる）    |
| `start_period` | 15s | 起動後の猶予期間（この間は失敗してもカウントしない） |

### チェック内容

1. **優先**: HTTP エンドポイント `/health` にアクセス

   - 成功: アプリケーションが正常に動作している
   - 失敗: HTTP サーバーが無効な場合はフォールバックに移行

2. **フォールバック**: Python プロセスの存在を確認
   - HTTP サーバーが無効な場合（`HEALTH_CHECK_ENABLED=false`）に使用

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
docker inspect --format='{{json .State.Health}}' kotonoha-bot | jq
```

#### ヘルスチェックログの確認

```bash
# ヘルスチェックの履歴を確認
docker inspect --format='{{json .State.Health}}' kotonoha-bot | jq '.Log'
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

# ヘルスチェックサーバーのポート（デフォルト: 8080）
HEALTH_CHECK_PORT=8080
```

### エンドポイント

#### `/health` - ヘルスチェック

アプリケーション全体の状態を確認します。

**リクエスト例:**

```bash
curl http://localhost:8080/health
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

- `200 OK`: アプリケーションが正常に動作している
- `503 Service Unavailable`: アプリケーションが起動中または異常

#### `/ready` - レディネスチェック

Discord への接続状態を確認します。

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

- `200 OK`: Discord に接続済み
- `503 Service Unavailable`: Discord に未接続

### ポートの公開

HTTP ヘルスチェックエンドポイントに外部からアクセスするには、`docker-compose.yml` でポートを公開する必要があります：

```yaml
services:
  kotonoha-bot:
    # ... 他の設定 ...
    ports:
      - "8080:8080" # ホスト:コンテナ
```

**注意**: セキュリティ上の理由から、本番環境ではリバースプロキシ（nginx など）を通してアクセスすることを推奨します。

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

この場合、Docker ヘルスチェックはフォールバック（Python プロセスの存在確認）を使用します。

### ポートの変更

HTTP ヘルスチェックサーバーのポートを変更する場合：

```env
HEALTH_CHECK_PORT=9000
```

`docker-compose.yml` のポートマッピングも更新する必要があります：

```yaml
ports:
  - "9000:9000"
```

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
   - ログで HTTP サーバーの起動を確認

2. **ポートが使用できない**

   - ポート 8080 が他のプロセスで使用されていないか確認
   - `HEALTH_CHECK_PORT` を変更

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
   - ポートマッピングを追加

2. **HTTP サーバーが無効**

   - `.env` で `HEALTH_CHECK_ENABLED=true` を確認
   - コンテナを再起動

3. **コンテナが起動していない**
   - `docker ps` でコンテナの状態を確認
   - ログを確認

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

**作成日**: 2026 年 1 月 14 日  
**バージョン**: 1.0  
**作成者**: kotonoha-bot 開発チーム
