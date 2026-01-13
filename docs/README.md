# Kotonoha（コトノハ）Discord ボット ドキュメント

場面緘黙自助グループ運営支援 Discord ボットのドキュメント集です。

## ドキュメント一覧

### プロジェクト管理

- **[要件定義書](./requirements.md)**: プロジェクトの要件定義
- **[機能要件一覧・非機能要件一覧](./functional-requirements.md)**: 機能要件と非機能要件の詳細一覧
- **[WBS（作業分解構造）](./wbs.md)**: プロジェクトの作業分解
- **[実装ロードマップ](./implementation-roadmap.md)**: 6 段階の実装計画と順序 ⭐ **実装開始前に必読**
- **[プロダクトバックログ](./product-backlog.md)**: 開発項目のバックログ
- **[ユーザーストーリー](./user-stories.md)**: ユーザーストーリー一覧

### 設計ドキュメント

- **[システム構成図・技術スタック定義](./system-architecture.md)**: システム構成、技術スタック、環境変数、ボリューム設計
- **[ミドルウェア選定書](./middleware-selection.md)**: 使用技術の選定理由
- **[基本設計書](./basic-design.md)**: システムの基本設計
- **[詳細設計書](./detailed-design.md)**: モジュール仕様、関数仕様、テーブル仕様
- **[内部設計・ディレクトリ構造](./requirements.md#12-付録システム構成詳細)**: ディレクトリ構造（要件定義書内）

### 機能仕様

- **[コマンド・機能仕様書](./command-specification.md)**: スラッシュコマンド、機能一覧
- **[イベント処理仕様書](./event-specification.md)**: Discord イベント、カスタムイベント、バックグラウンドタスク
- **[ユースケース記述](./use-cases.md)**: ユースケースの詳細記述

### データベース設計

- **[ER 図・テーブル定義・永続化戦略](./database-design.md)**: データベース設計、永続化戦略

### API 仕様

- **[外部インターフェース仕様書・API 仕様書](./api-specification.md)**: Discord API、Gemini API、内部 API

### 実装関連

- **[実装検討事項詳細](./implementation-considerations.md)**: 実装前に検討すべき技術的な詳細事項

### デプロイメント・運用

- **[デプロイメント・運用フロー](./deployment-operations.md)**: デプロイメント手順、運用フロー、トラブルシューティング

### テスト

- **[テスト計画書](./test-plan.md)**: テスト計画、テスト戦略
- **[テスト仕様書](./test-specification.md)**: テスト仕様、テストケース

---

## ドキュメントの読み方

### 開発開始時

1. **[要件定義書](./requirements.md)**: プロジェクトの全体像を把握
2. **[実装ロードマップ](./implementation-roadmap.md)**: 段階的な実装計画を確認 ⭐ **重要**
3. **[実装検討事項詳細](./implementation-considerations.md)**: 実装上の注意点を確認
4. **[WBS](./wbs.md)**: 作業項目を確認

### 設計時

1. **[基本設計書](./basic-design.md)**: システムの基本設計を確認
2. **[詳細設計書](./detailed-design.md)**: モジュール・関数の詳細を確認
3. **[API 仕様書](./api-specification.md)**: API の仕様を確認

### 実装時

1. **[コマンド・機能仕様書](./command-specification.md)**: 実装する機能の仕様を確認
2. **[イベント処理仕様書](./event-specification.md)**: イベント処理の仕様を確認
3. **[データベース設計](./database-design.md)**: データベースの設計を確認

### テスト時

1. **[テスト計画書](./test-plan.md)**: テスト計画を確認
2. **[テスト仕様書](./test-specification.md)**: テストケースを確認

### デプロイ時

1. **[デプロイメント・運用フロー](./deployment-operations.md)**: デプロイメント手順を確認
2. **[システム構成図](./system-architecture.md)**: システム構成を確認

---

## ドキュメントの更新

ドキュメントは随時更新されます。最新の情報については、各ドキュメントの「最終更新日」を確認してください。

---

**作成日**: 2024 年
**最終更新日**: 2024 年
**バージョン**: 1.0
**作成者**: kotonoha-bot 開発チーム
