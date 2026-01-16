# Kotonoha（コトノハ）Discord ボット ドキュメント

場面緘黙自助グループ運営支援 Discord ボットのドキュメント集です。

## クイックスタート

- **[Getting Started](./getting-started.md)**: 5 分で始める開発環境セットアップガイド（初めての方はここから）

## ドキュメント構成

### 要件定義

- [**要件概要**](./requirements/overview.md): プロジェクトの目的、背景、スコープ、
  システム構成、制約事項、成功基準（プロジェクト理解の出発点）
- [**Bot ペルソナ要件**](./requirements/persona-requirements.md):
  場面緘黙支援のための Bot ペルソナ定義、コミュニケーション要件、禁止事項
  （Bot の性格と応答スタイルの設計）
- [機能要件一覧](./requirements/functional-requirements.md):
  基本機能、会話の契機、セッション管理、AI 機能、エラーハンドリング、
  コマンド、運用機能の詳細要件と非機能要件
- [会話の契機の詳細](./requirements/conversation-triggers.md):
  メンション応答型、スレッド型、聞き耳型（LLM 判断・ルールベース）の
  3 つの会話方式の詳細説明
- [ユーザーストーリー](./requirements/user-stories.md):
  エンドユーザー視点の機能記述、エピック、受け入れテストシナリオ
- [ユースケース](./requirements/use-cases.md):
  各会話の契機、会話継続、エラー処理の詳細なユースケース記述とフロー図
- [プロジェクト管理](./requirements/project-management.md):
  WBS（作業分解構造）、プロダクトバックログ、6 スプリント計画、
  マイルストーン、リスク管理

### アーキテクチャ

- [**システム構成図**](./architecture/system-architecture.md):
  システムアーキテクチャ図、技術スタック、環境変数、ディレクトリ構造
  （システム理解の出発点）
- [基本設計書](./architecture/basic-design.md):
  レイヤー構成、モジュール設計、モジュール間の依存関係、責務分担
- [詳細設計書](./architecture/detailed-design.md):
  各モジュールのクラス・メソッド仕様、パラメータ、戻り値、依存関係
- [データベース設計](./architecture/database-design.md):
  ER 図、テーブル定義（sessions/messages/settings）、
  永続化戦略、インデックス設計
- [**ADR (Architecture Decision Records)**](./architecture/adr/):
  アーキテクチャ上の重要な意思決定の記録とその理由
  - [ADR について](./architecture/adr/README.md):
    ADR の目的、命名規則、ステータス、テンプレート、作成方法
  - [ADR-0001: Python 3.14 の採用](./architecture/adr/0001-use-python-3-14.md):
    Python 3.14 採用の理由
  - [ADR-0002: LiteLLM マルチプロバイダー戦略](./architecture/adr/0002-litellm-multi-provider-strategy.md):
    Claude API（LiteLLM 経由）採用の理由、代替案の比較と評価
  - [ADR-0003: SQLite の採用](./architecture/adr/0003-use-sqlite.md):
    SQLite 採用の理由と代替案比較
  - [ADR-0004: ハイブリッドセッション管理](./architecture/adr/0004-hybrid-session-management.md):
    SQLite + ChatSession ハイブリッド管理の採用理由、
    同期戦略、代替案比較
  - [ADR-0005: 4 つの会話の契機](./architecture/adr/0005-four-conversation-triggers.md):
    メンション型・スレッド型・DM 型・聞き耳型の採用理由
  - [ADR-0006: aiosqlite への移行](./architecture/adr/0006-migrate-to-aiosqlite.md):
    非同期データベースアクセスのための aiosqlite 移行の理由と計画

### 仕様書

- [API 仕様書](./specifications/api-specification.md):
  Discord API（WebSocket/HTTP）、Claude API、内部 API の詳細仕様と
  リクエスト・レスポンス形式
- [コマンド仕様書](./specifications/command-specification.md):
  スラッシュコマンド（/chat start, reset, status, /settings）の仕様と使用例
- [イベント処理仕様書](./specifications/event-specification.md):
  Discord イベント（message, thread, ready）の処理フローとカスタムイベント
- [Discord メッセージフォーマット仕様](./specifications/discord-message-formatting.md):
  Discord のメッセージフォーマット（Markdown、Embed など）の詳細
- [聞き耳型機能仕様書](./specifications/eavesdrop-specification.md):
  聞き耳型機能の詳細仕様、判定ロジック、応答生成、会話状態管理

