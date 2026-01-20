# Kotonoha（コトノハ）Discord ボット ドキュメント

場面緘黙自助グループ運営支援 Discord ボットのドキュメント集である。

## クイックスタート

- **[Getting Started](./getting-started.md)**: 5分で始める開発環境セットアップガイド（初めての方はここから）

## ドキュメント構成（Vモデル準拠）

このドキュメントは、Vモデルに基づいて構成されている。

### 00_planning/（企画・計画）

プロジェクトの方向性と進捗管理。

- [**プロジェクト管理**](./00_planning/project-management.md): WBS（作業分解構造）、プロダクトバックログ、スプリント計画、マイルストーン、リスク管理
- [**実装ロードマップ**](./00_planning/roadmap.md): 11段階の実装計画（環境構築 → NASデプロイ → AI応答 → セッション管理 → 会話の契機 → 高度機能 → aiosqlite移行 → 完全リファクタリング → 高度運用機能 → 自動化・最適化 → 監査機能）と各段階の詳細（実装開始前に必読）
- [**フェーズ別実装計画**](./00_planning/phases/): 各フェーズの詳細な実装ステップ
  - [Phase 1](./00_planning/phases/phase01.md): MVP（メンション応答型）の詳細実装ステップ（完了）
  - [Phase 2](./00_planning/phases/phase02.md): NASデプロイ（Docker化・24時間稼働）の詳細実装ステップ（完了）
  - [Phase 3](./00_planning/phases/phase03.md): CI/CD、テスト、コード品質の詳細実装ステップ（完了）
  - [Phase 4](./00_planning/phases/phase04.md): メッセージ長制限、バッチ同期の詳細実装ステップ（完了）
  - [Phase 5](./00_planning/phases/phase05.md): スレッド型、聞き耳型の詳細実装ステップ（完了）
  - [Phase 6](./00_planning/phases/phase06.md): レート制限、コマンド、エラーハンドリング強化の詳細実装ステップ（完了）
  - [Phase 7](./00_planning/phases/phase07.md): aiosqliteへの移行（完了）
  - [Phase 8](./00_planning/phases/phase08.md): PostgreSQLへの移行（pgvector対応）
  - [Phase 9](./00_planning/phases/phase09.md): LiteLLM 削除、Anthropic SDK 直接使用への移行
  - [Phase 10](./00_planning/phases/phase10.md): 完全リファクタリング
  - [Phase 11](./00_planning/phases/phase11.md): ハイブリッド検索（pg_bigm）
- [**将来機能レビュー**](./00_planning/phases/future-features-review.md): 将来実装予定の機能のレビュー

### 10_requirements/（要件定義 - Why & What）

ユーザーとシステムの要求事項の定義。

#### 11_business-reqs/（ビジネス要件）

- [**要件概要**](./10_requirements/11_business-reqs/overview.md): プロジェクトの目的、背景、スコープ、システム構成、制約事項、成功基準（プロジェクト理解の出発点）
- [**Bot ペルソナ要件**](./10_requirements/11_business-reqs/persona-requirements.md): 場面緘黙支援のためのBotペルソナ定義、コミュニケーション要件、禁止事項（Botの性格と応答スタイルの設計）
- [**ユーザーストーリー**](./10_requirements/11_business-reqs/user-stories.md): エンドユーザー視点の機能記述、エピック、受け入れテストシナリオ
- [**ユースケース**](./10_requirements/11_business-reqs/use-cases.md): 各会話の契機、会話継続、エラー処理の詳細なユースケース記述とフロー図

#### 12_system-reqs/（システム要件）

