# Discord Bot KOTONOHA（コトノハ）

場面緘黙自助グループ運営支援のための Discord ボットです。
Claude API を使用して、優しく思いやりのある AI アシスタントとして機能します。

## 概要

KOTONOHA は、場面緘黙で困っている人々が安心してコミュニケーションできる環境を
提供することを目的とした Discord ボットです。メンションされた時に Claude API 経由で
応答を生成し、会話履歴を保持して継続的な対話をサポートします。

## 主な機能

- ✅ **メンション応答型**: Bot をメンションすると AI が応答
- ✅ **会話履歴の保持**: セッション管理により会話の文脈を維持
- ✅ **セッション永続化**: SQLite によるデータベース保存と復元
- ✅ **LiteLLM 統合**: 複数の LLM プロバイダーに対応（現在は Claude API）
- ✅ **スレッド型**: メンション時に自動スレッド作成、スレッド内で会話継続
- ✅ **聞き耳型**: LLM 判断による自然な会話参加
- ✅ **レート制限**: リクエストキューとトークンバケットによるレート制限管理
- ✅ **スラッシュコマンド**: `/chat reset`, `/chat status` コマンド
- ✅ **エラーハンドリング**: ユーザーフレンドリーなエラーメッセージ

## 技術スタック

- **Python**: 3.14
- **Discord**: discord.py 2.6.4+
- **LLM**: Claude API（LiteLLM 経由）
  - 開発用: Claude Haiku 4.5（最速・低コスト）
  - 本番用: Claude Opus 4.5（最高品質）
  - バランス型: Claude Sonnet 4.5
- **データベース**: SQLite（将来 aiosqlite に移行予定）
- **パッケージマネージャー**: uv
- **デプロイ**: Docker + Watchtower（自動更新）
- **CI/CD**: GitHub Actions → GHCR → Watchtower

## クイックスタート

### 前提条件

- Python 3.14
- uv（パッケージマネージャー）
- Discord Bot Token
- Anthropic API Key

### セットアップ

1. **リポジトリのクローン**

   ```bash
   git clone https://github.com/your-org/kotonoha-bot.git
   cd kotonoha-bot
   ```

2. **環境変数の設定**

   ```bash
   cp .env.example .env
   # .env を編集して以下を設定:
   # - DISCORD_TOKEN: Discord Bot Token
   # - ANTHROPIC_API_KEY: Anthropic API Key
   # - LLM_MODEL: anthropic/claude-3-haiku-20240307 (開発用)
   ```

3. **依存関係のインストール**

   ```bash
   # uv をインストール（未インストールの場合）
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # 依存関係をインストール
   uv sync
   ```

4. **Bot の起動**

   ```bash
   uv run python -m kotonoha_bot.main
   ```

詳細なセットアップ手順は [Getting Started ガイド](./docs/getting-started.md) を参照してください。

## プロジェクト構成

```txt
kotonoha-bot/
├── src/kotonoha_bot/      # ソースコード
│   ├── main.py            # Bot エントリーポイント
│   ├── bot/               # Discord Bot 関連
│   │   ├── client.py      # Bot クライアント
│   │   └── handlers.py    # イベントハンドラー
│   ├── ai/                # AI プロバイダー（LiteLLM）
│   ├── session/           # セッション管理
│   ├── db/                # データベース（SQLite）
│   ├── router/            # メッセージルーティング
│   ├── eavesdrop/         # 聞き耳型機能
│   ├── commands/          # スラッシュコマンド
│   ├── rate_limit/        # レート制限
│   ├── errors/            # エラーハンドリング
│   └── utils/             # ユーティリティ
├── prompts/               # プロンプトファイル（Markdown）
│   ├── system_prompt.md                              # システムプロンプト
│   ├── eavesdrop_judge_prompt.md                    # 聞き耳型判定用プロンプト
│   ├── eavesdrop_response_prompt.md                 # 聞き耳型応答生成用プロンプト
│   ├── eavesdrop_same_conversation_prompt.md        # 聞き耳型同一会話判定用プロンプト
│   ├── eavesdrop_conversation_state_prompt.md       # 聞き耳型会話状態判定用プロンプト
│   └── eavesdrop_conversation_situation_changed_prompt.md  # 聞き耳型会話状況変化判定用プロンプト
├── tests/                 # テスト
│   ├── unit/              # 単体テスト
│   └── integration/       # 統合テスト
├── docs/                  # ドキュメント
├── data/                  # データベースファイル（自動生成）
│   └── sessions.db        # SQLite データベース
├── logs/                  # ログファイル（自動生成）
│   └── run.log            # 実行ログ
└── pyproject.toml         # プロジェクト設定
```

### プロンプトファイルの管理

