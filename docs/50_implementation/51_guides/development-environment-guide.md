# 開発環境ガイド

このドキュメントでは、Kotonoha Botの開発環境のセットアップと開発フローについて説明します。

## 目次

1. [概要](#概要)
2. [前提条件](#前提条件)
3. [開発環境のセットアップ](#開発環境のセットアップ)
4. [通常の開発フロー](#通常の開発フロー)
5. [マイグレーション管理](#マイグレーション管理)
6. [データベース管理](#データベース管理)
7. [テストの実行](#テストの実行)
8. [トラブルシューティング](#トラブルシューティング)

---

## 概要

### 基本方針

- **開発環境**: カスタムイメージを使用（GHCRからプル）
- **本番環境**: カスタムイメージを使用（GHCRからプル）
- **マイグレーション**: 両環境で同じマイグレーションファイルを使用
- **メリット**: 開発環境と本番環境で同じ環境を再現でき、pg_bigm拡張の動作を常に確認できる

### 開発環境の特徴

- **PostgreSQLイメージ**: `ghcr.io/${GITHUB_REPOSITORY}/kotonoha-postgres:latest`（カスタムイメージ）
- **pg_bigm拡張**: 利用可能
- **ハイブリッド検索**: インデックスあり、高速
- **環境の一貫性**: 本番環境と同じ環境を再現

---

## 前提条件

- Docker Composeが使用されていること
- カスタムPostgreSQLイメージ（`ghcr.io/${GITHUB_REPOSITORY}/kotonoha-postgres:latest`）を使用
- GHCRにカスタムイメージがプッシュされていること（初回のみ必要）
- `.env`ファイルが設定されていること

---

## 開発環境のセットアップ

### 1. 環境変数の設定

`.env`ファイルを作成し、必要な環境変数を設定します。

```bash
# .envファイルを作成
cp .env.example .env

# 必要な環境変数を設定
GITHUB_REPOSITORY=your-username/kotonoha-bot
DISCORD_TOKEN=your_discord_bot_token
ANTHROPIC_API_KEY=your_anthropic_api_key
# ... その他の環境変数
```

### 2. docker-compose.ymlの確認

`docker-compose.yml`を開き、`postgres`サービスの設定を確認します。

```yaml
services:
  postgres:
    # 開発環境と本番環境の両方でカスタムイメージを使用（GHCRからプル）
    image: ghcr.io/${GITHUB_REPOSITORY}/kotonoha-postgres:latest
```

**注意**: カスタムイメージを使用することで、開発環境でも`pg_bigm`拡張が利用可能になり、
ハイブリッド検索が最適なパフォーマンスで動作します。

### 3. カスタムイメージの取得

初回のみ、カスタムイメージをGHCRからプルします。

```bash
# コンテナを起動（自動的にイメージをプル）
docker compose up -d postgres
```

**注意**: カスタムイメージがGHCRにプッシュされている必要があります。
初回プル時は少し時間がかかりますが、その後はキャッシュされるため高速です。

---

## 通常の開発フロー

### 1. 開発を開始

```bash
# すべてのコンテナをバックグラウンドで起動（推奨）
docker compose up -d

# または、個別に起動する場合
# docker compose up -d postgres
# docker compose up -d kotonoha-bot

# ログを確認（必要に応じて）
docker compose logs -f kotonoha-bot
```

**注意**: `-d`オプションはバックグラウンドで実行するオプションです。
ログを確認したい場合は、別のターミナルで`docker compose logs -f kotonoha-bot`を実行してください。

### 2. マイグレーションについて

**通常の開発では、マイグレーションは既に適用済みです**。
通常の開発では、このステップは**スキップ**して問題ありません。

**マイグレーションが必要になるのは、以下の場合のみ**:

- 新しいテーブルを追加する
- 既存のテーブルにカラムを追加・削除する
- インデックスを追加・削除する
- 拡張機能を有効化する（例: 新しいPostgreSQL拡張）
- ENUM型を追加・変更する

**マイグレーションが不要な場合（通常の開発）**:

- ✅ 既存のコードを修正する
- ✅ 新しい機能を追加する（スキーマ変更なし）
- ✅ バグを修正する
- ✅ テストを追加する
- ✅ 既存の機能を拡張する（スキーマ変更なし）

### 3. マイグレーションを適用

```bash
# Bot起動時に自動適用される
# または手動で実行:
uv run alembic upgrade head
```

### 4. 動作確認

- ハイブリッド検索は動作する（インデックスあり、高速）
- pg_bigm拡張が正常に有効化されている

### 5. テストを実行

```bash
# ユニットテスト
uv run pytest tests/unit/ -v

# 統合テスト
uv run pytest tests/integration/ -v

# 特定のテストファイルを実行
uv run pytest tests/unit/db/test_postgres_hybrid_search.py -v
```

---

## マイグレーション管理

### マイグレーションを作成する手順

将来的にスキーマを変更する場合の手順です。

1. **マイグレーションファイルを作成**

   ```bash
   # 日時ベースのrevision IDを使用（推奨）
   DATE_ID=$(date +%Y%m%d%H%M)
   uv run alembic revision -m "マイグレーション名" --rev-id "$DATE_ID"
   ```

2. **マイグレーションファイルを編集**

   ```python
   # alembic/versions/{DATE_ID}_マイグレーション名.py
   revision: str = "{DATE_ID}"
   down_revision: str | Sequence[str] | None = "前のマイグレーションのrevision ID"
   ```

3. **開発環境でテスト**

   ```bash
   # マイグレーションを適用
   uv run alembic upgrade head
   
   # マイグレーションをロールバック（テスト用）
   uv run alembic downgrade -1
   
   # 再度適用
   uv run alembic upgrade head
   ```

4. **テストを実行**

   ```bash
   uv run pytest tests/ -v
   ```

5. **コミット・プッシュ**

   ```bash
   git add alembic/versions/
   git commit -m "feat: マイグレーション名を追加"
   git push
   ```

6. **本番環境にデプロイ**

   - CI/CDパイプラインが自動的にマイグレーションを適用
   - または、手動で`alembic upgrade head`を実行

### 日時ベースのRevision IDについて

**推奨**: マイグレーションのrevision IDは日時ベースの12桁数値（`YYYYMMDDHHMM`形式）を使用します。

**メリット**:

- **可読性の向上**: 日時が分かるため、いつ作成されたマイグレーションかが一目で分かる
- **時系列順の管理**: 作成順に並ぶため、マイグレーション履歴が分かりやすい
- **一意性の保証**: 同じ時刻に2つのマイグレーションを作成することは稀

**例**:

```bash
# 2026年1月20日 19:40に作成されたマイグレーション
DATE_ID=$(date +%Y%m%d%H%M)  # 202601201940
uv run alembic revision -m "add_new_table" --rev-id "$DATE_ID"
```

詳細は、[PostgreSQL実装ガイド](./postgresql-implementation-guide.md#13-alembicマイグレーション管理)を参照してください。

---

## データベース管理

### データベース初期化が必要な場合

Revision IDを変更した場合や、データベースを完全にリセットしたい場合のフローです。

**開発環境でのフロー**:

1. **コンテナを停止・削除**

   ```bash
   docker compose stop postgres
   docker compose rm -f postgres
   ```

2. **データベースボリュームを削除**

   ```bash
   docker volume rm kotonoha-bot_postgres_data
   ```

3. **コンテナを再起動**

   ```bash
   docker compose up -d postgres
   ```

4. **マイグレーションを適用**

   ```bash
   uv run alembic upgrade head
   ```

### データベースの状態確認

```bash
# PostgreSQLに接続
docker compose exec postgres psql -U kotonoha kotonoha

# 拡張機能の確認
\dx

# pg_bigm拡張の確認
\dx pg_bigm

# テーブル一覧の確認
\dt

# マイグレーション履歴の確認
SELECT * FROM alembic_version;
```

---

## テストの実行

### ユニットテスト

```bash
# すべてのユニットテストを実行
uv run pytest tests/unit/ -v

# 特定のテストファイルを実行
uv run pytest tests/unit/db/test_postgres_hybrid_search.py -v

# 特定のテスト関数を実行
uv run pytest tests/unit/db/test_postgres_hybrid_search.py::test_hybrid_search_basic -v
```

### 統合テスト

```bash
# すべての統合テストを実行
uv run pytest tests/integration/ -v

# 特定のテストファイルを実行
uv run pytest tests/integration/test_hybrid_search.py -v
```

### カバレッジ付きテスト

```bash
# カバレッジ付きでテスト実行
uv run pytest --cov=src/kotonoha_bot --cov-report=html

# カバレッジレポートを確認
# htmlcov/index.html を開く
```

---

## トラブルシューティング

### カスタムイメージがプルできない

**問題**: `docker compose up -d postgres`でエラーが発生する

**解決方法**:

1. GHCRにカスタムイメージがプッシュされているか確認
2. `.env`ファイルの`GITHUB_REPOSITORY`が正しく設定されているか確認
3. GitHubにログインしているか確認（必要に応じて）

```bash
# GitHubにログイン
echo $GITHUB_TOKEN | docker login ghcr.io -u $GITHUB_USERNAME --password-stdin
```

### pg_bigm拡張が有効化されない

**問題**: マイグレーション時に警告が表示される

**解決方法**:

1. カスタムイメージが正しくプルされているか確認

   ```bash
   docker compose images postgres
   ```

2. コンテナのログを確認

   ```bash
   docker compose logs postgres
   ```

3. 拡張機能の状態を確認

   ```bash
   docker compose exec postgres psql -U kotonoha kotonoha -c "\dx pg_bigm"
   ```

### マイグレーションが適用されない

**問題**: `alembic upgrade head`でエラーが発生する

**解決方法**:

1. マイグレーションファイルの`down_revision`が正しく設定されているか確認
2. データベースの状態を確認

   ```bash
   docker compose exec postgres psql -U kotonoha kotonoha -c "SELECT * FROM alembic_version;"
   ```

3. マイグレーションファイルの構文エラーを確認

   ```bash
   uv run alembic check
   ```

### データベース接続エラー

**問題**: データベースに接続できない

**解決方法**:

1. コンテナが起動しているか確認

   ```bash
   docker compose ps
   ```

2. コンテナのログを確認

   ```bash
   docker compose logs postgres
   ```

3. 環境変数が正しく設定されているか確認

   ```bash
   cat .env
   ```

### テストが失敗する

**問題**: テストが失敗する

**解決方法**:

1. データベースが起動しているか確認

   ```bash
   docker compose ps postgres
   ```

2. テスト用のデータベースが正しく設定されているか確認
3. テストデータが正しく設定されているか確認

---

## 関連ドキュメント

- [PostgreSQL実装ガイド](./postgresql-implementation-guide.md): PostgreSQLの実装詳細
- [PostgreSQLクエリガイド](./postgresql-query-guide.md): クエリの書き方
- [Phase 11実装計画](../00_planning/phases/phase11.md): Phase 11の詳細実装計画

---

**最終更新日**: 2026年1月20日  
**バージョン**: 1.0  
**作成者**: kotonoha-bot 開発チーム