### 実装

- [**実装ロードマップ**](./implementation/roadmap.md):
  11 段階の実装計画（環境構築 →NAS デプロイ →AI 応答 → セッション管理 →
  会話の契機 → 高度機能 →aiosqlite 移行 → 完全リファクタリング →
  高度運用機能 → 自動化・最適化 → 監査機能）と各段階の詳細
  （実装開始前に必読）
- [実装検討事項](./implementation/considerations.md):
  実装前に検討すべき技術的詳細（エラーハンドリング、レート制限、セキュリティなど）
- [ミドルウェア選定書](./implementation/middleware-selection.md):
  Python 3.14、discord.py、uv、Claude API など使用技術の選定理由と代替案比較
- [監査ログ実装計画](./implementation/audit-logging-implementation-plan.md):
  監査ログ機能の実装計画、データベーススキーマ、実装ステップ
- [知識ベース設計](./implementation/knowledge-base-design.md):
  知識ベース機能の設計と実装計画
- [**Phase 1 実装計画**](./implementation/phases/phase1.md):
  MVP（メンション応答型）の詳細実装ステップ、コード例、完了基準
- [Phase 2 実装計画](./implementation/phases/phase2.md):
  NAS デプロイ（Docker 化・24 時間稼働）の詳細実装ステップ
- [Phase 3 実装計画](./implementation/phases/phase3.md):
  CI/CD、テスト、コード品質の詳細実装ステップ
- [Phase 4 実装計画](./implementation/phases/phase4.md):
  メッセージ長制限、バッチ同期の詳細実装ステップ
- [Phase 5 実装計画](./implementation/phases/phase5.md):
  スレッド型、聞き耳型の詳細実装ステップ
- [Phase 6 実装計画](./implementation/phases/phase6.md):
  レート制限、コマンド、エラーハンドリング強化の詳細実装ステップ

### テスト

- [テスト計画書](./testing/test-plan.md): テスト戦略（単体・統合・システム・受入）、テスト項目、環境、手法
- [テスト仕様書](./testing/test-specification.md): 具体的なテストケース、期待される結果、テストデータ

### 運用

- [デプロイメント・運用](./operations/deployment-operations.md): CI/CD パイプライン（GitHub Actions→GHCR→Watchtower）、デプロイ手順、運用フロー、監視
- [ヘルスチェック](./operations/health-check.md): Docker ヘルスチェックと HTTP エンドポイントの設定・使用方法
- [トラブルシューティング](./operations/troubleshooting.md): よくある問題（Discord 接続、API エラー、DB 問題、パフォーマンス、デプロイメント）と解決方法

### 開発者向け

- [コントリビューションガイド](./development/contributing.md):
  開発フロー、コーディング規約、コミット規約、PR ガイドライン、テストの書き方
- [FAQ](./development/faq.md):
  セットアップ、開発環境、Bot 動作、AI 機能、セッション管理、
  デプロイメント、トラブルシューティングに関するよくある質問と回答
- [LiteLLM 必要性分析](./development/litellm-necessity-analysis.md):
  LiteLLM 採用の必要性と検討資料
- [LLM プロバイダー比較](./development/llm-provider-comparison.md):
  LLM プロバイダーの比較と選定理由
- [聞き耳型判定モデル比較](./development/eavesdrop-judge-model-comparison.md):
  聞き耳型判定に使用する LLM モデルの比較
- [プロンプト管理](./development/prompt-management.md):
  プロンプトファイルの管理方法とベストプラクティス

---

## ドキュメントの読み方

### 初めての方

1. **[Getting Started](./getting-started.md)**: 開発環境のセットアップ
2. **[要件概要](./requirements/overview.md)**: プロジェクトの目的と全体像を把握
3. **[システム構成図](./architecture/system-architecture.md)**: システムアーキテクチャを理解

### 開発を始める方

1. **[実装ロードマップ](./implementation/roadmap.md)**: 段階的な実装計画を確認
2. **[ADR](./architecture/adr/)**: 重要な技術的決定の背景を理解
3. **[実装検討事項](./implementation/considerations.md)**: 実装上の注意点を確認
4. **[プロジェクト管理](./requirements/project-management.md)**: 現在のスプリントとタスクを確認

### 設計を確認する方

1. **[基本設計書](./architecture/basic-design.md)**: システムの基本設計
2. **[詳細設計書](./architecture/detailed-design.md)**: モジュール・関数の詳細
3. **[データベース設計](./architecture/database-design.md)**: データモデルとスキーマ
4. **[API 仕様書](./specifications/api-specification.md)**: API インターフェース