- [**機能要件一覧**](./10_requirements/12_system-reqs/functional-requirements.md): 基本機能、会話の契機、セッション管理、AI機能、エラーハンドリング、コマンド、運用機能の詳細要件と非機能要件
- [**会話の契機の詳細**](./10_requirements/12_system-reqs/conversation-triggers.md): メンション応答型、スレッド型、聞き耳型（LLM判断・ルールベース）の3つの会話方式の詳細説明
- [**機能一覧**](./10_requirements/12_system-reqs/features-list.md): 実装済み機能の一覧
- [**ダッシュボードオプション**](./10_requirements/12_system-reqs/dashboard-options.md): ダッシュボード機能の要件

### 20_architecture/（アーキテクチャ - High-level How）

システム全体の構造と、技術的な意思決定。

#### 21_system-arch/（システム構成）

- [**システム構成図**](./20_architecture/21_system-arch/system-architecture.md): システムアーキテクチャ図、技術スタック、環境変数、ディレクトリ構造（システム理解の出発点）
- [**基本設計書**](./20_architecture/21_system-arch/basic-design.md): レイヤー構成、モジュール設計、モジュール間の依存関係、責務分担

#### 22_adrs/（ADR - Architecture Decision Records）

アーキテクチャ上の重要な意思決定の記録とその理由。

- [**ADR について**](./20_architecture/22_adrs/README.md): ADRの目的、命名規則、ステータス、テンプレート、作成方法
- [**ADR-0001: Python 3.14 の採用**](./20_architecture/22_adrs/0001-use-python-3-14.md): Python 3.14採用の理由
- [**ADR-0002: LiteLLM マルチプロバイダー戦略**](./20_architecture/22_adrs/0002-litellm-multi-provider-strategy.md): ~~Claude API（LiteLLM経由）採用の理由~~（[ADR-0011](./20_architecture/22_adrs/0011-remove-litellm-direct-sdk.md)により置き換え）
- [**ADR-0011: LiteLLM の削除とプロバイダー SDK の直接使用**](./20_architecture/22_adrs/0011-remove-litellm-direct-sdk.md): Anthropic SDK 直接使用への移行理由と決定
- [**ADR-0003: SQLite の採用**](./20_architecture/22_adrs/0003-use-sqlite.md): SQLite採用の理由と代替案比較
- [**ADR-0004: ハイブリッドセッション管理**](./20_architecture/22_adrs/0004-hybrid-session-management.md): SQLite + ChatSessionハイブリッド管理の採用理由、同期戦略、代替案比較
- [**ADR-0005: 4つの会話の契機**](./20_architecture/22_adrs/0005-four-conversation-triggers.md): メンション型・スレッド型・DM型・聞き耳型の採用理由
- [**ADR-0006: aiosqlite への移行**](./20_architecture/22_adrs/0006-migrate-to-aiosqlite.md): 非同期データベースアクセスのためのaiosqlite移行の理由と計画
- [**ADR-0007: PostgreSQL への移行**](./20_architecture/22_adrs/0007-migrate-to-postgresql.md): PostgreSQL + pgvectorへの移行の理由と計画
- [**ミドルウェア選定書**](./20_architecture/22_adrs/middleware-selection.md): Python 3.14、discord.py、uv、Claude APIなど使用技術の選定理由と代替案比較
- [**LiteLLM 必要性分析**](./20_architecture/22_adrs/litellm-necessity-analysis.md): ~~LiteLLM採用の必要性と検討資料~~（[ADR-0011](./20_architecture/22_adrs/0011-remove-litellm-direct-sdk.md)により置き換え、参考資料として保持）
- [**LLM プロバイダー比較**](./20_architecture/22_adrs/llm-provider-comparison.md): LLMプロバイダーの比較と選定理由
- [**聞き耳型判定モデル比較**](./20_architecture/22_adrs/eavesdrop-judge-model-comparison.md): 聞き耳型判定に使用するLLMモデルの比較
- [**監査ログ検討資料**](./20_architecture/22_adrs/audit-logging-considerations.md): 監査ログ機能の検討資料

### 30_design_basic/（基本設計/外部設計 - Interfaces）

システムの「外側」から見た振る舞いの定義（ブラックボックス視点）。

