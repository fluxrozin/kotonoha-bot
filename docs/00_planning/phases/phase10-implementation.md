# Phase 10: 完全リファクタリング - 実装ガイド

Phase 10 の詳細な実装手順、コーディング規約、コード例を記載したドキュメント

**作成日**: 2026年1月19日  
**バージョン**: 2.0  
**対象プロジェクト**: kotonoha-bot v0.9.0  
**前提条件**: Phase 7（aiosqlite 移行）完了済み、Phase 8（PostgreSQL への移行）完了済み、全テスト通過  
**開発体制**: 1人開発（将来的に機能は倍増予定）  
**完了日**: 2026年1月19日  
**ステータス**: ✅ 実装完了

**関連ドキュメント**:

- [Phase 10 基本方針](./phase10.md): リファクタリングの基本方針、目標、概要

**注意**: このドキュメントは詳細な実装手順を記載しています。基本方針や概要については [Phase 10 基本方針](./phase10.md) を先に確認してください。

---

## 目次

1. [エグゼクティブサマリー](#1-エグゼクティブサマリー)
2. [現状分析](#2-現状分析)
3. [コーディング規約](#3-コーディング規約)
4. [リファクタリング方針](#4-リファクタリング方針)
5. [新フォルダ構造](#5-新フォルダ構造)
6. [詳細実装計画](./phase10-implementation-steps.md): 各ステップ（Step 0-7）の詳細な実装手順とコード例
7. [テストコードリファクタリング](./phase10-implementation-testing.md#7-テストコードリファクタリング): テスト構造、完了基準、リスク管理、改善提案

---

## 1. エグゼクティブサマリー

このドキュメントは Phase 10 の詳細な実装手順を記載しています。

**基本方針や概要については [Phase 10 基本方針](./phase10.md) を先に確認してください。**

### 1.1 このドキュメントの内容

- コーディング規約（命名規則、型ヒント、docstring、エラーハンドリングなど）
- pyproject.toml の設定（Astralスタック版: Ruff + ty）
- リファクタリング・ワークフロー（爆速版: ty を使った高速チェック）
- 新フォルダ構造とファイル移動マッピング

**詳細な内容は以下のドキュメントを参照してください：**

- **[詳細実装計画（Step 0-7）](./phase10-implementation-steps.md)**: 各ステップの詳細な実装手順とコード例
- **[テスト・完了基準・リスク管理](./phase10-implementation-testing.md)**: テストコードリファクタリング、完了基準とチェックリスト、リスク管理、改善提案、付録

### 1.2 コードレビューとの関連

この実装計画は、Phase 9 完了後のコードレビューで指摘された改善項目を反映しています：

- **即座に対応すべき項目**: API キーの取得方法の統一（Step 3 に組み込み済み）
- **Phase 10 実装時に注意すべき項目**:
  - 例外のラッピング（抽象化の徹底）→ Step 3 に組み込み済み
  - Config のインスタンス化 → Step 1 に組み込み済み
  - 依存関係の方向性の明確化 → Step 0 に組み込み済み
- **将来の改善項目**:
  - 型ヒントの完全化 → Step 7 に組み込み済み
  - docstring の完全化 → Step 7 に組み込み済み

---

## 2. 現状分析

### 2.1 現在のファイル構造

```text
src/kotonoha_bot/           (3,649行)
├── main.py                 (175行) - エントリーポイント + ログ設定
├── config.py               (116行) - 設定管理
├── health.py               (106行) - ヘルスチェック
├── bot/
│   ├── client.py           (45行)
│   └── handlers.py         (832行) ← 最大の問題
├── ai/
│   ├── provider.py         (30行)
│   ├── anthropic_provider.py (289行)
│   └── prompts.py          (45行)
├── db/
│   └── sqlite.py           (242行)
├── session/
│   ├── manager.py          (131行)
│   └── models.py           (99行)
├── router/
│   └── message_router.py   (165行) ← 1ファイルのみ
├── eavesdrop/
│   ├── llm_judge.py        (557行)
│   └── conversation_buffer.py (60行)
├── commands/
│   └── chat.py             (128行)
├── rate_limit/
│   ├── monitor.py          (82行)
│   ├── token_bucket.py     (93行)
│   └── request_queue.py    (133行)
├── errors/
│   ├── discord_errors.py   (78行)
│   └── database_errors.py  (65行)
└── utils/
    ├── message_formatter.py (29行)
    └── message_splitter.py  (99行)
```

### 2.2 テスト構造

```text
tests/                      (3,193行)
├── conftest.py             (79行)
├── test_basic.py           (62行)
├── unit/                   (17ファイル)
│   ├── test_llm_judge.py   (453行) ← 最大
│   ├── test_thread_handler.py (373行)
│   ├── test_handlers_embed.py (325行)
│   └── ... (14ファイル)
├── integration/            (空)
└── performance/            (空)
```

### 2.3 重複コード詳細

#### 2.3.1 日付フォーマット（3箇所）

**場所**: `handlers.py` 183-192行, 453-460行, 554-560行

```python
# 同一パターンが3回出現
now = datetime.now()
weekday_names = ["月", "火", "水", "木", "金", "土", "日"]
current_date_info = (
    f"\n\n【現在の日付情報】\n"
    f"現在の日時: {now.strftime('%Y年%m月%d日 %H:%M:%S')}\n"
    f"今日の曜日: {weekday_names[now.weekday()]}曜日\n"
    ...
)
```

#### 2.3.2 プロンプト読み込み関数（2箇所）

**場所**: `ai/prompts.py:9-41`, `eavesdrop/llm_judge.py:19-51`

完全に同一の `_load_prompt_from_markdown()` 関数が存在。

#### 2.3.3 エラーメッセージ（10箇所以上）

**場所**: `handlers.py` 249-252行, 305-307行, 392-395行, 402-405行,
410-413行, 418-421行, 511-514行, 623-626行

```python
# 同一メッセージが複数箇所に散在
"すみません。一時的に反応できませんでした。\n"
"少し時間をおいて、もう一度試してみてください。"
```

#### 2.3.4 レスポンス送信パターン（4箇所）

**場所**: `handlers.py` 211-232行, 479-500行, 583-599行, 708-729行

```python
# 同一パターンが4回出現
response_chunks = split_message(response_text)
formatted_chunks = format_split_messages(response_chunks, len(response_chunks))
model_name = self.ai_provider.get_last_used_model()
rate_limit_usage = self.ai_provider.get_rate_limit_usage()
if formatted_chunks:
    embed = create_response_embed(formatted_chunks[0], model_name, rate_limit_usage)
    await channel.send(embed=embed)
    for chunk in formatted_chunks[1:]:
        await channel.send(chunk)
        await asyncio.sleep(0.5)
```

---

## 3. コーディング規約

### 3.1 基本規約

| 項目 | 規約 |
|------|------|
| Python バージョン | 3.14+ |
| 行長制限 | 88文字（ruff デフォルト） |
| インデント | スペース4つ |
| 文字コード | UTF-8 |
| 改行コード | LF |

### 3.2 命名規則

| 対象 | 規則 | 例 |
|------|------|-----|
| モジュール | snake_case | `message_handler.py` |
| クラス | PascalCase | `MessageHandler` |
| 関数/メソッド | snake_case | `handle_message()` |
| 定数 | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT` |
| プライベート | 先頭アンダースコア | `_internal_method()` |
| 型変数 | 大文字1文字または説明的な名前 | `T`, `MessageType` |

### 3.3 型ヒント規約（Modern Python Style）

**基本ルール**: Python 3.10以降のモダン記法を使用する。古い `typing.List` や `typing.Union` は使用しない。

#### 3.3.1 基本記法

```python
# ✅ 推奨: Python 3.14+ スタイル
def process(items: list[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    return result

# ✅ 推奨: Union は | を使用
def get_value(key: str) -> str | None:
    return None

# ✅ 推奨: Optional は | None を使用
def find_user(id: int) -> User | None:
    return None

# ✅ 推奨: クラス属性にも型ヒント
class Handler:
    sessions: dict[str, Session]
    _cache: list[Message] | None = None

# ❌ 非推奨: typing モジュールの旧型
from typing import List, Dict, Optional, Union  # 使用しない
def process(items: List[str]) -> Dict[str, int]:  # ❌ 古い書き方
    pass
```

#### 3.3.2 型の対応表

| 古い書き方（3.9以前） | 新しい書き方（3.10+） |
|---------------------|---------------------|
| `Union[str, int]` | `str | int` |
| `Optional[str]` | `str | None` |
| `List[str]` | `list[str]` |
| `Dict[str, int]` | `dict[str, int]` |
| `Tuple[str, int]` | `tuple[str, int]` |
| `Set[str]` | `set[str]` |
| `"MyClass"` (文字列) | `Self` (from typing import Self) |

#### 3.3.3 循環参照の回避（TYPE_CHECKING）

リファクタリングでファイルを分割すると、型ヒントのために import しただけで循環参照エラーになることが多発します。これを防ぐために `TYPE_CHECKING` を使用する。

```python
from typing import TYPE_CHECKING, Self

# 実行時にはインポートしない（循環参照回避）
if TYPE_CHECKING:
    from .session import SessionManager
    from .ai import AnthropicProvider

class MentionHandler:
    """メンション応答ハンドラー"""
    
    def __init__(
        self,
        session_manager: "SessionManager",  # 文字列で指定（TYPE_CHECKING ブロック内の型）
        ai_provider: "AnthropicProvider"    # 文字列で指定
    ):
        self.session_manager = session_manager
        self.ai_provider = ai_provider

class Builder:
    """ビルダークラス"""
    
    def set_config(self, value: int) -> Self:  # 自身のインスタンスを返す場合
        """設定を追加して自身を返す"""
        self.config = value
        return self
```

**重要**: Python 3.14 では `from __future__ import annotations` を使うか、文字列で型を指定することで循環参照を回避できる。

#### 3.3.4 具体的な適用例

```python
from typing import Self, TYPE_CHECKING

# ❌ 古い書き方（3.9以前）
# from typing import List, Dict, Optional, Union
# def process(items: List[str], option: Optional[int] = None) -> Dict[str, Union[int, str]]: ...

# ✅ 新しい書き方（3.10+ / 3.14）
def process(items: list[str], option: int | None = None) -> dict[str, int | str]:
    """アイテムを処理する
    
    Args:
        items: 処理するアイテムのリスト
        option: オプション値（省略可）
    
    Returns:
        処理結果の辞書
    """
    return {"count": 1}

class Builder:
    """ビルダークラス"""
    
    def set_config(self, value: int) -> Self:
        """設定を追加して自身を返す"""
        self.config = value
        return self
```

### 3.4 docstring 規約（Google Style）

**基本ルール**: **Google Style** を使用する。可読性が高く、ツール（VS Code, PyCharm, LLM）との相性が良い。

#### 3.4.1 Google Style の構成要素

1. **要約（Summary）**: 1行で何をするか書く。行の最後は半角ピリオドで終わること。
2. **詳細（Description）**: 必要なら詳細な挙動や注意点を書く
3. **Args**: 引数の名前、型（省略可）、説明
4. **Returns**: 戻り値の型（省略可）、説明
5. **Raises**: 発生しうる例外とその条件

#### 3.4.2 テンプレート

```python
def generate_response(
    self,
    messages: list[dict[str, str]],
    temperature: float = 0.7,
) -> tuple[str, TokenInfo]:
    """AIプロバイダーを使用して応答を生成する。

    会話履歴を受け取り、設定されたモデル（Claude等）に問い合わせを行う。
    レート制限時は自動的にリトライを行う。

    Args:
        messages: OpenAI形式のメッセージリスト [{"role": "user", "content": "..."}]
        temperature: 生成のランダム性 (0.0 - 1.0)。デフォルトは 0.7。

    Returns:
        生成された応答テキストと、トークン使用情報(TokenInfo)のタプル。

    Raises:
        AIAuthenticationError: APIキーが無効な場合
        AIRateLimitError: リトライ上限を超えてレート制限にかかった場合
    """
    # 実装...
```

#### 3.4.3 重要なポイント

1. **嘘を書かない**: 実装と食い違っているDocstringはバグよりタチが悪い
2. **Raises を重視**: 呼び出し元が try-except を書くために必須の情報。Phase 9で例外をラッピングしたのは、ここに書くためでもある
3. **型情報の記載**: Args と Returns に型を記載する場合は、関数シグネチャの型ヒントと一致させる

#### 3.4.4 クラスのdocstring例

```python
class AnthropicProvider(AIProvider):
    """Anthropic SDK を使用した LLM プロバイダー。

    Anthropic SDK を直接使用して Claude API を呼び出す。
    - 開発: claude-haiku-4-5（超低コスト）
    - 本番: claude-opus-4-5（最高品質）

    Attributes:
        model: 使用するモデル名
        client: Anthropic SDK クライアント
        rate_limit_monitor: レート制限モニター
    """
    
    def __init__(self, model: str = Config.LLM_MODEL):
        """AnthropicProvider を初期化する。

        Args:
            model: 使用するモデル名（省略時は Config.LLM_MODEL）

        Raises:
            ValueError: ANTHROPIC_API_KEY が設定されていない場合
        """
        # 実装...
```

#### 3.4.5 プライベートメソッドのdocstring

プライベートメソッド（`_` で始まる）にも docstring を追加する（複雑なロジックの場合）。

```python
def _convert_model_name(self, model: str) -> str:
    """LiteLLM のモデル名を Anthropic SDK のモデル名に変換。

    Args:
        model: LiteLLM 形式のモデル名（例: "anthropic/claude-haiku-4-5"）

    Returns:
        Anthropic SDK 形式のモデル名（例: "claude-haiku-4-5"）
    """
    # 実装...
```

### 3.5 インポート規約

```python
# 標準ライブラリ（アルファベット順）
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path

# サードパーティ（アルファベット順）
import discord
from anthropic import Anthropic
from discord.ext import tasks

# ローカル（相対インポート、アルファベット順）
from ..config import Config
from ..errors.messages import ErrorMessages
from .base import BaseHandler
```

### 3.6 エラーハンドリング規約

**重要**: 抽象化の徹底 - Handler層（プレゼンテーション層）は具体的なライブラリの例外を知らないようにする

```python
# ✅ 推奨: services/ai.py で例外をラッピング
# services/ai.py 内部
try:
    response = client.messages.create(...)
except anthropic.AuthenticationError:
    raise errors.ai.AIAuthenticationError("API認証に失敗しました")
except anthropic.RateLimitError as e:
    raise errors.ai.AIRateLimitError(f"レート制限: {e}")

# ✅ 推奨: Handler層では独自例外のみをキャッチ
# bot/handlers.py
try:
    await self.ai_provider.generate_response(messages)
except errors.ai.AIAuthenticationError:
    logger.error("Authentication failed")
    raise
except errors.ai.AIRateLimitError as e:
    logger.warning(f"Rate limited: {e}")
    await self._handle_rate_limit()

# ❌ 非推奨: Handler層で Anthropic SDK の例外を直接キャッチ（抽象化の漏れ）
try:
    await self.ai_provider.generate_response(messages)
except anthropic.AuthenticationError:  # 具体的なライブラリの例外を知っている
    logger.error("Authentication failed")
    raise
```

**理由**: 将来AIライブラリを変更する際に、Handler層の修正が不要になる。`kotonoha_bot.errors` の例外だけを知っていれば良い。

### 3.7 ログ規約

**基本方針**: Phase 10 では標準の `logging` モジュールを使用します。`structlog` への完全移行は Phase 11 以降で検討します。

```python
# モジュールレベルでロガーを取得
import logging
logger = logging.getLogger(__name__)

# ログレベルの使い分け
logger.debug("Internal state: %s", state)      # 開発用詳細情報
logger.info("Session created: %s", session_id) # 通常の操作情報
logger.warning("Retry attempt %d", attempt)     # 注意が必要な状況
logger.error("Failed to connect: %s", error)    # エラー（回復可能）
logger.exception("Unexpected error")            # エラー（スタックトレース付き）
```

**注**: `structlog` は `pyproject.toml` に含まれていますが、Phase 10 では使用しません。Phase 11 以降で構造化ログへの移行を検討します。

### 3.8 非同期規約

```python
# ✅ 推奨: async/await を一貫して使用
async def process_message(self, message: discord.Message) -> None:
    async with message.channel.typing():
        response = await self.generate_response(message)
        await self.send_response(message.channel, response)

# ✅ 推奨: 並行実行可能な場合は gather
results = await asyncio.gather(
    self.save_session(session_key),
    self.update_metrics(session_key),
)

# ❌ 非推奨: 同期的なスリープ
import time
time.sleep(1)  # イベントループをブロック

# ✅ 推奨: 非同期スリープ
await asyncio.sleep(1)
```

### 3.9 pyproject.toml の設定（Astralスタック版）

**基本方針**: mypy の設定はすべて削除し、`[tool.ty]` に置き換える。ty は ruff と同じ設計思想で作られているため、設定も非常に似ている。

#### 3.9.1 Linter & Formatter (Ruff) - Docstring強制用

```toml
[tool.ruff]
target-version = "py314"
line-length = 88
src = ["src"]

[tool.ruff.lint]
# D: Docstring (pydocstyle)
# I: Import order (isort)
# E, F: 基本エラー
# UP: 最新構文へアップグレード
# B: flake8-bugbear
# C4: flake8-comprehensions
# ARG: flake8-unused-arguments
# SIM: flake8-simplify
select = ["E", "F", "D", "I", "UP", "B", "C4", "ARG", "SIM"]
ignore = [
    "E501",   # line too long (handled by formatter)
]

[tool.ruff.lint.pydocstyle]
convention = "google"  # Google Style を強制

[tool.ruff.lint.isort]
known-first-party = ["kotonoha_bot"]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["D"]  # テストファイルは docstring チェックをスキップ
"__init__.py" = ["D104"]  # __init__.py の空の docstring を許可
```

#### 3.9.2 Type Checker (ty) - Strict設定

```toml
[tool.ty]
# Pythonバージョンの指定（プロジェクト設定から自動取得される場合もありますが明示推奨）
python-version = "3.14"

# 型チェックの厳格さ設定
# ty はデフォルトでかなり厳格ですが、明示的に有効化できるルールがあれば記述します
# (執筆時点のtyの仕様に合わせて調整してください。以下はRuffライクな想定設定です)
# select = ["ALL"]  # 可能な限り全てのチェックを有効化

# mypyの disallow_untyped_defs に相当
# ty ではデフォルトで型のない関数を警告するか、設定で強制します
# (tyのドキュメントに従い "missing-return-type" などのルールをエラーにする)

# 外部ライブラリの型が見つからない場合の挙動
# ignore-missing-imports = true に相当する設定
```

**補足**: ty は開発スピードが早いため、フラグ名が変わっている可能性があります。基本的には `uv run ty check` だけで妥当なデフォルト値で動きますが、より厳しくしたい場合はドキュメント（`uv run ty --help`）の "Strict" モードやルール設定を参照してください。

#### 3.9.4 ty (Type Checker) の運用リスク回避

**背景**: 2026年時点の設定とはいえ、ty が厳格すぎる、あるいは誤検知する場合のリスクヘッジが必要。

**対策 1: Fallbackの用意**

万が一 ty の挙動が怪しい場合に備え、`basedpyright` (Microsoftのpyrightの強化版) も念頭に置いておくと安心です。

```toml
# pyproject.toml（オプション: ty に問題がある場合の Fallback）
[project.optional-dependencies]
type-checking-fallback = ["basedpyright>=1.9.0"]

# basedpyright の設定例（ty の代替として使用する場合）
[tool.basedpyright]
pythonVersion = "3.14"
reportMissingTypeStubs = false
reportUnusedImport = true
```

**使用方法**:

```bash
# ty でチェック（通常時）
uv run ty check src/

# 万が一 ty に問題がある場合、basedpyright で確認
uv run basedpyright src/
```

**対策 2: CIでの二重チェック（オプション）**

ローカルでは爆速の ty を使い、GitHub Actions等では念のため mypy か basedpyright も走らせる構成も（移行初期は）アリです。

```yaml
# .github/workflows/ci.yml（例）
- name: Type Check (ty)
  run: uv run ty check src/

- name: Type Check (basedpyright) - Fallback
  run: |
    uv pip install basedpyright
    uv run basedpyright src/ || echo "basedpyright check failed (non-blocking)"
  continue-on-error: true  # ty が通れば警告のみ
```

**注意**: 1人開発なら ty 一本心中でも修正コストは低いので許容範囲です。CIでの二重チェックは、チーム開発や本番環境への影響が大きい場合に推奨されます。

#### 3.9.3 リファクタリング・ワークフロー（爆速版）

ty を使う最大のメリットは、その圧倒的な速度です。mypy で数秒〜数十秒待たされていた時間が、ty なら一瞬で終わります。

この特性を活かし、Phase 10 では以下のループを回してください。

**手順 A: ファイルを分割・移動する**

- `handlers.py` を分割したり、`services/` に移動します。

**手順 B: 瞬時にチェックする**

- コマンド一発で、Linter (Ruff) と Type Checker (ty) を走らせます。

```bash
# ワンライナーで全チェック（これをエイリアス登録推奨）
uv run ruff check src/ && uv run ty check src/
```

- Ruff が Docstring の不足やインポート順序を指摘します。
- ty が型の不整合やインポートエラーを指摘します。

**手順 C: エラーを潰す**

- ty のエラーメッセージは Rust コンパイラのように親切（"Did you mean...?" や詳細な場所が出る）なので、それに従って修正します。
- 型がわからない場合: ty は推論が強力ですが、明示が必要な場合は `var: int = 1` のように書きます。
- 循環参照: mypy と同様、`from typing import TYPE_CHECKING` は有効です。

**推奨エイリアス**:

```bash
# ~/.bashrc または ~/.zshrc に追加
alias check="uv run ruff check src/ && uv run ty check src/"
alias check-fix="uv run ruff check src/ --fix && uv run ty check src/"
```

---

## 4. リファクタリング方針

### 4.1 設計原則

1. **単一責任の原則 (SRP)**: 各クラス・モジュールは1つの責務のみを持つ
2. **依存性逆転の原則 (DIP)**: 抽象に依存し、具象に依存しない
3. **関心の分離 (SoC)**: 各レイヤーは独立した責務を持つ
4. **DRY 原則**: 重複コードを排除
5. **KISS 原則**: シンプルさを維持
6. **テストによる設計の汚染の排除**: 本番コードは「テストされていること」を知らなくていい

### 4.1.1 テストによる設計の汚染（Test-Induced Design Damage）の解消

**基本方針**: 本番コードの中に `if is_test_mode:` のような記述がゼロであること。

**よくあるパターンと解決策**:

#### パターン1: フラグ分岐（`if testing:`）

**悪い例**:

```python
# テスト時だけ外部APIを呼びたくない、DB書き込みをしたくない
def process_data(self):
    data = self.calculate()
    if not self.is_testing:  # ← これを消したい
        self.api.send(data)
```

**解決策**: 依存性の注入（DIパターン）

```python
# 良い例（本番コード）
class DataProcessor:
    def __init__(self, api_client):
        self.api_client = api_client  # 本番はRealClient、テストはMockClientが入る

    def process_data(self):
        data = self.calculate()
        self.api_client.send(data)  # フラグ不要。何が入っていてもsendを呼ぶだけ

# テストコード側
processor = DataProcessor(api_client=MockClient())
```

#### パターン2: privateメソッドの公開・アクセス

**悪い例**: テストしたいロジックが `_private_method` にあるため、無理やり `obj._private_method()` を呼んでいる、あるいはテストのために public に変更している。

**解決策**: ロジックの移動（Extract Class）

- privateメソッドをテストしたくなるのは、**「そのクラスが責任を持ちすぎている」**サイン
- そのロジックを別のクラス（またはユーティリティ関数）として切り出し、それを公開APIとしてテストする

**例**:

- Before: `Handler` クラスの中に複雑な `_parse_date()` があり、テストでそれを呼んでいる
- After: `utils/datetime.py` を作り、そこに `parse_date()` を移動。テストはその utils を堂々とテストする

#### パターン3: テスト用データの混入

**悪い例**:

```python
# 本番では絶対に使わないパラメータがある
class User:
    def __init__(self, id, name, force_admin_for_test=False):  # ← これ
        ...
```

**解決策**: Factoryパターンの利用

- 本番コードのコンストラクタはきれいに保ち、テストデータを作るための専用の工場（Factory）側で都合の良いデータを作って渡す
- 今回の計画にある `SessionFactory` がこれに当たる

#### パターン4: 時刻依存の排除

**悪い例**: 「現在時刻」に依存するテストのために `datetime.now()` をいじっている箇所がある

**解決策**:

- 引数で時刻を受け取るようにする
- `freezegun` などのライブラリに任せてコードからは削除する

**検索して駆逐する**:

リファクタリング作業中、以下のルールでコードを移行する:

1. **テスト汚染コードの検出**:

   ```bash
   # src/ 以下の全文検索
   grep -r "test\|mock\|debug\|dummy" src/ --include="*.py"
   ```

   - ヒットした箇所が「ロジック分岐」に使われていたら、DI（構成要素の差し替え）で解決できないか考える

2. **Configクラスを活用**:
   - 「タイムアウト時間を短くしたい」などの定数変更であれば、コードに書かず Config オブジェクト経由にする
   - `await asyncio.sleep(config.RETRY_DELAY)` としておけば、テスト時だけ `RETRY_DELAY = 0` の Config を渡せば待ち時間をゼロにできる

3. **どうしても残る場合の「妥協案」**:
   - 型ヒントで明示: どうしてもテスト用の引数が必要なら、docstringやコメントに `Use for testing only` と明記する
   - Protectedにする: 名前を `_` で始め、外部からは見えないことにしておく（Pythonでは慣習）

**結論**: 「テストコードのために本番コードを汚さない。代わりに、本番コードを『部品交換可能（疎結合）』にする」

これが今回のリファクタリング（特にDIの導入）で自然と達成できるはずです。過去の「継ぎ足しコード」を見つけたら、「これは Phase 10 で導入する DI (`setup_handlers`) か Config か Factory のどれで解決できるか？」と当てはめてみてください。ほぼ全て解決できるはずです。

### 4.2 アーキテクチャレイヤー

```text
┌─────────────────────────────────────────────────────────┐
│  Presentation Layer (bot/)                              │
│  - Discord イベントの受信・送信                          │
│  - ハンドラー、コマンド                                  │
├─────────────────────────────────────────────────────────┤
│  Application Layer (services/)                          │
│  - ビジネスロジック                                      │
│  - セッション管理、AI サービス                           │
├─────────────────────────────────────────────────────────┤
│  Domain Layer (db/)                                     │
│  - データモデル、リポジトリ                              │
├─────────────────────────────────────────────────────────┤
│  Infrastructure Layer (config.py, external/, features/) │
│  - 設定、ログ、外部サービス、機能モジュール              │
└─────────────────────────────────────────────────────────┘
```

### 4.3 依存性注入パターン

```python
# コンストラクタインジェクション
class MentionHandler(BaseHandler):
    def __init__(
        self,
        session_manager: SessionManager,
        ai_provider: AIProvider,
        response_sender: ResponseSender,
    ):
        self.session_manager = session_manager
        self.ai_provider = ai_provider
        self.response_sender = response_sender
```

---

## 5. 新フォルダ構造

**1人開発に適したフラットな構造**（ディレクトリ深度: 最大2階層）

```text
kotonoha-bot/
├── src/kotonoha_bot/        # ソースコード
│   ├── __init__.py
│   ├── main.py              # エントリーポイント
│   ├── config.py            # 設定管理（ログ設定も含む）
│   ├── health.py            # ヘルスチェック
│   │
│   ├── bot/                 # Discord Bot（プレゼンテーション層）
│   │   ├── __init__.py
│   │   ├── client.py        # KotonohaBot クラス
│   │   ├── router.py        # MessageRouter（router/から移動）
│   │   ├── handlers/        # ハンドラーパッケージ（handlers.py から物理分割）
│   │   │   ├── __init__.py  # MessageHandler（Facade）
│   │   │   ├── mention.py   # MentionHandler
│   │   │   ├── thread.py    # ThreadHandler
│   │   │   └── eavesdrop.py # EavesdropHandler
│   │   └── commands.py      # スラッシュコマンド（commands/chat.py から）
│   │
│   ├── services/            # ビジネスロジック
│   │   ├── __init__.py
│   │   ├── session.py       # SessionManager（session/から移動）
│   │   ├── ai.py            # AnthropicProvider（ai/から移動）
│   │   └── eavesdrop.py    # LLMJudge + ConversationBuffer 統合
│   │
│   ├── db/                  # データ層（そのまま維持）
│   │   ├── __init__.py
│   │   ├── sqlite.py
│   │   └── models.py        # session/models.py から移動
│   │
│   ├── errors/              # エラー処理（そのまま維持 + 追加）
│   │   ├── __init__.py
│   │   ├── messages.py      # 【新規】エラーメッセージ一元管理
│   │   ├── ai.py            # 【新規】AI関連の例外（抽象化の徹底）
│   │   ├── discord.py       # discord_errors.py からリネーム
│   │   └── database.py      # database_errors.py からリネーム
│   │
│   ├── rate_limit/          # レート制限（そのまま維持）
│   │   ├── __init__.py
│   │   ├── monitor.py
│   │   ├── token_bucket.py
│   │   └── request_queue.py
│   │
│   ├── utils/               # ユーティリティ
│   │   ├── __init__.py
│   │   ├── message.py       # formatter + splitter 統合
│   │   ├── datetime.py      # 【新規】日付フォーマット
│   │   └── prompts.py       # ai/prompts.py から移動
│   │
│   └── prompts/             # プロンプトファイル（Markdown）
│       ├── system.md        # システムプロンプト
│       └── ...              # その他のプロンプトファイル
│
├── tests/                   # テストコード
├── docs/                    # ドキュメント
├── scripts/                 # 運用スクリプト（bash）
├── logs/                    # ログファイル（.gitignore）
└── backups/                 # バックアップ（.gitignore）
```

### 5.2 ファイル移動マッピング

| 現在のパス | 新しいパス | 変更内容 |
|-----------|-----------|----------|
| `router/message_router.py` | `bot/router.py` | 移動 |
| `commands/chat.py` | `bot/commands.py` | 移動+リネーム |
| `session/manager.py` | `services/session.py` | 移動 |
| `session/models.py` | `db/models.py` | 移動 |
| `ai/provider.py` | `services/ai.py` | 統合 |
| `ai/anthropic_provider.py` | `services/ai.py` | 統合 |
| `ai/prompts.py` | `utils/prompts.py` | 移動 |
| `eavesdrop/llm_judge.py` | `services/eavesdrop.py` | 統合 |
| `eavesdrop/conversation_buffer.py` | `services/eavesdrop.py` | 統合 |
| `errors/discord_errors.py` | `errors/discord.py` | リネーム |
| `errors/database_errors.py` | `errors/database.py` | リネーム |
| `utils/message_formatter.py` | `utils/message.py` | 統合 |
| `utils/message_splitter.py` | `utils/message.py` | 統合 |
| (新規) | `errors/messages.py` | 新規作成 |
| (新規) | `utils/datetime.py` | 新規作成 |

### 5.3 削除対象ディレクトリ

- `router/` → `bot/router.py` に統合
- `ai/` → `services/ai.py` と `utils/prompts.py` に分割
- `session/` → `services/session.py` と `db/models.py` に分割
- `eavesdrop/` → `services/eavesdrop.py` に統合
- `commands/` → `bot/commands.py` に統合
- `prompts/`（ルートレベル） → `src/kotonoha_bot/prompts/` に移動
- `data/`（ルートレベル） → 削除

### 5.4 構造比較

| 項目 | 現在 | リファクタリング後 |
|------|------|-------------------|
| ディレクトリ数 | 10 | 7（handlers/パッケージ追加） |
| ファイル数 | 22 | 22（handlers分割により増加） |
| 最大深度 | 2階層 | 2階層 |
| handlers.py | 832行（1ファイル） | 物理分割（handlers/パッケージ、3ファイル） |

---

## 6. 詳細実装計画

詳細な実装手順、各ステップ（Step 0-7）のコード例については、以下のドキュメントを参照してください：

- **[詳細実装計画（Step 0-7）](./phase10-implementation-steps.md)**: 各ステップの詳細な実装手順とコード例

テストコードリファクタリング、完了基準、リスク管理、改善提案については、以下のドキュメントを参照してください：

- **[テスト・完了基準・リスク管理](./phase10-implementation-testing.md)**: テストコードリファクタリング、完了基準とチェックリスト、リスク管理、改善提案、付録

---

## 7. 完了報告

### 7.1 実装完了状況

Phase 10 の完全リファクタリングは、2026年1月19日に完了しました。

#### 主要な達成項目

1. **コード構造の整理**:
   - ✅ 新フォルダ構造への移行完了（`handlers/`, `services/`, `errors/`, `utils/`, `rate_limit/` など）
   - ✅ 不要なディレクトリの削除完了（`router/`, `commands/`, `external/ai/`, `features/eavesdrop/` など）
   - ✅ `bot/handlers.py` の物理分割完了（832行 → 4ファイルに分割）

2. **コード品質の向上**:
   - ✅ 重複コードの削除完了（日付フォーマット、プロンプト読み込み、エラーメッセージの一元管理）
   - ✅ 依存性注入パターンの適用完了
   - ✅ 例外のラッピング完了（抽象化の徹底）
   - ✅ Config のインスタンス化完了（Pydantic V2）

3. **テストの充実**:
   - ✅ テスト構造がソースコード構造と対応完了
   - ✅ 全テスト通過（313個すべて成功、スキップ0個）

4. **機能の維持**:
   - ✅ 既存の全機能が正常動作（回帰テスト完了）
   - ✅ `services/ai.py` の戻り値が `tuple[str, TokenInfo]` に変更完了

#### 各 Step の完了状況

- ✅ **Step 0**: 依存方向の確定（循環参照の防止）
- ✅ **Step 1**: 足場固め（config.py Pydantic化、utils/, errors/ の作成・移動）
- ✅ **Step 2**: データ層とビジネスロジック（db/ の移動、services/session.py の作成）
- ✅ **Step 3**: AIサービスと抽象化（services/ai.py の統合、例外ラッピング、戻り値変更）
- ✅ **Step 4**: プレゼンテーション層（bot/handlers/ の物理分割、setup_handlers (DI) の実装）
- ✅ **Step 5**: 結合と仕上げ（main.py の実装、Graceful Shutdown）
- ✅ **Step 6**: 結合テスト（E2E的な動作確認）
- ⚠️ **Step 7**: 品質向上（型ヒント・docstring の完全化 - 一部完了）

### 7.2 残存課題

以下の項目は、Phase 10 の必須スコープ外として、今後の改善項目として残存しています：

- **型ヒントの完全化**: 一部のファイルで型ヒントが不完全（`ruff check` で10エラー残存）
- **docstring の完全化**: 一部の公開APIでdocstringが不足
- **コードフォーマット**: 13ファイルがフォーマット必要
- **型チェック**: `ty` による型チェックで8エラー残存
- **テストカバレッジ**: 現在70%（目標80%未達）

これらの項目は、Phase 10 の主要な目標（コード構造の整理、重複コードの削除、依存性注入の改善）は達成されているため、今後の改善項目として継続的に対応していきます。

### 7.3 次のステップ

Phase 10 の完了により、以下のフェーズに進むことができます：

- **Phase 11**: ハイブリッド検索の実装（推奨）
- **Phase 12**: Reranking の実装（オプション）
- **Phase 13**: コスト管理の実装
- **Phase 14**: 監査ログの実装

**詳細な完了報告は以下のドキュメントを参照してください：**

- **[基本方針 - 完了報告](./phase10.md#13-完了報告)**: Phase 10 の概要と完了状況
- **[詳細実装計画 - 完了報告](./phase10-implementation-steps.md#7-完了報告)**: 各ステップの詳細な完了状況
- **[テスト・完了基準・リスク管理 - 完了報告](./phase10-implementation-testing.md#11-完了報告)**: 完了基準の達成状況と残存課題
