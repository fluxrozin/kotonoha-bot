# FAQ - よくある質問

Kotonoha Discord Bot プロジェクトに関するよくある質問をまとめました。

> **注意**: 本プロジェクトは現在 **Claude API（LiteLLM 経由）** を使用しています。Gemini API に関する FAQ は、聞き耳型機能（Phase 5）での将来実装の参考情報として残しています。詳細は [ADR-0002](../architecture/adr/0002-litellm-multi-provider-strategy.md) を参照してください。

## 目次

1. [セットアップ・環境構築](#セットアップ環境構築)
2. [開発環境](#開発環境)
3. [Bot の動作](#bot-の動作)
4. [AI 機能](#ai-機能)
5. [セッション管理](#セッション管理)
6. [デプロイメント](#デプロイメント)
7. [トラブルシューティング](#トラブルシューティング)
8. [コントリビューション](#コントリビューション)

---

## セットアップ・環境構築

### Q1: Discord Bot トークンの取得方法は?

**A**: Discord Developer Portal で Bot を作成する必要があります。

1. [Discord Developer Portal](https://discord.com/developers/applications) にアクセス
2. 「New Application」をクリック
3. アプリケーション名を入力（例: Kotonoha Bot）
4. 左側メニューから「Bot」を選択
5. **トークンの取得**:
   - 「TOKEN」セクションの「Reset Token」ボタンをクリック
   - 確認ダイアログで「Yes, do it!」をクリック
   - 新しいトークンが表示されるので、「Copy」ボタンをクリックしてコピー
   - **重要**: トークンは一度しか表示されないため、必ずコピーして保存してください
   - **注意**: 既存のトークンがある場合は無効になります（新規作成の場合は問題ありません）
6. `.env` ファイルに `DISCORD_TOKEN=コピーしたトークン` を追加

**重要**: トークンは絶対に公開しないでください。Git にコミットしないよう注意してください。

---

### Q2: Bot の権限設定はどうすればいい？

**A**: Discord Developer Portal で Bot の権限を設定する必要があります。

#### 1. Privileged Gateway Intents の設定

1. [Discord Developer Portal](https://discord.com/developers/applications) にアクセス
2. アプリケーションを選択
3. 左側メニューから「Bot」を選択
4. 「Privileged Gateway Intents」セクションで以下を有効化:
   - **Message Content Intent**: ✅ **必須** - メッセージ内容を読み取るために必要
   - Presence Intent: ❌ 不要（オフのまま）
   - Server Members Intent: ❌ 不要（オフのまま）

**重要**: Message Content Intent を有効化しないと、Bot はメッセージの内容を読み取れません。

#### 2. Bot Permissions の設定と招待リンクの生成

**設定場所**: 「OAuth2」→「URL Generator」で設定します（「Bot」タブではありません）

1. Discord Developer Portal で左側メニューから「OAuth2」→「URL Generator」を選択
2. 「SCOPES」で以下を選択:
   - ✅ `bot`
   - ✅ `applications.commands`（スラッシュコマンドを使用する場合）
3. 「BOT PERMISSIONS」で以下の権限を選択:

   **必須の権限（Text Permissions）**:

   - ✅ **Send Messages** - メッセージを送信
   - ✅ **Read Message History** - メッセージ履歴を読み取る
   - ✅ **Create Public Threads** - スレッド型でスレッドを作成（Phase 5 以降）
   - ✅ **Send Messages in Threads** - スレッド内でメッセージを送信（Phase 5 以降）
   - ✅ **Use Slash Commands** - スラッシュコマンドを使用（将来用）

   **推奨の権限**:

   - ✅ **Embed Links** - リンクを埋め込み形式で表示
   - ✅ **Attach Files** - ファイルを添付
   - ✅ **Add Reactions** - リアクションを追加

   **不要な権限**（選択しない）:

   - ❌ Administrator - 管理者権限は不要
   - ❌ Manage Server - サーバー管理権限は不要
   - ❌ Manage Roles - ロール管理権限は不要

4. 権限を選択すると、下部の「Generated URL」に招待リンクが自動生成されます
5. 生成された URL をコピーして、ブラウザで開いてサーバーに招待

**Permissions Integer**: 権限を選択すると、自動的に数値が計算されます（例: `274877906944`）。この数値は URL に含まれます。

---

### Q2: Gemini API キーの取得方法は?

**A**: Google AI Studio で API キーを取得できます。

1. [Google AI Studio](https://aistudio.google.com/app/apikey) にアクセス
2. Google アカウントでログイン
3. 「Get API Key」をクリック
4. API キーをコピー
5. `.env` ファイルに `GEMINI_API_KEY=貼り付けたAPIキー` を追加

**無料枠**（2026 年 1 月現在）:

- `gemini-2.5-flash`: 5 回/分、20 回/日、250,000 トークン/分
- `gemini-2.5-flash-lite`: 10 回/分、20 回/日、250,000 トークン/分
- `gemini-3-flash`: 5 回/分、20 回/日、250,000 トークン/分

**重要**: 無料枠は 1 日 20 リクエストまでに制限されています。継続的な開発やテストには有料プランへの移行を検討してください。

---

### Q3: Python 3.14 が必要な理由は?

**A**: Kotonoha プロジェクトは Python 3.14 を使用します。

- **必須バージョン**: Python 3.14

Python 3.14 を使用する理由:

- 最新のパフォーマンス改善
- セキュリティアップデート
- 最新の型ヒント機能

**インストール方法**:

```bash
# pyenv を使用（推奨）
pyenv install 3.14
pyenv local 3.14

# または公式サイトからダウンロード
# https://www.python.org/downloads/
```

---

### Q4: uv パッケージマネージャーとは?

**A**: `uv` は高速な Python パッケージマネージャーです。

**特徴**:

- pip よりも 10-100 倍高速
- Rust で実装
- pip 互換

**インストール**:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**使用方法**:

```bash
# プロジェクトの依存関係を同期（推奨）
# pyproject.tomlとuv.lockから依存関係をインストール
uv sync

# 新しいパッケージを追加
# pyproject.tomlとuv.lockを自動更新
uv add discord.py

# パッケージを削除
uv remove discord.py

# 従来のpip互換コマンド（非推奨）
uv pip install -r requirements.txt
uv pip install discord.py
```

**主なコマンドの違い**:

- `uv sync`: pyproject.toml + uv.lock からプロジェクトの依存関係を完全に同期（開発開始時、依存関係更新時に使用）
- `uv add`: 新しいパッケージを追加し、pyproject.toml と uv.lock を自動更新
- `uv pip install`: pip 互換コマンド（requirements.txt を使う場合のみ）

**pip でも問題ありません**: uv がなくても pip で開発できます。

---

## 開発環境

### Q5: WSL2 Ubuntu は必須ですか?

**A**: いいえ、WSL2 は推奨環境ですが必須ではありません。

**サポートされている環境**:

- WSL2 Ubuntu（推奨）
- macOS
- Linux（Ubuntu, Debian, Fedora など）
- Windows（ネイティブでも動作しますが、WSL2 推奨）

**WSL2 のメリット**:

- Linux コマンドが使える
- Docker との統合が良好
- 本番環境（Linux）に近い環境で開発できる

---

### Q6: Docker は必須ですか?

**A**: 開発時は必須ではありませんが、デプロイ時に必要です。

**開発時**:

```bash
# Dockerなしで実行可能
uv pip install -r requirements.txt
python -m kotonoha_bot.main
```

**本番環境**:

- Docker コンテナとして実行
- Synology NAS 上で Docker Compose を使用
- Watchtower による自動更新

---

### Q7: VSCode 以外のエディタでも開発できますか?

**A**: はい、どのエディタでも開発できます。

**推奨エディタ**:

- **VSCode**（推奨）: Python 拡張機能が充実
- **PyCharm**: Python 専用 IDE
- **Vim/Neovim**: コマンドライン派
- **その他**: お好みのエディタ

**VSCode 推奨理由**:

- Python 拡張が優秀
- デバッグ機能が充実
- Git 統合
- 無料

---

## Bot の動作

### Q8: Bot にメンションしても反応しない

**A**: いくつかの原因が考えられます。

**確認ポイント**:

1. **Bot がオンラインか確認**

   ```bash
   docker ps  # Bot コンテナが実行中か確認
   ```

2. **Bot の権限を確認**

   - Discord サーバーで Bot に「メッセージを読む」権限があるか
   - チャンネルの権限設定を確認

3. **正しくメンションしているか**

   - `@BotName メッセージ` の形式
   - スペースが必要

4. **ログを確認**

   ```bash
   docker logs kotonoha-bot
   ```

詳細は [troubleshooting.md](../operations/troubleshooting.md#問題-bot-がメンションに応答しない) を参照してください。

---

### Q9: Bot が作成したスレッドが自動アーカイブされる

**A**: これは Discord の仕様です。

**Discord のスレッド自動アーカイブ**:

- 24 時間: デフォルト
- 1 週間: サーバーブーストレベル 1 以上

**対策**:

1. **スレッドに定期的に投稿する**（推奨）
2. **サーバーをブーストして期間を延長**
3. **アーカイブ前にセッションを保存**（実装済み）

**Kotonoha Bot の対応**:

- スレッドアーカイブ時にセッションを SQLite に自動保存
- アーカイブ解除時にセッションを復元

---

### Q10: 聞き耳型が反応しすぎる/反応しない

**A**: 判定プロンプトの調整が必要です。

**反応しすぎる場合**:

```python
# config.py で確率を下げる
EAVESDROP_TRIGGER_PROBABILITY = 0.3  # 30%
```

**反応しない場合**:

```python
# 確率を上げる
EAVESDROP_TRIGGER_PROBABILITY = 0.7  # 70%
```

**LLM 判断（アプローチ 1）の調整**:

- `prompts/eavesdrop_judge.txt` を編集
- より厳しい/緩い基準に変更

**ルールベース（アプローチ 2）の調整**:

- キーワードリストを編集
- 盛り上がり検知の閾値を変更

---

## AI 機能

### Q11: Gemini API のレート制限に達した

**A**: 無料枠の制限に達しています。

**無料枠の制限**（2026 年 1 月現在）:

- **Gemini 2.5 Flash**: 5 回/分、20 回/日、250,000 トークン/分
- **Gemini 2.5 Flash Lite**: 10 回/分、20 回/日、250,000 トークン/分
- **Gemini 3 Flash**: 5 回/分、20 回/日、250,000 トークン/分

**重要**: 無料枠は 1 日 20 リクエストまでに制限されています。継続的な開発には有料プランへの移行を検討してください。

**対策**:

1. **リクエストを減らす**

   - 聞き耳型の判定頻度を下げる
   - 不要な API 呼び出しを削減

2. **有料プランにアップグレード**

   - Google Cloud の課金を有効化

3. **複数の API を使用**
   - フォールバック機能を実装（Phase 1 で実装済み）

**現在の実装**:

- レート制限監視機能
- 自動リトライ（指数バックオフ）

---

### Q12: Flash と Pro の使い分けは?

**A**: タスクの複雑度によって自動選択されます。

**Gemini 2.5 Flash / Gemini 2.5 Flash Lite（速い・無料枠）**:

- メンション応答型の通常の会話
- 聞き耳型の判定（Yes/No）
- シンプルな質問への回答
- **注意**: 無料枠は 1 日 20 リクエストまで

**有料モデル（Gemini 2.5 Pro など）**:

- 複雑な質問への回答
- 長い文脈の理解
- 高度な推論が必要な場合
- より高いレート制限

**自動選択ロジック**:

```python
def select_model(message: str, context_length: int) -> str:
    if context_length > 1000 or is_complex_query(message):
        return "gemini-2.5-pro"  # 有料プランが必要
    return "gemini-2.5-flash"  # または gemini-2.5-flash-lite
```

詳細は [ADR-0002](../architecture/adr/0002-litellm-multi-provider-strategy.md) を参照してください。

---

### Q13: AI の応答が遅い

**A**: いくつかの原因が考えられます。

**確認ポイント**:

1. **Gemini Pro を使用していないか**

   - Pro は Flash より遅い（5-10 秒）
   - Flash は通常 1-3 秒

2. **ネットワーク遅延**

   - インターネット接続を確認
   - Synology NAS のネットワーク設定

3. **セッション数が多すぎる**

   - 100 セッション以上でパフォーマンス低下
   - ログでアクティブセッション数を確認

4. **データベースが大きすぎる**
   - SQLite ファイルサイズを確認
   - 古いセッションを削除

---

## セッション管理

### Q14: セッションとは何ですか?

**A**: セッションは会話の文脈を管理する単位です。

**セッションの種類**:

- **メンション型**: `mention:{user_id}`
- **スレッド型**: `thread:{thread_id}`
- **聞き耳型**: `eavesdrop:{channel_id}`

**セッションに含まれるもの**:

- 会話履歴（メッセージのリスト）
- システムプロンプト
- セッションタイプ
- 最終アクティブ時刻

**セッションの保存先**:

- **メモリ**: 高速アクセス（最大 100 セッション）
- **SQLite**: 永続化（全セッション）

詳細は [ADR-0004](../architecture/adr/0004-hybrid-session-management.md) を参照してください。

---

### Q15: セッションはいつ削除されますか?

**A**: 自動削除とマニュアル削除があります。

**自動削除**:

- **24 時間非アクティブ**: メモリから削除、SQLite に保存
- **SQLite セッション**: 無期限保持（手動削除のみ）

**マニュアル削除**:

```bash
# コマンドで削除（将来実装予定）
/chat reset
```

**削除のタイミング**:

1. 5 分ごとのバックグラウンドタスクで確認
2. 非アクティブセッションを検知
3. SQLite に同期してメモリから削除

---

### Q16: Bot 再起動後にセッションは復元されますか?

**A**: はい、SQLite から自動復元されます。

**復元プロセス**:

1. Bot 起動時に SQLite を読み込み
2. アクティブなセッションをメモリに復元
3. 会話履歴も完全に復元

**復元されるセッション**:

- 24 時間以内にアクティブなセッション
- それ以外は SQLite にのみ保存

**手動復元**:

```bash
# ユーザーがメンションすると自動復元
@BotName こんにちは
```

---

## デプロイメント

### Q17: Synology NAS でのデプロイ方法は?

**A**: Docker と Watchtower を使用します。

**デプロイ手順**:

1. **GitHub Actions で Docker イメージをビルド**

   ```bash
   git push origin main
   # 自動的にGHCRにプッシュされる
   ```

2. **Synology NAS で Docker Compose を起動**

   ```bash
   cd /volume1/docker/kotonoha-bot
   docker-compose up -d
   ```

3. **Watchtower が自動更新**
   - 新しいイメージを検知
   - 自動的にコンテナを再起動

詳細は [deployment-operations.md](../operations/deployment-operations.md) を参照してください。

---

### Q18: CI/CD パイプラインの仕組みは?

**A**: GitHub Actions → GHCR → Watchtower → Synology NAS の流れです。

**フロー**:

```txt
コード push
  ↓
GitHub Actions
  ├─ テスト実行（将来）
  ├─ Docker イメージビルド
  └─ GHCR にプッシュ
  ↓
Watchtower（Synology NAS上）
  ├─ 新しいイメージを検知
  ├─ コンテナを停止
  ├─ 新しいイメージでコンテナ起動
  └─ 古いイメージを削除
```

**設定ファイル**:

- `.github/workflows/docker.yml`: GitHub Actions
- `docker-compose.yml`: Docker Compose 設定

---

### Q19: ログはどこに保存されますか?

**A**: Docker ログと SQLite データベースに保存されます。

**Docker ログの確認**:

```bash
# 最新のログを表示
docker logs kotonoha-bot

# リアルタイムでログを表示
docker logs -f kotonoha-bot

# 最新100行を表示
docker logs --tail 100 kotonoha-bot
```

**ログファイルの場所**:

```txt
/volume1/docker/kotonoha-bot/
├── logs/
│   ├── kotonoha-bot.log
│   └── error.log
└── data/
    └── sessions.db  # SQLite データベース
```

---

## トラブルシューティング

### Q20: `discord.errors.LoginFailure: Improper token has been passed.`

**A**: Discord トークンが無効です。

**解決方法**:

1. **トークンを再確認**

   ```bash
   cat .env | grep DISCORD_TOKEN
   ```

2. **トークンを再生成**

   - [Discord Developer Portal](https://discord.com/developers/applications) にアクセス
   - Bot の「Reset Token」をクリック
   - 新しいトークンをコピー
   - `.env` ファイルを更新

3. **環境変数が読み込まれているか確認**

   ```bash
   docker exec kotonoha-bot env | grep DISCORD_TOKEN
   ```

---

### Q21: `google.api_core.exceptions.ResourceExhausted: 429 Quota exceeded`

**A**: Gemini API のレート制限に達しています。

**即時対応**:

```bash
# Bot を一時停止
docker stop kotonoha-bot

# 1分待ってから再起動
sleep 60
docker start kotonoha-bot
```

**恒久対策**:

- リクエスト頻度を下げる
- 有料プランにアップグレード
- 複数 API のフォールバックを実装（Phase 1 で実装済み）

---

### Q22: データベースファイルが壊れた

**A**: バックアップから復元してください。

**復元手順**:

```bash
# Bot を停止
docker stop kotonoha-bot

# バックアップから復元
cp /volume1/docker/kotonoha-bot/backups/sessions_20240115.db \
   /volume1/docker/kotonoha-bot/data/sessions.db

# Bot を再起動
docker start kotonoha-bot
```

**バックアップがない場合**:

```bash
# データベースを削除（全セッション消失）
rm /volume1/docker/kotonoha-bot/data/sessions.db

# Bot が自動的に新しいデータベースを作成
docker start kotonoha-bot
```

---

## コントリビューション

### Q23: 初めての貢献で何をすべきですか?

**A**: `good first issue` ラベルから始めるのがおすすめです。

**初心者向けタスク**:

- ドキュメントの修正
- テストの追加
- バグ修正（simple なもの）

**手順**:

1. Issue 一覧を確認（注: GitHub リポジトリ URL は実際の組織名に置き換えてください）
2. `good first issue` を見つける
3. Issue にコメントして割り当てを依頼
4. ブランチを作成して実装
5. PR を作成

詳細は [contributing.md](./contributing.md) を参照してください。

---

### Q24: プルリクエストのレビューはどのくらいかかりますか?

**A**: 通常 1-3 日以内にレビューされます。

**レビュープロセス**:

1. PR 作成
2. CI/CD チェック（自動）
3. コードレビュー（1-3 日）
4. フィードバック対応
5. 承認
6. マージ

**レビューを早くもらうには**:

- 小さい PR にする（300 行以下）
- テストを含める
- ドキュメントを更新する
- わかりやすい説明を書く

---

### Q25: テストの書き方がわかりません

**A**: pytest を使用します。サンプルコードを参考にしてください。

**基本的なテスト**:

```python
import pytest
from kotonoha_bot.session import SessionManager

class TestSessionManager:
    @pytest.fixture
    def manager(self):
        """SessionManagerのフィクスチャ。"""
        return SessionManager()

    def test_create_session(self, manager):
        """セッションが作成できることを確認。"""
        session = manager.create_session(
            session_key="test:123",
            session_type="mention"
        )

        assert session is not None
        assert session.session_key == "test:123"
        assert session.session_type == "mention"
```

**テストの実行**:

```bash
# 全テストを実行
pytest

# 特定のテストを実行
pytest tests/unit/test_session.py

# カバレッジ付きで実行
pytest --cov=kotonoha_bot --cov-report=html
```

詳細は [contributing.md](./contributing.md#テストの書き方) を参照してください。

---

## さらなる質問

この FAQ で解決しない問題がある場合:

1. **ドキュメントを確認**

   - [Getting Started](../getting-started.md)
   - [Troubleshooting Guide](../operations/troubleshooting.md)
   - [Architecture Documentation](../architecture/)

2. **Issue を検索**

   - 既存の Issue を検索（注: GitHub リポジトリ URL は実際の組織名に置き換えてください）

3. **新しい Issue を作成**

   - 見つからない場合は新規作成

4. **GitHub Discussions を利用**
   - 一般的な質問、アイデア

---

**作成日**: 2026 年 1 月 14 日
**最終更新日**: 2026 年 1 月 14 日
**バージョン**: 1.0