- [**API 仕様書**](./30_design_basic/api-specification.md): Discord API（WebSocket/HTTP）、Claude API、内部APIの詳細仕様とリクエスト・レスポンス形式
- [**コマンド仕様書**](./30_design_basic/command-specification.md): スラッシュコマンド（/chat start, reset, status, /settings）の仕様と使用例
- [**イベント処理仕様書**](./30_design_basic/event-specification.md): Discordイベント（message, thread, ready）の処理フローとカスタムイベント
- [**Discord メッセージフォーマット仕様**](./30_design_basic/discord-message-formatting.md): Discordのメッセージフォーマット（Markdown、Embedなど）の詳細
- [**聞き耳型機能仕様書**](./30_design_basic/eavesdrop-specification.md): 聞き耳型機能の詳細仕様、判定ロジック、応答生成、会話状態管理

### 40_design_detailed/（詳細設計/内部設計 - Internals）

システムの「内側」の構造定義（ホワイトボックス視点）。

#### 41_logic/（ロジック設計）

- [**詳細設計書**](./40_design_detailed/41_logic/detailed-design.md): 各モジュールのクラス・メソッド仕様、パラメータ、戻り値、依存関係
- [**知識ベース設計**](./40_design_detailed/41_logic/knowledge-base-design.md): 知識ベース機能の設計と実装計画

#### 42_db-schema-physical/（データベーススキーマ）

- [**データベース設計**](./40_design_detailed/42_db-schema-physical/database-design.md): ER図、テーブル定義（sessions/messages/settings）、永続化戦略、インデックス設計
- [**PostgreSQL スキーマ概要**](./40_design_detailed/42_db-schema-physical/postgresql-schema-overview.md): PostgreSQLスキーマの概要、ER図、拡張機能と型定義
- [**PostgreSQL テーブル定義**](./40_design_detailed/42_db-schema-physical/postgresql-schema-tables.md): PostgreSQLテーブルの詳細定義
- [**PostgreSQL インデックス設計**](./40_design_detailed/42_db-schema-physical/postgresql-schema-indexes.md): PostgreSQLインデックス、制約、データ型の説明
- [**PostgreSQL 完全なDDLスクリプト**](./40_design_detailed/42_db-schema-physical/postgresql-schema-ddl.md): 完全なDDLスクリプト、環境変数一覧、ヘルスチェック実装

### 50_implementation/（実装ガイド - Procedures）

開発者のための手順書・マニュアル。

#### 51_guides/（ガイド）

- [**開発環境ガイド**](./50_implementation/51_guides/development-environment-guide.md): 開発環境のセットアップ、通常の開発フロー、マイグレーション管理、データベース管理、テストの実行方法（**開発者必読**）
- [**実装検討事項**](./50_implementation/51_guides/considerations.md): 実装前に検討すべき技術的詳細（エラーハンドリング、レート制限、セキュリティなど）
- [**コード品質チェック・テスト実施マニュアル**](./50_implementation/51_guides/code-quality-and-testing.md): 型ヒント、docstring、フォーマット、型チェック、テストカバレッジのベストプラクティス（**開発者必読**）
- [**プロンプト管理**](./50_implementation/51_guides/prompt-management.md): プロンプトファイルの管理方法とベストプラクティス
- [**FAQ**](./50_implementation/51_guides/faq.md): セットアップ、開発環境、Bot動作、AI機能、セッション管理、デプロイメント、トラブルシューティングに関するよくある質問と回答
- [**PostgreSQL クエリガイド**](./50_implementation/51_guides/postgresql-query-guide.md): PostgreSQLの使用例とクエリ
- [**PostgreSQL 実装ガイド**](./50_implementation/51_guides/postgresql-implementation-guide.md): PostgreSQLのパフォーマンス考慮事項、将来の拡張性、実装上の注意事項とベストプラクティス、バックアップ戦略
- [**会話定義**](./50_implementation/51_guides/conversation-definition.md): 会話定義の検討資料
- [**会話状態LLM判定**](./50_implementation/51_guides/conversation-state-llm-judgment.md): 会話状態LLM判定の検討資料
- [**介入改善**](./50_implementation/51_guides/intervention-improvements.md): 介入改善の検討資料
- [**トークン最適化**](./50_implementation/51_guides/token-optimization.md): トークン最適化の検討資料
- [**コード例**](./50_implementation/51_guides/examples/): 実装例
  - [AI プロバイダーの使用例](./50_implementation/51_guides/examples/ai_provider_usage_example.md)
  - [AI プロバイダーなしの実装例](./50_implementation/51_guides/examples/without_ai_provider.md)

