# Troubleshooting Guide - Kotonoha Discord Bot

Kotonoha Discord ボットの問題解決ガイド

## 目次

1. [起動・接続の問題](#1-起動接続の問題)
2. [AI 応答の問題](#2-ai-応答の問題)
3. [データベースの問題](#3-データベースの問題)
4. [パフォーマンスの問題](#4-パフォーマンスの問題)
5. [デプロイメントの問題](#5-デプロイメントの問題)

---

## 1. 起動・接続の問題

### 問題: Bot が Discord に接続できない

**症状**:

```txt
ERROR: discord.errors.LoginFailure: Improper token has been passed.
```

**原因**:

- Discord Bot Token が正しく設定されていない
- Token が無効または期限切れ

**解決方法**:

1. **環境変数の確認**

   ```bash
   cat .env | grep DISCORD_TOKEN
   ```

2. **Token の再取得**

   - [Discord Developer Portal](https://discord.com/developers/applications) にアクセス
   - アプリケーションを選択
   - "Bot" タブで Token を Reset して再取得
   - `.env` ファイルを更新

3. **Bot の再起動**

   ```bash
   docker-compose restart kotonoha
   ```

---

### 問題: Bot がサーバーに参加できない

**症状**:

- Bot をサーバーに招待しても参加しない
- 招待リンクが無効

**原因**:

- 招待リンクの権限設定が不正
- Bot の Privileged Gateway Intents が有効化されていない

**解決方法**:

1. **Privileged Gateway Intents の有効化**

   - [Discord Developer Portal](https://discord.com/developers/applications) にアクセス
   - "Bot" タブを開く
   - 以下の Intents を有効化:
     - PRESENCE INTENT
     - SERVER MEMBERS INTENT
     - MESSAGE CONTENT INTENT

2. **招待リンクの再生成**

   ```txt
   https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=8&scope=bot%20applications.commands
   ```

   - `YOUR_CLIENT_ID` を実際の Client ID に置き換える
   - `permissions=8` は管理者権限（必要に応じて変更）

---

### 問題: Bot は起動しているがメッセージに反応しない

**症状**:

- Bot のステータスはオンライン
- メンションしても応答がない

**原因**:

- `on_message` イベントが正しく実装されていない
- Bot 自身のメッセージに反応してしまっている
- メッセージ権限が不足している

**解決方法**:

1. **ログの確認**

   ```bash
   docker logs kotonoha-bot --tail 50
   ```

2. **Bot の権限確認**

   - サーバー設定 → 役割 → Bot の役割を確認
   - 以下の権限が必要:
     - メッセージを読む
     - メッセージを送信
     - スレッドを作成
     - メッセージ履歴を読む

3. **コードの確認**

   ```python
   # bot.pyで以下を確認
   if message.author == self.user:
       return  # Bot自身のメッセージは無視
   ```

---

## 2. AI 応答の問題

### 問題: Gemini API エラーが発生する

**症状**:

```txt
ERROR: google.api_core.exceptions.PermissionDenied: 403 API key not valid
```

**原因**:

- Gemini API Key が正しく設定されていない
- API Key が無効または期限切れ

**解決方法**:

1. **API Key の確認**

   ```bash
   cat .env | grep GEMINI_API_KEY
   ```

2. **API Key の再取得**

   - [Google AI Studio](https://makersuite.google.com/app/apikey) にアクセス
   - 新しい API Key を作成
   - `.env` ファイルを更新

3. **Bot の再起動**

   ```bash
   docker-compose restart kotonoha
   ```

---

### 問題: レート制限エラーが発生する

**症状**:

```txt
ERROR: google.api_core.exceptions.ResourceExhausted: 429 Resource has been exhausted
```

**原因**:

- Gemini API のレート制限（Flash: 15 回/分、1,500 回/日、Pro: 2 回/分、50 回/日）に達した

**解決方法**:

1. **レート制限の確認**

   ```bash
   docker logs kotonoha-bot | grep "rate limit"
   ```

2. **一時的な対処**

   - しばらく待ってからリトライ（Bot は自動的にリトライします）
   - 聞き耳型を無効化して負荷を軽減

3. **恒久的な対処**
   - レート制限対応の実装を確認（トークンバケットアルゴリズム）
   - 優先度管理の実装（ユーザー応答 > 聞き耳型判定）

---

### 問題: AI の応答が不適切または期待と異なる

**症状**:

- AI の応答が文脈に合わない
- 不適切な内容を返す
- トンチンカンな発言をする

**原因**:

- システムプロンプトが不適切
- 会話履歴が正しく渡されていない
- 聞き耳型で会話の文脈を誤解している

**解決方法**:

1. **システムプロンプトの確認**

   - `src/kotonoha_bot/ai/gemini.py` のシステムプロンプトを確認
   - 場面緘黙支援に適した表現になっているか確認

2. **会話履歴の確認**

   ```bash
   # ログで会話履歴を確認
   docker logs kotonoha-bot | grep "会話履歴"
   ```

3. **聞き耳型の判定プロンプトを最適化**
   - `src/kotonoha_bot/eavesdrop/llm_judge.py` の判定プロンプトを調整
   - より厳格な判定基準を設定

---

## 3. データベースの問題

### 問題: データベースファイルが見つからない

**症状**:

```txt
ERROR: sqlite3.OperationalError: unable to open database file
```

**原因**:

- `data/` ディレクトリが存在しない
- ファイルの書き込み権限がない
- Docker ボリュームマウントの問題

**解決方法**:

1. **ディレクトリの作成**

   ```bash
   mkdir -p /volume1/docker/kotonoha/data
   chmod 755 /volume1/docker/kotonoha/data
   ```

2. **権限の確認**

   ```bash
   ls -la /volume1/docker/kotonoha/data
   # 所有者が正しいか確認（通常は1000:1000）
   ```

3. **ボリュームマウントの確認**

   ```bash
   docker inspect kotonoha-bot | grep Mounts -A 10
   ```

---

### 問題: データベースが破損している

**症状**:

```txt
ERROR: sqlite3.DatabaseError: database disk image is malformed
```

**原因**:

- データベースファイルが破損
- 不正な終了によるファイル破損

**解決方法**:

1. **データベースの整合性チェック**

   ```bash
   docker exec kotonoha-bot sqlite3 /app/data/kotonoha.db "PRAGMA integrity_check;"
   ```

2. **バックアップからリストア**

   ```bash
   # 最新のバックアップを確認
   ls -lt /volume1/docker/kotonoha/backups/

   # バックアップからリストア
   cp /volume1/docker/kotonoha/backups/kotonoha_YYYYMMDD_HHMMSS.db \
      /volume1/docker/kotonoha/data/kotonoha.db

   # コンテナ再起動
   docker-compose restart kotonoha
   ```

3. **リストアできない場合**

   ```bash
   # データベースを削除して再作成
   rm /volume1/docker/kotonoha/data/kotonoha.db
   docker-compose restart kotonoha
   # 注意: 会話履歴は失われます
   ```

---

### 問題: セッションが復元されない

**症状**:

- Bot を再起動すると会話履歴が失われる
- 以前の会話が続かない

**原因**:

- セッションの同期機能が動作していない
- SQLite への保存が失敗している

**解決方法**:

1. **ログの確認**

   ```bash
   docker logs kotonoha-bot | grep "session"
   docker logs kotonoha-bot | grep "save"
   ```

2. **データベースの確認**

   ```bash
   docker exec kotonoha-bot sqlite3 /app/data/kotonoha.db "SELECT * FROM sessions LIMIT 5;"
   ```

3. **同期機能の確認**
   - `src/kotonoha_bot/session/manager.py` の同期ロジックを確認
   - バッチ同期タスクが動作しているか確認

---

## 4. パフォーマンスの問題

### 問題: 応答が遅い（3 秒以上かかる）

**症状**:

- メッセージを送信してから応答まで 10 秒以上かかる
- Bot が応答しないように見える

**原因**:

- Gemini API の応答が遅い
- レート制限で待機している
- データベースクエリが遅い
- メモリ不足

**解決方法**:

1. **レスポンスタイムの測定**

   ```bash
   docker logs kotonoha-bot | grep "response time"
   ```

2. **リソース使用状況の確認**

   ```bash
   docker stats kotonoha-bot
   ```

3. **最適化**
   - Flash モデルを優先的に使用
   - セッション数を制限（最大 100）
   - データベースクエリを最適化

---

### 問題: メモリ使用量が多い

**症状**:

```txt
WARNING: Memory usage: 800MB (limit: 1G)
```

**原因**:

- セッション数が多すぎる
- 会話履歴が肥大化している
- メモリリークの可能性

**解決方法**:

1. **セッション数の確認**

   ```bash
   docker exec kotonoha-bot sqlite3 /app/data/kotonoha.db "SELECT COUNT(*) FROM sessions WHERE is_archived = 0;"
   ```

2. **クリーンアップの実行**

   ```bash
   # 非アクティブセッションを強制削除
   docker exec kotonoha-bot python -m kotonoha_bot.scripts.cleanup
   ```

3. **メモリ制限の調整**

   ```yaml
   # docker-compose.ymlで調整
   resources:
     limits:
       memory: 2G # 1G → 2Gに増やす
   ```

---

## 5. デプロイメントの問題

### 問題: Docker イメージのビルドが失敗する

**症状**:

```txt
ERROR: failed to solve: process "/bin/sh -c uv sync" did not complete successfully
```

**原因**:

- 依存関係の解決に失敗
- `pyproject.toml` の記述エラー
- ネットワークエラー

**解決方法**:

1. **ローカルでビルドテスト**

   ```bash
   docker build -t kotonoha-bot:test .
   ```

2. **依存関係の確認**

   ```bash
   uv sync --dry-run
   ```

3. **キャッシュのクリア**

   ```bash
   docker builder prune -a
   ```

---

### 問題: Watchtower が新しいイメージを取得しない

**症状**:

- GitHub にプッシュしてもコンテナが更新されない
- Watchtower のログにエラーがない

**原因**:

- イメージタグが変わっていない
- Watchtower の設定ミス
- GHCR の認証エラー

**解決方法**:

1. **Watchtower のログ確認**

   ```bash
   docker logs watchtower --tail 50
   ```

2. **手動でイメージを更新**

   ```bash
   docker pull ghcr.io/your-org/kotonoha-bot:latest
   docker-compose up -d kotonoha
   ```

3. **Watchtower の再起動**

   ```bash
   docker-compose restart watchtower
   ```

---

### 問題: コンテナが起動直後に停止する

**症状**:

```bash
docker ps  # kotonoha-botが表示されない
docker ps -a  # Exitedステータスで表示される
```

**原因**:

- 起動時のエラー
- 環境変数の設定ミス
- ヘルスチェックの失敗

**解決方法**:

1. **ログの確認**

   ```bash
   docker logs kotonoha-bot
   ```

2. **環境変数の確認**

   ```bash
   docker inspect kotonoha-bot | grep -A 20 Env
   ```

3. **ヘルスチェックの無効化（テスト用）**

   ```yaml
   # docker-compose.ymlで一時的に無効化
   # healthcheck:
   #   disable: true
   ```

---

## 6. よくある質問

### Q: Bot が突然応答しなくなった

**A**: 以下を順番に確認してください:

1. Bot のステータス（オンラインか）
2. ログにエラーがないか
3. API のレート制限に達していないか
4. データベース接続が正常か

詳細は各セクションを参照してください。

---

### Q: エラーメッセージが表示されない

**A**: ログレベルを DEBUG に変更してください:

```bash
# .env ファイルで設定
LOG_LEVEL=DEBUG

# コンテナ再起動
docker-compose restart kotonoha
```

---

### Q: バックアップから復元した後、データが古い

**A**: バックアップのタイムスタンプを確認してください:

```bash
ls -lt /volume1/docker/kotonoha/backups/
```

最新のバックアップを使用していることを確認してください。

---

## 7. サポート

### 7.1 ログの収集

問題を報告する際は、以下の情報を含めてください:

```bash
# ログの収集
docker logs kotonoha-bot --since 1h > kotonoha_logs.txt

# システム情報
docker info > system_info.txt
docker inspect kotonoha-bot > container_info.txt

# 環境変数（機密情報を削除）
cat .env | sed 's/=.*/=***/' > env_info.txt
```

### 7.2 連絡先

- **GitHub Issues**: GitHubリポジトリのIssuesページ（注: URLは実際の組織名に置き換えてください）
- **ドキュメント**: [docs/](../README.md)

---

**作成日**: 2026年1月14日
**最終更新日**: 2026年1月14日
**バージョン**: 1.0
**作成者**: kotonoha-bot 開発チーム