### 実装する方

1. **[コマンド仕様書](./specifications/command-specification.md)**: 実装する機能の仕様
2. **[イベント処理仕様書](./specifications/event-specification.md)**: イベント処理の仕様
3. **[コントリビューションガイド](./development/contributing.md)**: コーディング規約とワークフロー

### テストする方

1. **[テスト計画書](./testing/test-plan.md)**: テスト戦略
2. **[テスト仕様書](./testing/test-specification.md)**: テストケース
3. **[コントリビューションガイド - テスト](./development/contributing.md#テストの書き方)**: テストの書き方

### デプロイ・運用する方

1. **[デプロイメント・運用](./operations/deployment-operations.md)**: デプロイ手順
2. **[システム構成図](./architecture/system-architecture.md)**: インフラ構成
3. **[トラブルシューティング](./operations/troubleshooting.md)**: 問題解決ガイド

### 困ったときは

1. **[FAQ](./development/faq.md)**: よくある質問
2. **[トラブルシューティング](./operations/troubleshooting.md)**: 具体的な問題と解決方法
3. **GitHub Issues**: 質問や報告（注: GitHub リポジトリ URL は実際の組織名/ユーザー名に置き換えてください）

---

## ドキュメント構造

```text
docs/
├── README.md                          # このファイル（ドキュメント全体のナビゲーション）
├── getting-started.md                 # 5分で始める開発環境セットアップ
│
├── requirements/                      # 要件定義
│   ├── overview.md                    # 目的、背景、スコープ、制約（必読）
│   ├── persona-requirements.md        # Botペルソナ定義、コミュニケーション要件（必読）
│   ├── functional-requirements.md     # 機能要件・非機能要件の詳細
│   ├── conversation-triggers.md       # 4つの会話方式の詳細説明
│   ├── user-stories.md                # ユーザー視点の機能記述
│   ├── use-cases.md                   # 詳細なユースケース
│   └── project-management.md          # WBS、バックログ、スプリント計画
│
├── architecture/                      # アーキテクチャ
│   ├── system-architecture.md         # システム構成、技術スタック、環境変数（必読）
│   ├── basic-design.md                # レイヤー構成、モジュール設計
│   ├── detailed-design.md             # クラス・メソッド詳細仕様
│   ├── database-design.md             # ER図、テーブル定義、インデックス設計
│   └── adr/                           # Architecture Decision Records
│       ├── README.md                  # ADRの目的と作成方法
│       ├── 0001-use-python-3-14.md    # Python 3.14採用理由
│       ├── 0002-litellm-multi-provider-strategy.md  # LiteLLMマルチプロバイダー戦略
│       ├── 0003-use-sqlite.md         # SQLite採用理由
│       ├── 0004-hybrid-session-management.md  # ハイブリッドセッション管理の採用理由
│       ├── 0005-four-conversation-triggers.md  # 4つの会話の契機
│       └── 0006-migrate-to-aiosqlite.md  # aiosqliteへの移行
│
├── specifications/                    # 仕様書
│   ├── api-specification.md           # Discord/Claude API仕様
│   ├── command-specification.md       # スラッシュコマンド仕様
│   ├── event-specification.md         # イベント処理フロー
│   ├── discord-message-formatting.md  # Discord メッセージフォーマット仕様
│   └── eavesdrop-specification.md     # 聞き耳型機能仕様
│
├── implementation/                    # 実装
│   ├── roadmap.md                     # 11段階実装計画（実装開始前必読）
│   ├── considerations.md              # 実装上の検討事項
│   ├── middleware-selection.md        # 使用技術の選定理由
│   ├── audit-logging-considerations.md  # 監査ログ検討資料
│   ├── audit-logging-implementation-plan.md  # 監査ログ実装計画
│   ├── knowledge-base-design.md       # 知識ベース設計
│   ├── conversation_definition.md     # 会話定義の検討資料
│   ├── conversation_state_llm_judgment.md  # 会話状態LLM判定の検討資料
│   ├── intervention_improvements.md   # 介入改善の検討資料
│   ├── token_optimization.md          # トークン最適化の検討資料
│   └── phases/                        # フェーズ別実装計画
│       ├── phase1.md                  # Phase 1: MVP実装ステップ（完了）
│       ├── phase2.md                  # Phase 2: NASデプロイ（Docker化・24時間稼働）（完了）
│       ├── phase3.md                  # Phase 3: CI/CD、テスト、コード品質（完了）
│       ├── phase4.md                  # Phase 4: メッセージ長制限、バッチ同期（完了）
│       ├── phase5.md                  # Phase 5: スレッド型、聞き耳型（完了）
│       └── phase6.md                  # Phase 6: レート制限、コマンド、エラーハンドリング強化（完了）
│
├── testing/                           # テスト
│   ├── test-plan.md                   # テスト戦略と計画
│   └── test-specification.md          # テストケースと期待結果
│
├── operations/                        # 運用
│   ├── deployment-operations.md       # CI/CDパイプラインと監視
│   ├── health-check.md                # ヘルスチェックの設定・使用方法
│   └── troubleshooting.md             # 問題解決ガイド
│
├── examples/                          # コード例
│   ├── ai_provider_usage_example.md   # AI プロバイダーの使用例
│   └── without_ai_provider.md          # AI プロバイダーなしの実装例
└── development/                       # 開発者向け
    ├── contributing.md                # 開発フロー、規約、PRガイドライン
    ├── faq.md                         # よくある質問と回答
    ├── litellm-necessity-analysis.md  # LiteLLM必要性の検討資料
    ├── llm-provider-comparison.md     # LLMプロバイダー比較資料
    ├── eavesdrop-judge-model-comparison.md  # 聞き耳型判定モデル比較
    └── prompt-management.md          # プロンプト管理
```

### ディレクトリ説明

**requirements/** - プロジェクトの「何を作るか」を定義

- プロジェクトの目的、機能要件、非機能要件、制約条件
- Bot のペルソナ定義とコミュニケーション要件（場面緘黙支援のための設計）
- ユーザーストーリーとユースケース
- プロジェクト管理（WBS、バックログ、スプリント計画）

**architecture/** - システムの「どう作るか」を定義

- システム全体の構成と技術スタック
- モジュール設計とクラス設計
- データベース設計
- 重要な技術的決定（ADR）

**specifications/** - インターフェースの「詳細仕様」を定義

- 外部 API（Discord、Claude）の使用方法
- 内部 API の仕様
- イベント処理とコマンド処理の詳細

**implementation/** - 実装の「手順と計画」を定義

- 段階的な実装ロードマップ
- 各フェーズの詳細な実装計画（ステップバイステップ）
- 実装上の注意点と技術選定理由

**testing/** - テストの「計画と仕様」を定義

- テスト戦略（単体・統合・E2E）
- 具体的なテストケース

**operations/** - 運用の「手順と対処法」を定義

- デプロイ方法（CI/CD）
- トラブルシューティング

**development/** - 開発者の「参加方法」を定義

- コーディング規約とワークフロー
- FAQ（開発・運用に関する質問）

---

## ドキュメントの更新

ドキュメントは随時更新されます。最新の情報については、各ドキュメントの「最終更新日」を確認してください。

### ドキュメント貢献

ドキュメントの改善も大歓迎です！誤字脱字、わかりにくい説明、
不足している情報などがあれば、
[コントリビューションガイド](./development/contributing.md)を参照して
Pull Request を作成してください。

---

## プロジェクト情報

- **プロジェクト名**: Kotonoha（コトノハ）Discord Bot
- **目的**: 場面緘黙自助グループの運営支援
- **技術スタック**: Python 3.14, discord.py, Claude API (LiteLLM), SQLite, Docker
- **ホスティング**: Synology NAS + Docker + Watchtower
- **CI/CD**: GitHub Actions → GHCR → Watchtower

---

**作成日**: 2026 年 1 月 14 日  
**最終更新日**: 2026 年 1 月 15 日  
**バージョン**: 2.2  
**作成者**: kotonoha-bot 開発チーム

## 更新履歴

- **v2.2** (2026-01-15): 実際のフォルダ・ファイル構成に基づいて更新
  - ADR-0006（aiosqlite への移行）を追加
  - 聞き耳型機能仕様書を追加
  - 実装ロードマップを 11 段階に更新
  - Phase 3-6 の実装計画を追加
  - 監査ログ実装計画、知識ベース設計を追加
  - 開発者向けドキュメント（聞き耳型判定モデル比較、プロンプト管理）を追加
  - コード例ディレクトリを追加
  - 実装検討資料（会話定義、会話状態判定、介入改善、トークン最適化）を追加
- **v2.1** (2026-01-14): 初版リリース