#### 52_procedures/（手順）

- [**PostgreSQL 実装手順**](./50_implementation/52_procedures/postgresql-implementation.md): PostgreSQL実装の詳細手順
- [**PostgreSQL カスタムイメージ作成・デプロイ完全ガイド**](./50_implementation/52_procedures/postgres-custom-image-guide.md): Dockerfile.postgresを使用したカスタムイメージの作成、GHCRへのプッシュ、自動化、導入・デプロイまでの全手順
- [**PostgreSQL セッションアーカイブ手順**](./50_implementation/52_procedures/postgresql-session-archiving.md): PostgreSQLセッションアーカイブの手順
- [**PostgreSQL Embedding処理手順**](./50_implementation/52_procedures/postgresql-embedding-processing.md): PostgreSQL Embedding処理の手順
- [**監査ログ実装計画**](./50_implementation/52_procedures/audit-logging-implementation-plan.md): 監査ログ機能の実装計画、データベーススキーマ、実装ステップ

### 60_testing/（テスト - Verification）

品質保証の計画と仕様。

- [**テスト計画書**](./60_testing/test-plan.md): テスト戦略（単体・統合・システム・受入）、テスト項目、環境、手法
- [**テスト仕様書**](./60_testing/test-specification.md): 具体的なテストケース、期待される結果、テストデータ
- [**PostgreSQL テスト戦略**](./60_testing/postgresql-testing-strategy.md): PostgreSQLテストの戦略と計画

### 90_operations/（運用保守 - Operations）

リリース後の運用情報。

- [**デプロイメント・運用**](./90_operations/deployment-operations.md): CI/CDパイプライン（GitHub Actions→GHCR→Watchtower）、デプロイ手順、運用フロー、監視
- [**ヘルスチェック**](./90_operations/health-check.md): DockerヘルスチェックとHTTPエンドポイントの設定・使用方法
- [**トラブルシューティング**](./90_operations/troubleshooting.md): よくある問題（Discord接続、APIエラー、DB問題、パフォーマンス、デプロイメント）と解決方法

---

## ドキュメントの読み方

### 初めての方

1. **[Getting Started](./getting-started.md)**: 開発環境のセットアップ
2. **[要件概要](./10_requirements/11_business-reqs/overview.md)**: プロジェクトの目的と全体像を把握
3. **[システム構成図](./20_architecture/21_system-arch/system-architecture.md)**: システムアーキテクチャを理解

### 開発を始める方

1. **[実装ロードマップ](./00_planning/roadmap.md)**: 段階的な実装計画を確認
2. **[ADR](./20_architecture/22_adrs/)**: 重要な技術的決定の背景を理解
3. **[実装検討事項](./50_implementation/51_guides/considerations.md)**: 実装上の注意点を確認
4. **[コード品質チェック・テスト実施マニュアル](./50_implementation/51_guides/code-quality-and-testing.md)**: コード品質ツールの使い方とベストプラクティス
5. **[プロジェクト管理](./00_planning/project-management.md)**: 現在のスプリントとタスクを確認

### 設計を確認する方

