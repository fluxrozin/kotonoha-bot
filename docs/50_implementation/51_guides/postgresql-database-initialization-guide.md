# PostgreSQLデータベース初期化ガイド

このドキュメントでは、Kotonoha BotプロジェクトでPostgreSQLデータベースを完全に初期化（リセット）する手順について説明します。

## 目次

1. [概要](#概要)
2. [現在の設定の確認](#現在の設定の確認)
3. [パスワードのリセット](#パスワードのリセット)
4. [初期化手順](#初期化手順)
5. [デフォルト値](#デフォルト値)
6. [注意事項](#注意事項)
7. [完全な初期化コマンド（一括実行）](#完全な初期化コマンド一括実行)
8. [関連ドキュメント](#関連ドキュメント)

---

## 概要

### 初期化とは

データベースを完全に初期化すると、以下の操作が行われます：

- すべてのデータが削除される
- すべてのテーブルが削除される
- 新しいデータベースが作成される
- マイグレーションが自動実行される（次回起動時）

⚠️ **警告**: この操作は**すべてのデータを削除**します。実行前に重要なデータのバックアップを取得してください。

### 使用場面

- 開発環境でデータベースをクリーンな状態に戻したい場合
- テストデータをすべて削除したい場合
- パスワードをリセットしたい場合
- データベースの設定を変更した後、新しい状態で開始したい場合

---

## 現在の設定の確認

初期化前に、現在のPostgreSQL設定を確認できます：

```bash
# .envファイルのPostgreSQL設定を確認
grep -E "^(POSTGRES_|DATABASE_URL)" .env
```

出力例：

```bash
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=kotonoha
POSTGRES_USER=kotonoha
POSTGRES_PASSWORD=admin
```

---

## パスワードのリセット

初期化と同時にパスワードをリセットする場合：

### 仕組み

PostgreSQL公式Dockerイメージは、**データディレクトリが空の場合のみ**`POSTGRES_PASSWORD`環境変数を使用してデータベースを初期化します。

1. ボリュームを削除すると、データディレクトリが空になる
2. コンテナを起動すると、その時点での環境変数の値（`.env`から読み取られる）で`initdb`が実行される
3. そのため、**ボリューム削除前に`.env`ファイルを編集**しておく必要がある

### 手順

1. **コンテナを停止**（オプション、既に停止している場合は不要）
   ```bash
   docker compose down
   ```

2. **`.env`ファイルを編集**（ボリュームを削除する前に行う）
   - `POSTGRES_PASSWORD`の値を新しいパスワードに変更
   - `DATABASE_URL`を使用している場合も更新

3. **初期化手順を実行**
   - 下記の[初期化手順](#初期化手順)を実行
   - ボリューム削除後、コンテナ起動時に新しいパスワードでデータベースが作成される

```bash
# .envファイルの例（初期化前に編集）
POSTGRES_USER=kotonoha
POSTGRES_PASSWORD=new_password_here  # 新しいパスワードを設定
POSTGRES_DB=kotonoha
```

### 接続文字列の更新

`.env`で`DATABASE_URL`を使用している場合、パスワード変更後に接続文字列も更新が必要です：

```bash
# 変更前
DATABASE_URL=postgresql://kotonoha:old_password@postgres:5432/kotonoha

# 変更後（初期化前に更新）
DATABASE_URL=postgresql://kotonoha:new_password@postgres:5432/kotonoha
```

### パスワードリセットの完全な手順

```bash
# 1. コンテナを停止
docker compose down

# 2. .envファイルを編集（ボリュームを削除する前）
# POSTGRES_PASSWORD=new_password_here を設定
# この時点で環境変数が更新される

# 3. データボリュームを削除
# これにより、データディレクトリが空になる
docker volume rm kotonoha-bot_postgres_data

# 4. PostgreSQLコンテナを起動
# データディレクトリが空のため、initdbが実行される
# その時点での環境変数（.envから読み取られた値）で初期化される
docker compose up -d postgres

# 5. データベース接続を確認
docker compose exec -T postgres psql -U kotonoha -d kotonoha -c "SELECT version();"

# 6. すべてのサービスを起動（マイグレーションが自動実行される）
docker compose up -d
```

### 注意

- 既存のボリュームがある状態で`POSTGRES_PASSWORD`を変更しても、パスワードは変更されません
- パスワードを変更するには、必ずボリュームを削除してからコンテナを起動する必要があります
- ボリューム削除前に`.env`を編集しておくことで、新しいパスワードでデータベースが作成されます

---

## 初期化手順

### ステップ1: コンテナを停止

```bash
# すべてのコンテナを停止
docker compose down
```

### ステップ2: PostgreSQLデータボリュームを削除

```bash
# PostgreSQLデータボリュームを削除（すべてのデータが削除される）
docker volume rm kotonoha-bot_postgres_data
```

### ステップ3: PostgreSQLコンテナを再起動

```bash
# PostgreSQLコンテナを起動（新しいデータベースが作成される）
docker compose up -d postgres
```

### ステップ4: データベースの起動を確認

```bash
# コンテナの状態を確認
docker compose ps postgres

# データベースに接続できるか確認
docker compose exec -T postgres psql -U kotonoha -d kotonoha -c "SELECT version();"
```

### ステップ5: マイグレーションの実行

次回、botコンテナを起動すると、Alembicマイグレーションが自動実行され、テーブルが作成されます：

```bash
# すべてのサービスを起動（マイグレーションが自動実行される）
docker compose up -d
```

---

## デフォルト値

`docker-compose.yml`で設定されているデフォルト値：

- **ユーザー名**: `kotonoha`
- **パスワード**: `password`（`.env`で上書き可能）
- **データベース名**: `kotonoha`
- **ホスト**: `postgres`（コンテナ名）
- **ポート**: `5432`

### 環境変数での上書き

`.env`ファイルで以下の環境変数を設定することで、デフォルト値を上書きできます：

```bash
POSTGRES_USER=kotonoha
POSTGRES_PASSWORD=your_password_here
POSTGRES_DB=kotonoha
```

---

## 注意事項

### 1. データのバックアップ

初期化前に重要なデータをバックアップしてください。

```bash
# バックアップの例（初期化前）
docker compose exec -T postgres pg_dump -U kotonoha kotonoha > backup_$(date +%Y%m%d_%H%M%S).sql
```

### 2. 接続文字列の更新

`.env`の`DATABASE_URL`も更新が必要な場合があります。パスワードを変更した場合は、接続文字列内のパスワードも更新してください。

### 3. pgAdminの設定

pgAdminでPostgreSQLサーバーを登録している場合、パスワード変更後に再登録が必要です。

詳細は[pgAdminセットアップガイド](./pgadmin-setup-guide.md)を参照してください。

### 4. 実行中のサービス

初期化中は、データベースを使用しているサービス（botコンテナなど）を停止してください。

### 5. ボリューム名の確認

ボリューム名が異なる場合があります。以下のコマンドで確認できます：

```bash
# ボリューム一覧を確認
docker volume ls | grep postgres
```

---

## 完全な初期化コマンド（一括実行）

すべての手順を一度に実行する場合：

```bash
# コンテナを停止
docker compose down

# データボリュームを削除
docker volume rm kotonoha-bot_postgres_data

# PostgreSQLコンテナを起動
docker compose up -d postgres

# 起動を待機（5秒）
sleep 5

# データベース接続を確認
docker compose exec -T postgres psql -U kotonoha -d kotonoha -c "SELECT version();"

# すべてのサービスを起動（マイグレーションが自動実行される）
docker compose up -d
```

### スクリプト化

頻繁に初期化を行う場合は、スクリプトを作成することもできます：

```bash
#!/bin/bash
# reset-db.sh

set -e

echo "PostgreSQLデータベースを初期化します..."
echo "⚠️  警告: すべてのデータが削除されます"
read -p "続行しますか? (y/N): " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "キャンセルしました"
    exit 1
fi

echo "コンテナを停止中..."
docker compose down

echo "データボリュームを削除中..."
docker volume rm kotonoha-bot_postgres_data || true

echo "PostgreSQLコンテナを起動中..."
docker compose up -d postgres

echo "起動を待機中..."
sleep 5

echo "データベース接続を確認中..."
docker compose exec -T postgres psql -U kotonoha -d kotonoha -c "SELECT version();" > /dev/null

echo "すべてのサービスを起動中（マイグレーションが自動実行されます）..."
docker compose up -d

echo "✅ 初期化が完了しました"
```

---

## 関連ドキュメント

- [pgAdminセットアップガイド](./pgadmin-setup-guide.md)
- [PostgreSQL実装ガイド](./postgresql-implementation-guide.md)
- [PostgreSQL実装手順](../52_procedures/postgresql-implementation.md)
- [PostgreSQLクエリガイド](./postgresql-query-guide.md)

---

**最終更新日**: 2026年1月20日  
**バージョン**: 1.0  
**作成者**: kotonoha-bot 開発チーム
