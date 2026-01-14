# デプロイメント・運用フロー

## 1. デプロイメントフロー

### 1.1 CI/CD パイプライン

```mermaid
graph LR
    A[開発者PC] -->|git push| B[GitHub]
    B -->|Trigger| C[GitHub Actions]
    C -->|Build| D[Docker Image]
    D -->|Push| E[GHCR]
    E -->|Check| F[Watchtower]
    F -->|Pull & Restart| G[Synology NAS]
```

### 1.2 デプロイメント手順

#### 1.2.1 初回デプロイ

1. **環境準備**

   ```bash
   # Synology NAS でディレクトリ作成
   mkdir -p /volume1/docker/kotonoha/{data,logs,backups}
   chmod 755 /volume1/docker/kotonoha/{data,logs,backups}
   ```

2. **環境変数設定**

   - Container Manager で環境変数を設定
   - `DISCORD_TOKEN` と `GEMINI_API_KEY` を設定

3. **Docker Compose 設定**

   `docker-compose.yml` の設定について:

   **ビルドとイメージの設定**:

   - `build` と `image` を両方指定することで、ローカルビルドと CI/CD の両方に対応できます
   - ローカルでビルドする場合: `docker compose build` でビルド
   - GHCR からプルする場合: `docker compose pull` でプル（または Watchtower が自動更新）
   - ローカルでビルドしたイメージに `image` で指定した名前（タグ）が付けられます

   **ユーザー設定**:

   - `user: root` でコンテナを起動し、`entrypoint.sh` がパーミッション修正後に `botuser` に切り替えます
   - これにより、ボリュームマウントされたディレクトリのパーミッション問題を自動的に解決します

   **ポート設定**:

   - `127.0.0.1:8081:8080` でヘルスチェック用のポートを公開（ローカルホストのみ）
   - セキュリティ上の理由から、外部から直接アクセスできないように制限されています

   詳細は [Phase 2 実装ガイド](../implementation/phases/phase2.md) を参照してください。

4. **コンテナ起動**

   ```bash
   docker-compose up -d
   ```

5. **動作確認**
   - ログの確認
   - ヘルスチェックの確認
   - Discord での動作確認

#### 1.2.2 通常のデプロイ（自動）

1. **コード変更**

   - 開発者がコードを変更
   - GitHub にプッシュ

2. **自動ビルド**

   - GitHub Actions が自動的にトリガー
   - Docker イメージをビルド
   - GHCR にプッシュ

3. **自動更新**

   - Watchtower が新しいイメージを検出
   - コンテナを自動再起動

4. **動作確認**
   - ログの確認
   - エラーの有無を確認

### 1.3 Watchtower について

**Watchtower とは**:

Watchtower は、Docker コンテナの自動更新ツールです。GitHub Container Registry (GHCR) から新しいイメージを定期的にチェックし、更新があれば自動的にコンテナを再起動して最新版に更新します。

**詳細**: <https://containrrr.dev/watchtower/>

**動作の仕組み**:

1. `kotonoha-bot` コンテナに `com.centurylinklabs.watchtower.enable=true` ラベルが付いている
2. Watchtower がこのラベルを検出し、定期的にイメージをチェック（デフォルト: 5 分ごと）
3. 新しいイメージがあれば自動的にコンテナを更新
4. 古いイメージを削除（`WATCHTOWER_CLEANUP=true` の場合）

**ローカル開発環境での使用**:

- ローカル開発環境では、`.env` ファイルで `WATCHTOWER_NOTIFICATION_URL` の行をコメントアウトしてください
- コメントアウトすることで、環境変数が未定義となり、Watchtowerは通知を送信しません
- 本番環境では、コメントアウトを解除して `WATCHTOWER_NOTIFICATION_URL` に Discord Webhook URL などを設定してください
- Container Manager（Synology NAS）でも、環境変数で制御できるため、GUI から簡単に設定できます

**設定項目**:

| 環境変数                      | 説明                               | デフォルト |
| ----------------------------- | ---------------------------------- | ---------- |
| `WATCHTOWER_CLEANUP`          | 古いイメージを自動削除             | `true`     |
| `WATCHTOWER_POLL_INTERVAL`    | イメージ更新チェック間隔（秒）     | `300`      |
| `WATCHTOWER_LABEL_ENABLE`     | ラベルで対象コンテナを制限         | `true`     |
| `WATCHTOWER_NOTIFICATIONS`    | 通知方法（shoutrrr）               | `shoutrrr` |
| `WATCHTOWER_NOTIFICATION_URL` | 通知先 URL（Discord Webhook など） | -          |
| `WATCHTOWER_SCHEDULE`         | cron 形式でのスケジュール          | -          |
| `WATCHTOWER_ROLLING_RESTART`  | 一度に 1 コンテナずつ更新          | `false`    |

#### Discord Webhook 通知の設定方法

Watchtower から Discord に更新通知を送信するには、Discord Webhook を作成して設定します。

##### 手順 1: Discord Webhook の作成

1. **Discord サーバーを開く**

   - 通知を受け取りたい Discord サーバーを開く
   - サーバー管理者権限が必要です