1. **[基本設計書](./20_architecture/21_system-arch/basic-design.md)**: システムの基本設計
2. **[詳細設計書](./40_design_detailed/41_logic/detailed-design.md)**: モジュール・関数の詳細
3. **[データベース設計](./40_design_detailed/42_db-schema-physical/database-design.md)**: データモデルとスキーマ
4. **[API 仕様書](./30_design_basic/api-specification.md)**: APIインターフェース

### 実装する方

1. **[コマンド仕様書](./30_design_basic/command-specification.md)**: 実装する機能の仕様
2. **[イベント処理仕様書](./30_design_basic/event-specification.md)**: イベント処理の仕様
3. **[実装ガイド](./50_implementation/51_guides/)**: 実装上のガイドライン

### テストする方

1. **[テスト計画書](./60_testing/test-plan.md)**: テスト戦略
2. **[テスト仕様書](./60_testing/test-specification.md)**: テストケース

### デプロイ・運用する方

1. **[デプロイメント・運用](./90_operations/deployment-operations.md)**: デプロイ手順
2. **[システム構成図](./20_architecture/21_system-arch/system-architecture.md)**: インフラ構成
3. **[トラブルシューティング](./90_operations/troubleshooting.md)**: 問題解決ガイド

### 困ったときは

1. **[FAQ](./50_implementation/51_guides/faq.md)**: よくある質問
2. **[トラブルシューティング](./90_operations/troubleshooting.md)**: 具体的な問題と解決方法
3. **GitHub Issues**: 質問や報告（注: GitHubリポジトリURLは実際の組織名/ユーザー名に置き換えること）

---

## ドキュメント構造（Vモデル準拠）

