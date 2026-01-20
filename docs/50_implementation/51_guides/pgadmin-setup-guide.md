# pgAdmin セットアップガイド

このドキュメントでは、Kotonoha BotプロジェクトでpgAdminを使用するためのセットアップ方法について説明します。

## 目次

1. [概要](#概要)
2. [セキュリティ対策](#セキュリティ対策)
3. [実装手順](#実装手順)
4. [使用方法](#使用方法)
5. [よくある操作](#よくある操作)
6. [トラブルシューティング](#トラブルシューティング)
7. [セキュリティチェックリスト](#セキュリティチェックリスト)

---

## 概要

### 基本方針

- **Docker Composeのプロファイル機能を使用**: 開発環境でのみ有効化
- **本番環境では起動しない**: セキュリティを確保
- **環境変数で制御**: 認証情報とアクセス設定を管理

### なぜこの方法か

1. **セキュリティ**: 本番環境での誤起動を防止
2. **シンプル**: プロファイル指定で制御
3. **明確**: 起動方法で意図が明確
4. **柔軟**: 必要な時だけ起動可能

### pgAdminとは

pgAdminは、PostgreSQLデータベースを管理するためのWebベースのGUIツールです。

- データベースの閲覧・編集
- SQLクエリの実行
- テーブル構造の確認
- インデックスの管理
- データのエクスポート・インポート

---

## セキュリティ対策

### 対策1: プロファイルによる起動制御

- 本番環境では`docker compose up -d`のみ実行
- プロファイルを指定しない限り起動しない

### 対策2: ローカルホストのみバインド（デフォルト）

- `127.0.0.1:5050:80`で外部アクセスを遮断
- 同一LAN内アクセスが必要な場合は環境変数で切り替え可能

### 対策3: 強力なパスワード必須化

- 環境変数で認証情報を設定（デフォルト値なし）
- 弱いパスワードの使用を防止

### 対策4: 開発環境でのみ使用

- `.env`に設定を追加するのは開発環境のみ
- 本番環境では設定を追加しない

---

## 実装手順

### ステップ1: docker-compose.ymlに追加

`watchtower`サービスの後に以下を追加：

```yaml
  # pgAdmin（開発環境のみ、プロファイルで制御）
  # 使用方法: docker compose --profile pgadmin up -d pgadmin
  # ⚠️ 本番環境では使用しないこと
  pgadmin:
    image: dpage/pgadmin4:latest
    container_name: kotonoha-pgadmin
    restart: unless-stopped
    profiles:
      - pgadmin
    environment:
      # 環境変数で認証情報を設定（.envファイルに追加）
      # 開発環境でのみ設定すること
      PGADMIN_DEFAULT_EMAIL: ${PGADMIN_EMAIL:?pgAdmin email is required}
      PGADMIN_DEFAULT_PASSWORD: ${PGADMIN_PASSWORD:?pgAdmin password is required}
      PGADMIN_CONFIG_SERVER_MODE: 'False'
      PGADMIN_CONFIG_MASTER_PASSWORD_REQUIRED: 'False'
    volumes:
      - pgadmin_data:/var/lib/pgadmin
    networks:
      - kotonoha-network
    ports:
      # 環境変数で制御（デフォルト: 127.0.0.1 = ローカルホストのみ）
      # 同一LAN内からアクセスする場合: .env に PGADMIN_BIND_ADDRESS=0.0.0.0 を設定
      - "${PGADMIN_BIND_ADDRESS:-127.0.0.1}:5050:80"
    depends_on:
      postgres:
        condition: service_healthy
```

### ステップ2: volumesセクションに追加

`volumes`セクションに以下を追加：

```yaml
volumes:
  postgres_data:
  pgadmin_data:  # ← これを追加
```

### ステップ3: .env.exampleに追加

`.env.example`の最後（Watchtower設定の後）に以下を追加：

```bash
# ============================================================================
# pgAdmin 設定（開発環境のみ、オプション）
# ============================================================================

# ⚠️ 重要: 本番環境では設定しないこと
# 開発環境でのみ使用する場合、以下の環境変数のコメントを外して設定してください
# 強力なパスワードを設定すること（推奨: 20文字以上、英数字+記号）

# pgAdminログイン用メールアドレス
# 注意: .localドメインも使用可能ですが、有効なメールアドレス形式（例: admin@example.com）を推奨
# PGADMIN_EMAIL=admin@example.com

# pgAdminログイン用パスワード（強力なパスワードを設定すること）
# PGADMIN_PASSWORD=your_strong_password_here

# pgAdminポートバインディング設定（オプション）
# デフォルト: 127.0.0.1（ローカルホストのみ、セキュア）
# 同一LAN内からアクセスする場合: 0.0.0.0
# ⚠️ セキュリティ警告: 0.0.0.0 に設定する場合は強力なパスワードを必須とすること
# 本番環境では使用しないこと
# PGADMIN_BIND_ADDRESS=127.0.0.1
```

---

## 使用方法

### 開発環境での使用

#### 1. .envファイルに設定を追加

```bash
# .envファイルを編集
PGADMIN_EMAIL=admin@example.com
PGADMIN_PASSWORD=your_strong_password_here

# ローカルホストのみ（デフォルト、セキュア）
# PGADMIN_BIND_ADDRESS=127.0.0.1  # 設定しない場合はこれがデフォルト

# または、同一LAN内からアクセス可能にする場合
# PGADMIN_BIND_ADDRESS=0.0.0.0
```

#### 2. pgAdminを起動

```bash
# pgAdminを含めて起動
docker compose --profile pgadmin up -d pgadmin

# または、すべてのサービスと一緒に起動
docker compose --profile pgadmin up -d
```

#### 3. ブラウザでアクセス

- **URL**: `http://localhost:5050`（ローカルホストのみの場合）
- **または**: `http://<サーバーのIPアドレス>:5050`（同一LAN内アクセスの場合）
- **メール**: `.env`で設定した`PGADMIN_EMAIL`
- **パスワード**: `.env`で設定した`PGADMIN_PASSWORD`

#### 4. PostgreSQLサーバーを登録

pgAdminにログイン後、サーバーを追加：

1. 左側の「Servers」を右クリック → 「Register」→「Server...」
2. 「General」タブ:
   - **Name**: `Kotonoha PostgreSQL`（任意）
3. 「Connection」タブ:
   - **Host name/address**: `postgres`（コンテナ名）
   - **Port**: `5432`
   - **Maintenance database**: `kotonoha`
   - **Username**: `kotonoha`（`.env`の`POSTGRES_USER`）
   - **Password**: `password`（`.env`の`POSTGRES_PASSWORD`）
   - **Save password**: チェックを入れる（推奨）
4. 「Save」をクリック

### 本番環境での使用

#### 通常の起動（pgAdminは起動しない）

```bash
# 通常通り起動（pgAdminは起動しない）
docker compose up -d
```

#### 注意事項

- `.env`に`PGADMIN_EMAIL`や`PGADMIN_PASSWORD`を追加しない
- プロファイルを指定しない限り、pgAdminは起動しない

---

## よくある操作

### pgAdminのみ起動

```bash
docker compose --profile pgadmin up -d pgadmin
```

### pgAdminを停止

```bash
docker compose --profile pgadmin stop pgadmin
```

### pgAdminを削除

```bash
docker compose --profile pgadmin down pgadmin
```

### すべてのサービスとpgAdminを起動

```bash
docker compose --profile pgadmin up -d
```

### 通常の起動（pgAdminなし）

```bash
docker compose up -d
```

### すべてのサービスを停止（pgAdminを含む）

⚠️ **重要**: `docker compose down`だけでは、プロファイルで制御されているpgAdminコンテナは停止されません。

**pgAdminを含めてすべて停止する場合**:

```bash
docker compose --profile pgadmin down
```

**pgAdminを除いて停止する場合**:

```bash
docker compose down
```

**孤立したコンテナも含めて停止する場合**:

```bash
docker compose --profile pgadmin down --remove-orphans
```

### サーバーのIPアドレスを確認

```bash
# Linux/WSL2の場合
ip addr show | grep "inet " | grep -v 127.0.0.1
# または
hostname -I

# Windowsの場合
ipconfig
```

---

## データベース初期化について

PostgreSQLデータベースを完全に初期化（リセット）する手順については、別のドキュメントを参照してください：

- [PostgreSQLデータベース初期化ガイド](./postgresql-database-initialization-guide.md)

---

## トラブルシューティング

### エラー: "pgAdmin email is required"

**原因**: `.env`に`PGADMIN_EMAIL`が設定されていない

**解決方法**:
```bash
# .envファイルに追加
PGADMIN_EMAIL=admin@example.com
PGADMIN_PASSWORD=your_strong_password_here
```

### pgAdminに接続できない

**確認事項**:

1. pgAdminコンテナが起動しているか
   ```bash
   docker compose --profile pgadmin ps pgadmin
   ```

2. ポート5050が使用可能か
   ```bash
   netstat -an | grep 5050
   # または
   ss -tlnp | grep 5050
   ```

3. ブラウザで`http://localhost:5050`にアクセスできるか

4. コンテナのログを確認
   ```bash
   docker compose --profile pgadmin logs pgadmin
   ```

### PostgreSQLサーバーに接続できない

**確認事項**:

1. PostgreSQLコンテナが起動しているか
   ```bash
   docker compose ps postgres
   ```

2. ホスト名が`postgres`（コンテナ名）になっているか

3. ポートが`5432`になっているか

4. ユーザー名とパスワードが`.env`の設定と一致しているか

5. PostgreSQLコンテナのログを確認
   ```bash
   docker compose logs postgres
   ```

### 同一LAN内からアクセスできない

**確認事項**:

1. `.env`に`PGADMIN_BIND_ADDRESS=0.0.0.0`が設定されているか

2. ファイアウォールでポート5050が開いているか
   ```bash
   # Linuxの場合（ufwを使用している場合）
   sudo ufw allow 5050/tcp
   ```

3. サーバーのIPアドレスが正しいか

4. コンテナを再起動して設定を反映
   ```bash
   docker compose --profile pgadmin restart pgadmin
   ```

### ボリュームの確認

pgAdminの設定が保存されているボリュームを確認：

```bash
# ボリューム一覧の確認
docker volume ls

# ボリュームの詳細確認
docker volume inspect kotonoha-bot_pgadmin_data
```

### ボリュームの削除（設定をリセットしたい場合）

⚠️ **注意**: これを行うとpgAdminの設定がすべて削除されます

```bash
# pgAdminコンテナを停止・削除
docker compose --profile pgadmin down pgadmin

# ボリュームを削除
docker volume rm kotonoha-bot_pgadmin_data

# 再起動（新しい設定で開始）
docker compose --profile pgadmin up -d pgadmin
```

---

## セキュリティチェックリスト

### 開発環境

- [ ] `.env`に`PGADMIN_EMAIL`と`PGADMIN_PASSWORD`を設定
- [ ] 強力なパスワードを設定（20文字以上、英数字+記号）
- [ ] プロファイルを指定して起動
- [ ] 同一LAN内アクセスが必要な場合のみ`PGADMIN_BIND_ADDRESS=0.0.0.0`を設定

### 本番環境

- [ ] `.env`にpgAdmin設定を追加していない
- [ ] 通常の起動コマンド（`docker compose up -d`）のみ使用
- [ ] プロファイルを指定していない

---

## 環境ごとの`.env`ファイルの使い分け

### 開発環境

- **場所**: プロジェクトディレクトリの`.env`
- **pgAdmin設定**: 追加する（使用する場合）

### 本番環境

- **場所**: 本番サーバーの`.env`、またはContainer Managerの環境変数
- **pgAdmin設定**: 追加しない

### 重要なポイント

1. **`.env`ファイルはGitに含まれない**: `.gitignore`に`.env`が追加されているため、リポジトリには含まれません
2. **`.env.example`はテンプレート**: 実際の値は含まれません
3. **開発環境と本番環境で異なる`.env`ファイルを使用**: それぞれの環境に適した設定を管理

---

## まとめ

### 推奨方法の特徴

| 項目 | 説明 |
|------|------|
| **起動方法** | プロファイルを指定して起動 |
| **セキュリティ** | 本番環境では起動しない |
| **設定** | `.env`で認証情報を管理 |
| **アクセス** | デフォルト: ローカルホストのみ（`127.0.0.1:5050`） |
| **同一LAN内アクセス** | 環境変数で切り替え可能（`PGADMIN_BIND_ADDRESS=0.0.0.0`） |

### メリット

1. **セキュリティ**: 本番環境での誤起動を防止
2. **シンプル**: プロファイル指定で制御
3. **明確**: 起動方法で意図が明確
4. **柔軟**: 必要な時だけ起動可能

### 実装のポイント

1. **プロファイル機能を使用**: `profiles: - pgadmin`
2. **環境変数で認証情報を必須化**: デフォルト値なし
3. **ポートバインディングを環境変数で制御**: 柔軟なアクセス制御
4. **`.env.example`にコメントアウト形式で追加**: 設定項目の可視化

---

**最終更新日**: 2026年1月20日  
**バージョン**: 1.1  
**作成者**: kotonoha-bot 開発チーム