2. **サーバー設定を開く**

   - サーバー名を右クリック → 「サーバーの設定」を選択
   - または、サーバー名の横の下矢印をクリック → 「サーバーの設定」

3. **連携サービスに移動**

   - 左メニューから「連携サービス」を選択
   - 「ウェブフック」タブを開く

4. **新しいウェブフックを作成**

   - 「新しいウェブフック」ボタンをクリック
   - または、通知を送信したいチャンネルを右クリック → 「連携サービス」→「ウェブフック」→「新規ウェブフック」

5. **ウェブフックを設定**

   - **名前**: 任意の名前（例: "Watchtower"）
   - **チャンネル**: 通知を送信するチャンネルを選択
   - 「ウェブフック URL をコピー」をクリック

6. **ウェブフック URL を保存**

   - コピーした URL は以下の形式です:

     ```txt
     https://discord.com/api/webhooks/WEBHOOK_ID/WEBHOOK_TOKEN
     ```

   - 例: `https://discord.com/api/webhooks/123456789012345678/abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ`

##### 手順 2: 環境変数の設定

1. **`.env` ファイルを開く**

   ```bash
   # プロジェクトディレクトリで
   nano .env
   # または
   vi .env
   ```

2. **Webhook URL から ID とトークンを抽出**

   Webhook URL の形式:

   ```txt
   https://discord.com/api/webhooks/WEBHOOK_ID/WEBHOOK_TOKEN
   ```

   例:

   ```txt
   https://discord.com/api/webhooks/123456789012345678/abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ
   ```

   - `WEBHOOK_ID`: `123456789012345678`（URL の `/webhooks/` の後）
   - `WEBHOOK_TOKEN`: `abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ`（ID の後の `/` の後）

3. **`.env` ファイルに設定を追加**

   ```bash
   # Watchtower 通知設定
   WATCHTOWER_NOTIFICATIONS=shoutrrr
   WATCHTOWER_NOTIFICATION_URL=discord://WEBHOOK_TOKEN@WEBHOOK_ID
   ```

   **実際の例**:

   ```bash
   WATCHTOWER_NOTIFICATIONS=shoutrrr
   WATCHTOWER_NOTIFICATION_URL=discord://abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ@123456789012345678
   ```

   **重要**:

   - 形式は `discord://TOKEN@ID` です（URL とは順序が逆）
   - `@` の前がトークン、`@` の後が ID です

4. **コンテナを再起動**

   ```bash
   docker-compose restart watchtower
   ```

##### 手順 3: 動作確認

1. **Watchtower のログを確認**

   ```bash
   docker logs watchtower
   ```

2. **テスト通知を送信**（オプション）

   Watchtower が正常に動作している場合、コンテナ更新時に自動的に通知が送信されます。
   手動でテストする場合は、Watchtower のログで通知の送信状況を確認できます。

3. **Discord チャンネルで確認**

   - 設定したチャンネルに Watchtower からの通知が表示されることを確認
   - 通知には以下の情報が含まれます:
     - 更新されたコンテナ名
     - 更新時刻
     - イメージ情報

##### 通知の例

```txt
🔄 Watchtower がコンテナを更新しました

コンテナ: kotonoha-bot
イメージ: ghcr.io/your-username/kotonoha-bot:latest
時刻: 2026-01-15 10:30:00 UTC
```

##### トラブルシューティング

- **通知が届かない場合**:

  1. Webhook URL が正しいか確認
  2. `.env` ファイルの形式が正しいか確認（`discord://TOKEN@ID`）
  3. Watchtower のログでエラーを確認: `docker logs watchtower`
  4. Webhook が削除されていないか確認（Discord の連携サービスで確認）

- **Webhook を削除した場合**:
  - 新しい Webhook を作成して、`.env` ファイルを更新
  - Watchtower コンテナを再起動

---

## 2. 運用フロー

### 2.1 日常運用

#### 2.1.1 ログ確認

```bash
# リアルタイムログ確認
docker logs -f kotonoha-bot

# 最新100行のログ確認
docker logs --tail 100 kotonoha-bot

# エラーログのみ確認
docker logs kotonoha-bot 2>&1 | grep ERROR
```

#### 2.1.2 ヘルスチェック

詳細は [ヘルスチェックドキュメント](./health-check.md) を参照してください。

```bash
# Docker ヘルスチェックの状態を確認
docker ps

# HTTP ヘルスチェックエンドポイントにアクセス（ポート公開時）
curl http://localhost:8080/health

# 期待される応答
{"status": "healthy", "discord": "connected", "sessions": 5}
```

#### 2.1.3 リソース監視

```bash
# コンテナのリソース使用状況
docker stats kotonoha-bot
```

### 2.2 バックアップ運用

#### 2.2.1 手動バックアップ

```bash
# データベースのバックアップ
docker exec kotonoha-bot python -m kotonoha_bot.scripts.backup

# または直接コピー
cp /volume1/docker/kotonoha/data/kotonoha.db \
   /volume1/docker/kotonoha/backups/kotonoha_$(date +%Y%m%d_%H%M%S).db
```

#### 2.2.2 自動バックアップ