```text
docs_new/
├── README.md                          # このファイル（ドキュメント全体のナビゲーション）
├── getting-started.md                 # 5分で始める開発環境セットアップ
│
├── 00_planning/                       # 企画・計画
│   ├── project-management.md          # WBS、バックログ、スプリント計画
│   ├── roadmap.md                     # 11段階実装計画（実装開始前必読）
│   ├── phases/
│   │   ├── future-features-review.md  # 将来機能レビュー
│   └── phases/                        # フェーズ別実装計画
│       ├── phase01.md                # Phase 1: MVP実装ステップ（完了）
│       ├── phase02.md                # Phase 2: NASデプロイ（完了）
│       ├── phase03.md                # Phase 3: CI/CD、テスト（完了）
│       ├── phase04.md                # Phase 4: メッセージ長制限（完了）
│       ├── phase05.md                # Phase 5: スレッド型、聞き耳型（完了）
│       ├── phase06.md                # Phase 6: レート制限、コマンド（完了）
│       ├── phase07.md                # Phase 7: aiosqlite移行（完了）
│       ├── phase08.md                # Phase 8: PostgreSQL移行
│       ├── phase09.md                # Phase 9: LiteLLM削除、Anthropic SDK直接使用への移行
│       ├── phase10.md                # Phase 10: 完全リファクタリング
│       ├── phase10-implementation.md  # Phase 10: 完全リファクタリング実装ガイド（メイン）
│       ├── phase10-implementation-steps.md  # Phase 10: 詳細実装計画（Step 0-7）
│       ├── phase10-implementation-testing.md  # Phase 10: テスト・完了基準・リスク管理
│       └── phase11.md                 # Phase 11: ハイブリッド検索（pg_bigm）
│
├── 10_requirements/                   # 要件定義
│   ├── 11_business-reqs/              # ビジネス要件
│   │   ├── overview.md                # 目的、背景、スコープ、制約（必読）
│   │   ├── persona-requirements.md    # Botペルソナ定義、コミュニケーション要件（必読）
│   │   ├── user-stories.md            # ユーザー視点の機能記述
│   │   └── use-cases.md               # 詳細なユースケース
│   └── 12_system-reqs/                # システム要件
│       ├── functional-requirements.md # 機能要件・非機能要件の詳細
│       ├── conversation-triggers.md   # 4つの会話方式の詳細説明
│       ├── features-list.md           # 機能一覧
│       └── dashboard-options.md       # ダッシュボードオプション
│
├── 20_architecture/                   # アーキテクチャ
│   ├── 21_system-arch/                # システム構成
│   │   ├── system-architecture.md     # システム構成、技術スタック、環境変数（必読）
│   │   └── basic-design.md            # レイヤー構成、モジュール設計
│   └── 22_adrs/                       # Architecture Decision Records
│       ├── README.md                  # ADRの目的と作成方法
│       ├── 0001-use-python-3-14.md    # Python 3.14採用理由
│       ├── 0002-litellm-multi-provider-strategy.md  # LiteLLMマルチプロバイダー戦略
│       ├── 0003-use-sqlite.md         # SQLite採用理由
│       ├── 0004-hybrid-session-management.md  # ハイブリッドセッション管理
│       ├── 0005-four-conversation-triggers.md  # 4つの会話の契機
│       ├── 0006-migrate-to-aiosqlite.md  # aiosqliteへの移行
│       ├── 0007-migrate-to-postgresql.md  # PostgreSQLへの移行
│       ├── middleware-selection.md     # ミドルウェア選定書
│       ├── litellm-necessity-analysis.md  # LiteLLM必要性分析
│       ├── llm-provider-comparison.md # LLMプロバイダー比較
│       ├── eavesdrop-judge-model-comparison.md  # 聞き耳型判定モデル比較
│       └── audit-logging-considerations.md  # 監査ログ検討資料
│
├── 30_design_basic/                    # 基本設計/外部設計
│   ├── api-specification.md           # Discord/Claude API仕様
│   ├── command-specification.md       # スラッシュコマンド仕様
│   ├── event-specification.md         # イベント処理フロー
│   ├── discord-message-formatting.md  # Discord メッセージフォーマット仕様
│   └── eavesdrop-specification.md     # 聞き耳型機能仕様
│
├── 40_design_detailed/                 # 詳細設計/内部設計
│   ├── 41_logic/                      # ロジック設計
│   │   ├── detailed-design.md         # クラス・メソッド詳細仕様
│   │   └── knowledge-base-design.md   # 知識ベース設計
│   └── 42_db-schema-physical/          # データベーススキーマ
│       ├── database-design.md         # ER図、テーブル定義、インデックス設計
│       ├── postgresql-schema-overview.md  # PostgreSQLスキーマ概要
│       ├── postgresql-schema-tables.md    # PostgreSQLテーブル定義
│       ├── postgresql-schema-indexes.md   # PostgreSQLインデックス設計
│       └── postgresql-schema-ddl.md       # PostgreSQL完全なDDLスクリプト
│
├── 50_implementation/                  # 実装ガイド
│   ├── 51_guides/                     # ガイド
│   │   ├── considerations.md          # 実装上の検討事項
│   │   ├── code-quality-and-testing.md # コード品質チェック・テスト実施マニュアル（開発者必読）
│   │   ├── prompt-management.md       # プロンプト管理
│   │   ├── faq.md                     # よくある質問と回答
│   │   ├── postgresql-query-guide.md  # PostgreSQLクエリガイド
│   │   ├── postgresql-implementation-guide.md  # PostgreSQL実装ガイド
│   │   ├── conversation-definition.md # 会話定義の検討資料
│   │   ├── conversation-state-llm-judgment.md  # 会話状態LLM判定の検討資料
│   │   ├── intervention-improvements.md  # 介入改善の検討資料
│   │   ├── token-optimization.md      # トークン最適化の検討資料
│   │   └── examples/                  # コード例
│   │       ├── ai_provider_usage_example.md
│   │       └── without_ai_provider.md
│   └── 52_procedures/                  # 手順
│       ├── postgresql-implementation.md  # PostgreSQL実装手順
│       ├── postgresql-session-archiving.md  # PostgreSQLセッションアーカイブ手順
│       ├── postgresql-embedding-processing.md  # PostgreSQL Embedding処理手順
│       └── audit-logging-implementation-plan.md  # 監査ログ実装計画
│
├── 60_testing/                         # テスト
│   ├── test-plan.md                   # テスト戦略と計画
│   ├── test-specification.md          # テストケースと期待結果
│   └── postgresql-testing-strategy.md # PostgreSQLテスト戦略
│
└── 90_operations/                      # 運用保守
    ├── deployment-operations.md       # CI/CDパイプラインと監視
    ├── health-check.md                 # ヘルスチェックの設定・使用方法
    └── troubleshooting.md              # 問題解決ガイド
│
└── XX_temporary/                       # 一時ドキュメント置き場（⚠️ 整理が必要）
    └── README.md                       # 一時ドキュメントの使い方と整理方法
```