プロンプトファイルは `prompts/` フォルダに集約されています。Docker を使用している場合、`docker-compose.yml` でマウントされているため、コンテナを再起動せずにプロンプトを編集できます。

詳細は [プロンプト管理ガイド](./docs/development/prompt-management.md) を参照してください。

## ドキュメント

詳細なドキュメントは [`docs/`](./docs/) ディレクトリを参照してください。

### 主要ドキュメント

- **[Getting Started](./docs/getting-started.md)**: 開発環境のセットアップガイド
- **[実装ロードマップ](./docs/implementation/roadmap.md)**: 11 段階の実装計画
- **[システムアーキテクチャ](./docs/architecture/system-architecture.md)**: システム構成と技術スタック
- **[Phase 1-6 実装完了報告](./docs/implementation/phases/)**: 各 Phase の実装詳細

### ドキュメント一覧

- [要件定義](./docs/requirements/)
- [アーキテクチャ設計](./docs/architecture/)
- [API 仕様](./docs/specifications/)
- [実装計画](./docs/implementation/)
- [テスト計画](./docs/testing/)
- [運用ガイド](./docs/operations/)
- [開発者向けガイド](./docs/development/)

## 実装状況

### Phase 1: MVP（メンション応答型）✅ 完了

- Discord Bot の基本接続
- メンション応答型の会話契機
- LiteLLM 経由での Claude API 統合
- セッション管理（メモリ + SQLite）
- 会話履歴の保持と復元

### Phase 2: NAS デプロイ ✅ 完了

- Docker コンテナ化
- NAS 上での 24 時間稼働
- データの永続化
- バックアップ機能

### Phase 3: CI/CD、テスト、コード品質 ✅ 完了

- GitHub Actions による CI/CD
- 自動テスト（pytest）
- コード品質チェック（Ruff、ty）

### Phase 4: メッセージ長制限、バッチ同期 ✅ 完了

- メッセージ分割機能
- バッチ同期によるセッション保存の最適化

### Phase 5: 会話の契機拡張 ✅ 完了

- メッセージルーターによる会話の契機判定
- スレッド型: メンション時に自動スレッド作成、スレッド内で会話継続
- 聞き耳型: LLM 判断による自然な会話参加
- 3 つの方式を統一的に扱うインターフェース

### Phase 6: レート制限、コマンド、エラーハンドリング強化 ✅ 完了

- リクエストキューによるレート制限管理
- トークンバケットによる API レート制限対応
- スラッシュコマンド（`/chat reset`, `/chat status`）
- ユーザーフレンドリーなエラーメッセージ

### Phase 7-11: 未実装

- Phase 7: aiosqlite への移行（非同期化）
- Phase 8: 完全リファクタリング
- Phase 9: 高度な運用機能（モニタリング・設定管理・コスト管理）
- Phase 10: 自動化・最適化機能
- Phase 11: 監査機能

詳細は [実装ロードマップ](./docs/implementation/roadmap.md) を参照してください。

#### Docker デプロイ

```bash
# 初回セットアップ
mkdir -p data logs backups
sudo chown -R 1000:1000 data logs backups

# 環境変数の設定
cp .env.example .env
# .env を編集して必要な値を設定

# コンテナのビルドと起動
docker compose build
docker compose up -d

# ログの確認
docker compose logs -f
```

**重要**: 初回起動前に、ホスト側でディレクトリを作成し、
適切な権限を設定してください。Docker が存在しないディレクトリを自動作成すると、
`root:root` 所有になり、コンテナ内の `botuser` (UID 1000) が書き込めなくなります。

詳細は [Phase 2 実装ガイド](./docs/implementation/phases/phase2.md) を参照してください。

## 開発

### 開発環境のセットアップ

```bash
# 開発用依存関係を含めてインストール
uv sync --group dev

# コードフォーマットとリント
uv run ruff format .
uv run ruff check .

# 型チェック
uv run ty check src/

# テストの実行
uv run pytest

# カバレッジ付きでテスト実行
uv run pytest --cov=src/kotonoha_bot --cov-report=html
```

## ライセンス

MIT License

Copyright (c) 2026 fluxrozin

詳細は [LICENSE](./LICENSE) ファイルを参照してください。

## 作者

- fluxrozin ([fluxrozin@gmail.com](mailto:fluxrozin@gmail.com))

## リンク

- [Discord Developer Portal](https://discord.com/developers/applications)
- [Anthropic Console](https://console.anthropic.com/)
- [LiteLLM Documentation](https://docs.litellm.ai/)
- [discord.py Documentation](https://discordpy.readthedocs.io/)

詳細なドキュメントは [docs/README.md](./docs/README.md) を参照してください。

---

**注意**: このプロジェクトは開発中です。本番環境で使用する前に、適切なセキュリティ設定とテストを実施してください。