- 1 日 1 回（深夜 0 時）に自動実行
- 7 日分のバックアップを保持
- 7 日以上古いバックアップは自動削除

#### 2.2.3 リストア

```bash
# バックアップからリストア
cp /volume1/docker/kotonoha/backups/kotonoha_YYYYMMDD_HHMMSS.db \
   /volume1/docker/kotonoha/data/kotonoha.db

# コンテナ再起動
docker-compose restart kotonoha
```

### 2.3 トラブルシューティング

#### 2.3.1 Bot が応答しない

1. **ログ確認**

   ```bash
   docker logs kotonoha-bot --tail 50
   ```

2. **接続状態確認**

   - Discord API への接続状態を確認
   - トークンの有効性を確認

3. **コンテナ再起動**

   ```bash
   docker-compose restart kotonoha
   ```

#### 2.3.2 API エラー

1. **エラーログ確認**

   ```bash
   docker logs kotonoha-bot | grep ERROR
   ```

2. **API キーの確認**

   - Anthropic API キーの有効性
   - レート制限の状態

3. **リトライ**
   - 自動リトライを待つ
   - 手動でコンテナ再起動

#### 2.3.3 データベースエラー

1. **データベースファイルの確認**

   ```bash
   ls -lh /volume1/docker/kotonoha/data/kotonoha.db
   ```

2. **データベースの整合性チェック**

   ```bash
   docker exec kotonoha-bot sqlite3 /app/data/kotonoha.db "PRAGMA integrity_check;"
   ```

3. **バックアップからリストア**
   - 最新のバックアップからリストア

---

## 3. モニタリング

### 3.1 監視項目

| 項目                     | 閾値    | アクション               |
| ------------------------ | ------- | ------------------------ |
| **メモリ使用量**         | > 500MB | 警告ログ出力             |
| **CPU 使用率**           | > 80%   | 警告ログ出力             |
| **API レート制限使用率** | > 80%   | 警告ログ出力             |
| **エラー率**             | > 5%    | 警告ログ出力、管理者通知 |
| **応答時間**             | > 10 秒 | 警告ログ出力             |

### 3.2 ログ監視

```bash
# エラーログの監視
tail -f /volume1/docker/kotonoha/logs/kotonoha.log | grep ERROR

# レート制限の監視
tail -f /volume1/docker/kotonoha/logs/kotonoha.log | grep "rate limit"
```

### 3.3 アラート設定

- **Discord チャンネル**: 管理者用チャンネルに通知
- **ログファイル**: エラーログに記録
- **メール通知**: 将来の拡張（オプション）

---

## 4. メンテナンス

### 4.1 定期メンテナンス

| 作業                   | 頻度       | 内容                     |
| ---------------------- | ---------- | ------------------------ |
| **ログローテーション** | 1 週間ごと | 古いログファイルの削除   |
| **データベース最適化** | 1 ヶ月ごと | `VACUUM` の実行          |
| **バックアップ確認**   | 1 週間ごと | バックアップの整合性確認 |
| **依存関係の更新**     | 3 ヶ月ごと | ライブラリの更新         |

### 4.2 データベース最適化

```bash
# SQLite の最適化
docker exec kotonoha-bot sqlite3 /app/data/kotonoha.db "VACUUM;"

# インデックスの再構築
docker exec kotonoha-bot sqlite3 /app/data/kotonoha.db "REINDEX;"
```

### 4.3 ログローテーション

```bash
# ログファイルのローテーション
logrotate -f /etc/logrotate.d/kotonoha
```

---

## 5. アップグレード手順

### 5.1 マイナーアップグレード

1. **コード更新**

   - GitHub にプッシュ
   - 自動デプロイを待つ

2. **動作確認**
   - ログの確認
   - 機能の動作確認

### 5.2 メジャーアップグレード

1. **バックアップ**

   ```bash
   docker exec kotonoha-bot python -m kotonoha_bot.scripts.backup
   ```

2. **データベースマイグレーション**

   ```bash
   docker exec kotonoha-bot python -m kotonoha_bot.scripts.migrate
   ```

3. **コード更新**

   - GitHub にプッシュ
   - 自動デプロイを待つ

4. **動作確認**
   - ログの確認
   - 機能の動作確認
   - データの整合性確認

---

## 6. ロールバック手順

### 6.1 緊急ロールバック

1. **現在のイメージタグを確認**

   ```bash
   docker inspect kotonoha-bot | grep Image
   ```

2. **前のバージョンに戻す**

   ```bash
   docker-compose pull kotonoha:previous-version
   docker-compose up -d kotonoha
   ```

3. **動作確認**
   - ログの確認
   - 機能の動作確認

### 6.2 データロールバック

1. **バックアップからリストア**

   ```bash
   cp /volume1/docker/kotonoha/backups/kotonoha_YYYYMMDD_HHMMSS.db \
      /volume1/docker/kotonoha/data/kotonoha.db
   ```

2. **コンテナ再起動**

   ```bash
   docker-compose restart kotonoha
   ```

---

**作成日**: 2026 年 1 月 14 日
**バージョン**: 1.0
**作成者**: kotonoha-bot 開発チーム
