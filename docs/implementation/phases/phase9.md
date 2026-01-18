# Phase 8+ 実装計画とロードマップ

Kotonoha Discord Bot の Phase 8（完全リファクタリング）の実装計画と Phase 9 以降のロードマップ

**作成日**: 2026年1月17日  
**バージョン**: 1.0  
**作成者**: kotonoha-bot 開発チーム

---

## 目次

1. [実装サマリー](#実装サマリー)
2. [Phase 8 の目標](#phase-8-の目標)
3. [前提条件](#前提条件)
4. [現状分析](#現状分析)
5. [リファクタリング方針](#リファクタリング方針)
6. [新しいフォルダ構造](#新しいフォルダ構造)
7. [実装ステップ](#実装ステップ)
8. [完了基準](#完了基準)
9. [リスク管理](#リスク管理)
10. [結論](#結論)

---

## 実装サマリー

Phase 8 では、コードベースの品質向上と技術的負債の解消を実現するため、最適な構造にリファクタリングします。

**主な改善点**:

- ✅ レイヤードアーキテクチャの明確化
- ✅ 依存性注入の改善
- ✅ 設定管理の階層化と分離
- ✅ エラーハンドリングの統一
- ✅ ログ設定の分離
- ✅ 巨大ファイルの分割（handlers.py 833 行 → 複数モジュールに分割）
- ✅ 型安全性の向上
- ✅ テストの充実
- ✅ フォルダ構造の最適化
- ✅ 重複コードの削除（日付フォーマット、プロンプト読み込み、エラーメッセージ）

**実装期間**: 約 10-15 日

---

## Phase 8 の目標

### 完全リファクタリングの目的

**目標**: コードベースの品質向上と技術的負債の解消を実現する

**達成すべきこと**:

1. **コード構造の整理**: モジュール構造の最適化、循環参照の解消、責務の明確化
2. **アーキテクチャの改善**: 設計パターンの適用、依存性注入の改善、エラーハンドリングの統一
3. **パフォーマンス最適化**: データベースクエリの最適化、メモリ使用量の最適化、非同期処理の最適化
4. **コード品質の向上**: 型ヒントの完全化、ドキュメントの充実、コードスタイルの統一
5. **テストの充実**: テストカバレッジの向上、テストの品質向上
6. **重複コードの削除**: 日付フォーマット、プロンプト読み込み、エラーメッセージの一元管理

**注意**: 機能や要件、使用は一切変更しないこと。リファクタリングのみを実施する。

---

## 前提条件

### 実装前の確認事項

- ✅ **Phase 7（aiosqlite への移行）が完了していること**
- ✅ すべてのテストが通過していること（137 テストケース）
- ✅ 既存の機能が正常に動作していること

### 必要な知識・スキル

- Python 3.14 の型ヒント機能
- 非同期プログラミング（asyncio）
- 設計パターン（依存性注入、ファクトリーパターンなど）
- テスト駆動開発（TDD）の理解
- リファクタリング手法

---

## 現状分析

### 現在の構造の問題点

#### 1. フォルダ構造の問題

**現在の構造**:

```txt
src/kotonoha_bot/
├── main.py                    # エントリーポイント（ログ設定も含む）
├── config.py                  # 設定管理（責務が多すぎる）
├── health.py                  # ヘルスチェック
├── bot/
│   ├── client.py              # Bot クライアント
│   └── handlers.py           # メッセージハンドラー（833行、大きすぎる）
├── ai/
│   ├── provider.py
│   ├── litellm_provider.py
│   └── prompts.py
├── db/
│   └── sqlite.py
├── session/
│   ├── manager.py
│   └── models.py
├── router/
│   └── message_router.py
├── eavesdrop/
│   ├── llm_judge.py
│   └── conversation_buffer.py
├── commands/
│   └── chat.py
├── rate_limit/
│   ├── monitor.py
│   ├── token_bucket.py
│   └── request_queue.py
├── errors/
│   ├── discord_errors.py
│   └── database_errors.py
└── utils/
    ├── message_formatter.py
    └── message_splitter.py
```

**問題点**:

- `handlers.py` が 833 行と大きすぎる（単一責任の原則違反）
- `config.py` がすべての設定を管理（責務が多すぎる）
- `main.py` にログ設定が含まれている（関心の分離違反）
- レイヤーが明確でない（プレゼンテーション層、アプリケーション層、データアクセス層の区別が不明確）
- エラーハンドリングが分散している
- 重複コードが存在（日付フォーマット、プロンプト読み込み）

#### 2. コード品質の問題

- 型ヒントが完全ではない箇所がある
- docstring が不足している箇所がある
- 循環参照の可能性がある
- 依存性注入が不十分（直接インスタンス化が多い）

#### 3. 重複コードの問題

（重大度: 高）

1. **日付フォーマットの重複コード**
   - handlers.py の3箇所で同じ曜日・日付フォーマットロジック

2. **プロンプト読み込み関数の重複**
   - `ai/prompts.py` と `eavesdrop/llm_judge.py` で同一の
     `_load_prompt_from_markdown()` 関数が存在

3. **エラーメッセージの散在**
   - 各ハンドラーで同じエラーレスポンスパターンが散在

---

## リファクタリング方針

### 設計原則

1. **単一責任の原則（SRP）**: 各クラス・モジュールは 1 つの責務のみを持つ
2. **依存性逆転の原則（DIP）**: 抽象に依存し、具象に依存しない
3. **関心の分離（SoC）**: 各レイヤーは独立した責務を持つ
4. **DRY 原則**: 重複コードを削除
5. **KISS 原則**: シンプルに保つ

### アーキテクチャパターン

**レイヤードアーキテクチャ**を採用:

1. **プレゼンテーション層**: Discord イベントの受信・送信
2. **アプリケーション層**: ビジネスロジック
3. **データアクセス層**: データの永続化
4. **インフラストラクチャ層**: 外部サービスとの通信、設定管理、ログ

### 依存性注入

- コンストラクタインジェクションを採用
- インターフェース（プロトコル）を定義して抽象化
- ファクトリーパターンでインスタンス生成を管理

### 基本方針

- **1ファイルだけのディレクトリは統合する**（router/ → bot/）
- **833行の handlers.py は分割必須**（bot/handlers/ 内で分割）
- **重複コードを統一**（日付、プロンプト読み込み、エラーメッセージ）
- **ディレクトリ増は避ける**（新規ディレクトリ作成は最小限）

---

## 新しいフォルダ構造

### 提案する構造

小規模プロジェクトに適した、シンプルで実用的な構造:

```txt
src/kotonoha_bot/
├── __init__.py
├── main.py                    # エントリーポイント
│
├── core/                      # コア機能
│   ├── __init__.py
│   ├── config.py             # 設定管理（クラスで整理、1ファイル）
│   ├── logging.py            # ログ設定（分離）
│   └── exceptions.py         # カスタム例外クラス
│
├── bot/                       # Discord Bot 関連
│   ├── __init__.py
│   ├── client.py            # Bot クライアント
│   ├── router.py             # メッセージルーター（router/message_router.py から移動）
│   ├── handlers/             # イベントハンドラー（分割）
│   │   ├── __init__.py
│   │   ├── base.py          # 基底ハンドラー
│   │   ├── mention.py       # メンション応答型
│   │   ├── thread.py        # スレッド型
│   │   └── eavesdrop.py     # 聞き耳型
│   └── commands/            # スラッシュコマンド
│       ├── __init__.py
│       └── chat.py
│
├── services/                 # サービス層（ビジネスロジック）
│   ├── __init__.py
│   ├── session.py           # セッション管理
│   ├── ai.py                # AI サービス
│   └── conversation.py      # 会話管理
│
├── data/                     # データアクセス
│   ├── __init__.py
│   ├── database.py          # データベース操作
│   └── models.py            # データモデル（Session, Message）
│
├── features/                 # 機能別モジュール
│   ├── __init__.py
│   ├── rate_limit/          # レート制限
│   │   ├── __init__.py
│   │   ├── monitor.py
│   │   ├── token_bucket.py
│   │   └── request_queue.py
│   ├── eavesdrop/           # 聞き耳型
│   │   ├── __init__.py
│   │   ├── judge.py         # llm_judge.py からリネーム
│   │   └── buffer.py        # conversation_buffer.py からリネーム
│   └── errors/              # エラーハンドリング（統一）
│       ├── __init__.py
│       ├── messages.py      # エラーメッセージ定義（一元管理）【新規】
│       ├── discord.py       # Discord エラー分類
│       └── database.py      # データベースエラー分類
│
├── external/                 # 外部サービス
│   ├── __init__.py
│   ├── ai/                  # AI プロバイダー
│   │   ├── __init__.py
│   │   ├── provider.py     # インターフェース
│   │   ├── litellm.py       # LiteLLM 実装（litellm_provider.py からリネーム）
│   │   └── prompts.py       # プロンプト管理
│   └── health.py            # ヘルスチェック
│
└── utils/                    # ユーティリティ
    ├── __init__.py
    ├── message.py           # メッセージ関連（formatter, splitter を統合）
    └── datetime.py          # 日時ユーティリティ（新規）【新規】
```

### 主な変更点

1. **レイヤーの簡略化**: `bot/`, `services/`, `data/`, `features/`, `external/`,
   `core/` の 6 層
2. **handlers.py の分割**: 833 行 → `mention.py`, `thread.py`, `eavesdrop.py`
   に分割（必須）
3. **設定管理の整理**: `config.py` → `core/config.py` に移動、クラスで整理（1 ファイル）
4. **ログ設定の分離**: `main.py` から `core/logging.py` に分離
5. **エラーハンドリングの統一**: `errors/` → `features/errors/` に移動、`messages.py` で一元管理
6. **重複コードの削除**:
   - `utils/datetime.py` で日付フォーマットを統一
   - `external/ai/prompts.py` の `_load_prompt_from_markdown()` を公開関数化
   - `features/errors/messages.py` でエラーメッセージを一元管理
7. **router/ の統合**: `router/message_router.py` → `bot/router.py` に移動

### ファイル数の比較

| 項目                   | 現在                | リファクタリング後        |
| ---------------------- | ------------------- | ------------------------- |
| **総ファイル数**       | 約 30               | 約 35 (+5)                |
| **ディレクトリ数**     | 約 10               | 約 7 (-3)                 |
| **handlers.py 分割**   | 1 ファイル (833 行) | 4 ファイル                |
| **設定管理**           | 1 ファイル          | 1 ファイル                |
| **エラーハンドリング** | 2 ファイル          | 3 ファイル (+messages.py) |
| **重複コード削除**     | 6+ 箇所             | 0 箇所                    |

**この案の特徴**:

- ファイル数の増加が最小限（+5 ファイルのみ）
- ディレクトリ数の削減（-3 ディレクトリ）
- 実装期間が短い（10-15 日）
- 小規模プロジェクトに適している
- 保守しやすい
- 過度な抽象化を避け、実用的
- 重複コードを完全に削除

### 詳細設計

#### utils/datetime.py

```python
"""日付・時刻ユーティリティ"""

from datetime import datetime

WEEKDAY_NAMES_JA = ["月", "火", "水", "木", "金", "土", "日"]


def format_datetime_for_prompt() -> str:
    """システムプロンプト用の現在日時情報を生成"""
    now = datetime.now()
    return (
        f"\n\n【現在の日付情報】\n"
        f"現在の日時: {now.strftime('%Y年%m月%d日 %H:%M:%S')}\n"
        f"今日の曜日: {WEEKDAY_NAMES_JA[now.weekday()]}曜日\n"
        f"日付や曜日に関する質問には、この情報を基に具体的に回答してください。"
        f"プレースホルダー（[明日の曜日]など）は使用せず、実際の日付や曜日を回答してください。"
    )
```

#### features/errors/messages.py

```python
"""ユーザー向けメッセージ定義（一元管理）"""


class ErrorMessages:
    """エラーメッセージ"""

    # 汎用
    GENERIC = (
        "すみません。一時的に反応できませんでした。\n"
        "少し時間をおいて、もう一度試してみてください。"
    )

    # Discord API
    PERMISSION = "すみません。必要な権限がありません。\nサーバー管理者にご確認ください。"
    RATE_LIMIT = "すみません。リクエストが多すぎるため、\nしばらく待ってから再度お試しください。"
    NOT_FOUND = "すみません。リソースが見つかりませんでした。"
    DISCORD_SERVER = "すみません。Discord サーバーで問題が発生しています。\nしばらく待ってから再度お試しください。"

    # データベース
    DB_LOCKED = "すみません。データベースが一時的に使用中です。\nしばらく待ってから再度お試しください。"
    DB_ERROR = "すみません。データベースで問題が発生しました。\n少し時間をおいて、もう一度試してみてください。"


class CommandMessages:
    """コマンド応答メッセージ"""

    RESET_SUCCESS = "会話履歴をリセットしました。\n新しい会話として始めましょう。"
    RESET_NOT_FOUND = "会話履歴が見つかりませんでした。"
    RESET_FAILED = "会話履歴のリセットに失敗しました。"
    STATUS_NOT_FOUND = "セッションが見つかりませんでした。"
    STATUS_FAILED = "セッション状態の取得に失敗しました。"

    EAVESDROP_CLEARED = "✅ 会話ログバッファをクリアしました。"
    EAVESDROP_USAGE = (
        "使用方法:\n"
        "`!eavesdrop clear` - 会話ログバッファをクリア\n"
        "`!eavesdrop status` - バッファ状態を表示"
    )


class SessionTypeNames:
    """セッションタイプの日本語表示名"""

    MAPPING = {
        "mention": "メンション応答型",
        "thread": "スレッド型",
        "eavesdrop": "聞き耳型",
        "dm": "DM型",
    }

    @classmethod
    def get(cls, session_type: str) -> str:
        return cls.MAPPING.get(session_type, session_type)
```

#### external/ai/prompts.py の拡張

```python
"""プロンプト管理"""

# _load_prompt_from_markdown() を公開関数化
def load_prompt_from_markdown(file_path: str) -> str:
    """Markdownファイルからプロンプトを読み込む（公開関数）"""
    # 既存の実装をそのまま使用
    ...
```

#### bot/handlers/ の分割

```python
# bot/handlers/base.py
"""基底ハンドラー"""

class BaseHandler:
    """すべてのハンドラーの基底クラス"""
    # 共通処理（エラーハンドリング、ログなど）
    ...

# bot/handlers/mention.py（約150行）
"""メンション応答ハンドラー"""

class MentionHandler(BaseHandler):
    async def handle(self, message): ...
    async def _process(self, message): ...

# bot/handlers/thread.py（約250行）
"""スレッド型ハンドラー"""

class ThreadHandler(BaseHandler):
    async def handle(self, message): ...
    async def _create_thread_and_respond(self, message): ...
    async def _process_thread_message(self, message): ...

# bot/handlers/eavesdrop.py（約100行）
"""聞き耳型ハンドラー"""

class EavesdropHandler(BaseHandler):
    async def handle(self, message): ...
    async def _process(self, message): ...
```

#### 重要な変更: litellm.py の戻り値変更

**Phase 8 のリファクタリング時に実施**:

```python
# external/ai/litellm.py
async def generate_response(
    self,
    messages: list[Message],
    system_prompt: str | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
) -> tuple[str, dict]:
    """応答を生成し、トークン情報も返す
    
    Returns:
        tuple[str, dict]: (応答テキスト, トークン情報)
        トークン情報の形式:
        {
            "input_tokens": int,
            "output_tokens": int,
            "total_tokens": int,
            "model_used": str,
            "latency_ms": int,
        }
    """
    # 既存の実装...
    
    token_info = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "model_used": self._last_used_model,
        "latency_ms": latency_ms,
    }
    return result, token_info
```

**理由**: Phase 9.5（コスト管理）と Phase 11.1（監査ログ）でトークン情報が必要なため、
Phase 8 のリファクタリング時に戻り値を変更します。
Phase 8 は完全リファクタリングなので、後方互換性を保つ必要はありません。

---

## 実装ステップ

### Step 1: コア機能の整理 (1-2 日)

**目標**: 設定管理とログ設定を整理する

**実装内容**:

- [ ] `core/config.py` の作成
  - [ ] `config.py` を移動
  - [ ] クラスで整理（`DiscordConfig`, `LLMConfig`, `DatabaseConfig` など）
  - [ ] 後方互換性のため `Config` クラスで統合
- [ ] `core/logging.py` の作成
  - [ ] `main.py` からログ設定を移動
- [ ] `core/exceptions.py` の作成
  - [ ] カスタム例外クラスの定義
- [ ] `main.py` の更新
  - [ ] インポートパスの更新

**完了基準**:

- [ ] 設定管理が整理されている
- [ ] ログ設定が分離されている
- [ ] 既存の機能が正常に動作する

### Step 2: handlers.py の分割 (2-3 日)

**目標**: 833 行の `handlers.py` を責務ごとに分割する

**実装内容**:

- [ ] `bot/handlers/base.py` の作成
  - [ ] `BaseHandler` クラスの実装（共通処理）
- [ ] `bot/handlers/mention.py` の作成
  - [ ] `MentionHandler` クラスの実装
- [ ] `bot/handlers/thread.py` の作成
  - [ ] `ThreadHandler` クラスの実装
- [ ] `bot/handlers/eavesdrop.py` の作成
  - [ ] `EavesdropHandler` クラスの実装
- [ ] `bot/handlers/__init__.py` の作成
  - [ ] `MessageHandler` クラスの実装（各ハンドラーを統合）
- [ ] `bot/handlers.py` の削除（または空にして再エクスポート）
- [ ] **重要**: `litellm.py` の `generate_response()` の戻り値を `tuple[str, dict]` に変更
- [ ] すべての呼び出し箇所（8箇所）を更新

**完了基準**:

- [ ] `handlers.py` が分割されている
- [ ] 各ハンドラーが単一責任の原則に従っている
- [ ] `litellm.py` の戻り値が `tuple[str, dict]` になっている
- [ ] すべての呼び出し箇所が更新されている
- [ ] 既存の機能が正常に動作する

### Step 3: サービス層の整理 (1-2 日)

**目標**: ビジネスロジックをサービス層に集約する

**実装内容**:

- [ ] `services/session.py` の作成
  - [ ] `SessionService` クラスの実装（`SessionManager` を移動・改善）
- [ ] `services/ai.py` の作成
  - [ ] `AIService` クラスの実装（AI プロバイダーの抽象化）
- [ ] `services/conversation.py` の作成
  - [ ] `ConversationService` クラスの実装（会話管理のビジネスロジック）
- [ ] 既存コードの更新
  - [ ] すべてのインポートパスを更新

**完了基準**:

- [ ] サービス層が整理されている
- [ ] 既存の機能が正常に動作する

### Step 4: データアクセス層の整理 (1 日)

**目標**: データアクセス層を整理する

**実装内容**:

- [ ] `data/database.py` の作成
  - [ ] `SQLiteDatabase` クラスの実装（`db/sqlite.py` から移動）
- [ ] `data/models.py` の作成
  - [ ] `ChatSession`, `Message` クラスの実装（`session/models.py` から移動）
- [ ] 既存コードの更新
  - [ ] すべてのインポートパスを更新

**完了基準**:

- [ ] データアクセス層が整理されている
- [ ] 既存の機能が正常に動作する

### Step 5: 外部サービス層の整理 (1 日)

**目標**: 外部サービス層を整理する

**実装内容**:

- [ ] `external/ai/provider.py` の作成
  - [ ] `AIProvider` インターフェースの実装（`ai/provider.py` から移動）
- [ ] `external/ai/litellm.py` の作成
  - [ ] `LiteLLMProvider` クラスの実装（`ai/litellm_provider.py` から移動）
  - [ ] **重要**: `generate_response()` の戻り値を `tuple[str, dict]` に変更（Step 2 で実施済み）
- [ ] `external/ai/prompts.py` の作成
  - [ ] プロンプト管理の実装（`ai/prompts.py` から移動）
  - [ ] `_load_prompt_from_markdown()` を `load_prompt_from_markdown()` として公開関数化
- [ ] `external/health.py` の作成
  - [ ] ヘルスチェックの実装（`health.py` から移動）
- [ ] `features/eavesdrop/judge.py` の更新
  - [ ] `external/ai/prompts.py` の `load_prompt_from_markdown()` を使用
- [ ] 既存コードの更新
  - [ ] すべてのインポートパスを更新

**完了基準**:

- [ ] 外部サービス層が整理されている
- [ ] プロンプト読み込みの重複が削除されている
- [ ] 既存の機能が正常に動作する

### Step 6: 機能別モジュールの整理 (1-2 日)

**目標**: 機能別モジュールを整理する

**実装内容**:

- [ ] `features/rate_limit/` の移動
  - [ ] `rate_limit/` から移動
- [ ] `features/eavesdrop/` の移動
  - [ ] `eavesdrop/` から移動、ファイル名を改善
- [ ] `features/errors/messages.py` の作成
  - [ ] エラーメッセージの文面を一元管理
- [ ] `features/errors/discord.py` の作成
  - [ ] Discord エラー分類（`errors/discord_errors.py` から移動）
- [ ] `features/errors/database.py` の作成
  - [ ] データベースエラー分類（`errors/database_errors.py` から移動）
- [ ] `bot/router.py` の作成
  - [ ] `router/message_router.py` から移動
- [ ] 既存コードの更新
  - [ ] すべてのインポートパスを更新
  - [ ] エラーメッセージを `features/errors/messages.py` から取得するように変更

**完了基準**:

- [ ] 機能別モジュールが整理されている
- [ ] エラーメッセージが一元管理されている
- [ ] router/ ディレクトリが削除されている
- [ ] 既存の機能が正常に動作する

### Step 7: ユーティリティの整理 (1 日)

**目標**: ユーティリティを整理する

**実装内容**:

- [ ] `utils/message.py` の作成
  - [ ] メッセージフォーマッターと分割機能を統合
- [ ] `utils/datetime.py` の作成
  - [ ] 日付フォーマット関数を実装
- [ ] 既存コードの更新
  - [ ] すべてのインポートパスを更新
  - [ ] handlers.py の3箇所の日付フォーマットを `utils/datetime.py` に置き換え

**完了基準**:

- [ ] ユーティリティが整理されている
- [ ] 日付フォーマットの重複が削除されている
- [ ] 既存の機能が正常に動作する

### Step 8: 型ヒントとドキュメントの充実 (1-2 日)

**目標**: 型ヒントとドキュメントを充実させる

**実装内容**:

- [ ] すべての関数・メソッドに型ヒントを追加
- [ ] すべてのクラス・関数・メソッドに docstring を追加
- [ ] `ty` による型チェックの通過

**完了基準**:

- [ ] 型ヒントが完全化されている
- [ ] ドキュメントが充実している

### Step 9: テストの充実 (1-2 日)

**目標**: テストカバレッジを向上させる

**実装内容**:

- [ ] テストカバレッジの測定
- [ ] 不足しているテストの追加
- [ ] すべてのテストが通過することを確認
- [ ] `litellm.py` の戻り値変更に関するテストを追加

**完了基準**:

- [ ] テストカバレッジが 80% 以上になっている
- [ ] すべてのテストが通過する

**合計期間**: 約 10-15 日

---

## 完了基準

### 必須項目

- [ ] コード構造が整理されている（シンプルなレイヤードアーキテクチャ）
- [ ] アーキテクチャが改善されている（依存性注入の改善）
- [ ] パフォーマンスが最適化されている（データベースクエリ、非同期処理）
- [ ] コード品質が向上している（型ヒント、ドキュメント、スタイル）
- [ ] テストカバレッジが向上している（80% 以上）
- [ ] すべてのテストが通過する（既存の 137 テストケース + 新規テスト）
- [ ] ドキュメントが更新されている
- [ ] 既存の機能が正常に動作する（回帰テスト）
- [ ] 重複コードが削除されている（日付フォーマット、プロンプト読み込み、エラーメッセージ）
- [ ] `litellm.py` の戻り値が `tuple[str, dict]` になっている

### 品質基準

- **型安全性**: `ty` による型チェックが通過する
- **コードスタイル**: `ruff check` が警告なしで通過する
- **テストカバレッジ**: 80% 以上
- **ドキュメント**: すべての公開 API に docstring が存在する

---

**注意**: Phase 9 以降のロードマップについては、[実装ロードマップ](../roadmap.md) を参照してください。

## 技術仕様

### 依存性注入の実装

**コンストラクタインジェクション**を採用:

```python
class SessionService:
    def __init__(
        self,
        repository: ISessionRepository,
        config: SessionConfig,
    ):
        self.repository = repository
        self.config = config
```

### サービス層

**ビジネスロジックをサービス層に集約**:

```python
class SessionService:
    def __init__(
        self,
        database: SQLiteDatabase,
        config: SessionConfig,
    ):
        self.database = database
        self.config = config

    async def get_or_create_session(
        self, session_key: str, session_type: SessionType
    ) -> ChatSession:
        # ビジネスロジック
        ...
```

### litellm.py の戻り値変更

**Phase 8 のリファクタリング時に実施**:

```python
async def generate_response(
    self,
    messages: list[Message],
    system_prompt: str | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
) -> tuple[str, dict]:
    """応答を生成し、トークン情報も返す
    
    Returns:
        tuple[str, dict]: (応答テキスト, トークン情報)
        トークン情報の形式:
        {
            "input_tokens": int,
            "output_tokens": int,
            "total_tokens": int,
            "model_used": str,
            "latency_ms": int,
        }
    """
    # 既存の実装...
    
    token_info = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "model_used": self._last_used_model,
        "latency_ms": latency_ms,
    }
    return result, token_info
```

**理由**: Phase 9.5（コスト管理）と Phase 11.1（監査ログ）でトークン情報が必要なため、
Phase 8 のリファクタリング時に戻り値を変更します。
Phase 8 は完全リファクタリングなので、後方互換性を保つ必要はありません。

---

## リスク管理

### リスクと対策

#### リスク 1: リファクタリングによる既存機能の破壊

**対策**:

- 各ステップで動作確認を実施
- 既存のテストをすべて通過させる
- 段階的なリファクタリング（一度にすべてを変更しない）

#### リスク 2: テストカバレッジの不足による回帰バグ

**対策**:

- テストカバレッジを 80% 以上にする
- 統合テストを追加
- エッジケースのテストを追加

#### リスク 3: パフォーマンス最適化による予期しない副作用

**対策**:

- パフォーマンステストを実施
- ベンチマークを取得
- 段階的な最適化

#### リスク 4: インポートパスの変更による混乱

**対策**:

- 後方互換性のための `__init__.py` で再エクスポート（一時的）
- 段階的な移行（一度にすべてを変更しない）
- 明確な移行ガイドの提供

#### リスク 5: litellm.py の戻り値変更による影響

**対策**:

- Phase 8 の Step 2 で `litellm.py` の戻り値を変更
- すべての呼び出し箇所（8箇所）を同時に更新
- テストを更新して動作確認

---

## 結論

この実装計画は、Phase 8 の完全リファクタリングを実現するための包括的な計画です。

**主な特徴**:

1. **コードベースの品質向上**: レイヤードアーキテクチャの明確化、依存性注入の改善
2. **技術的負債の解消**: 巨大ファイルの分割、重複コードの削除
3. **重複コードの削除**: 日付フォーマット、プロンプト読み込み、エラーメッセージの一元管理
4. **litellm.py の戻り値変更**: Phase 9.5（コスト管理）と Phase 11.1（監査ログ）で必要なトークン情報を取得可能に
5. **将来の拡張性**: Phase 9 以降の機能追加に対応できる構造

**推奨**: この計画に従って Phase 8 を実装し、Phase 9 以降の機能追加に対応する。

**Phase 9 以降のロードマップ**: [実装ロードマップ](../roadmap.md) を参照してください。

---

**更新履歴**:

- v1.0 (2026-01-17): 初版作成
  （phase8_claude.md、phase8_cursor.md、future_features_review.md を統合）