### ディレクトリ説明

**00_planning/** - プロジェクトの「方向性」を定義

- プロジェクト管理（WBS、バックログ、スプリント計画）
- 実装ロードマップ（段階的な実装計画）
- フェーズ別実装計画（各フェーズの詳細ステップ）

**10_requirements/** - プロジェクトの「何を作るか」を定義

- ビジネス要件: プロジェクトの目的、機能要件、Botのペルソナ定義、ユーザーストーリー、ユースケース
- システム要件: 機能要件・非機能要件の詳細、会話の契機の詳細

**20_architecture/** - システムの「どう作るか」を定義

- システム構成: システム全体の構成と技術スタック、モジュール設計
- ADR: 重要な技術的決定（技術選定の理由、比較検討、却下された案）

**30_design_basic/** - インターフェースの「詳細仕様」を定義

- 外部API（Discord、Claude）の使用方法
- 内部APIの仕様
- イベント処理とコマンド処理の詳細

**40_design_detailed/** - システムの「内側」の構造を定義

- ロジック設計: 各モジュールのクラス・メソッド仕様、パラメータ、戻り値、依存関係
- データベーススキーマ: ER図、テーブル定義、インデックス設計

**50_implementation/** - 実装の「手順と計画」を定義

- ガイド: 実装上の注意点と技術選定理由、コーディング規約、プロンプト管理手法
- 手順: 環境構築手順、マイグレーション実行手順、デプロイ手順

**60_testing/** - テストの「計画と仕様」を定義

- テスト戦略（単体・統合・E2E）
- 具体的なテストケース

**90_operations/** - 運用の「手順と対処法」を定義

- デプロイ方法（CI/CD）
- トラブルシューティング

**XX_temporary/** - 一時的なドキュメントのステージングエリア

- 一時的なメモ、レビュー、検討資料を置く場所
- 定期的に評価し、適切なVモデル構造のフォルダに分類・分割・統合する
- 詳細は [XX_temporary/README.md](./XX_temporary/README.md) を参照

---

## ドキュメントの更新

ドキュメントは随時更新される。最新の情報については、各ドキュメントの「最終更新日」を確認すること。

---

## プロジェクト情報

- **プロジェクト名**: Kotonoha（コトノハ）Discord Bot
- **目的**: 場面緘黙自助グループの運営支援
- **技術スタック**: Python 3.14, discord.py, Claude API (Anthropic SDK), PostgreSQL 18 + pgvector, Docker
- **ホスティング**: Synology NAS + Docker + Watchtower
- **CI/CD**: GitHub Actions → GHCR → Watchtower

---

**作成日**: 2026年1月19日  
**最終更新日**: 2026年1月19日  
**バージョン**: 3.0（Vモデル準拠版）  
**作成者**: kotonoha-bot 開発チーム

## 更新履歴

- **v3.0** (2026-01-19): Vモデル準拠の新構造に完全移行
  - ドキュメントをVモデル構造（00_planning 〜 90_operations）に再配置
  - 巨大ファイル（postgresql-schema-design.md）を機能単位で分割
  - リンクを新構造に更新
  - 相互参照リンクを追加
