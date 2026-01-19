# Phase 9: LiteLLM 削除、Anthropic SDK 直接使用への移行

**作成日**: 2026年1月19日  
**バージョン**: 1.0  
**対象プロジェクト**: kotonoha-bot v0.9.0  
**前提条件**: Phase 8（PostgreSQL + pgvector 実装）完了済み、全テスト通過

---

## 目次

1. [エグゼクティブサマリー](#1-エグゼクティブサマリー)
2. [目的とスコープ](#2-目的とスコープ)
3. [設計方針](#3-設計方針)
4. [実装ステップ](#4-実装ステップ)
5. [完了基準](#5-完了基準)
6. [テスト計画](#6-テスト計画)
7. [導入・デプロイ手順](#7-導入デプロイ手順)
8. [今後の改善計画](#8-今後の改善計画)

---

## 1. エグゼクティブサマリー

### 1.1 目的

LiteLLM を削除し、Anthropic SDK を直接使用することで、以下の目的を達成する：

1. **パフォーマンス向上**: オーバーヘッドの削減、メモリ使用量の削減
2. **セキュリティ向上**: セキュリティリスクの削減（複数の CVE の解消）
3. **コードのシンプル化**: 依存関係の削減、設定の簡素化、コードの理解しやすさ向上
4. **保守性向上**: デバッグの容易さ、プロバイダー固有の機能を直接利用可能

### 1.2 背景

現在の実装では、LLM API へのアクセスに LiteLLM を使用しているが、実際の使用状況は以下の通り：

- **チャット/会話判定**: Claude のみ（すべて同じプロバイダー Anthropic）
  - 開発: `claude-haiku-4-5`
  - 本番: `claude-opus-4-5`
- **ベクトル化**: OpenAI のみ（直接 OpenAI SDK を使用）

プロバイダーを切り替える必要がないため、LiteLLM の主な価値（統一インターフェース）が不要である。

また、LiteLLM には以下のデメリットがある：

- **パフォーマンス劣化**: 長時間稼働時のレイテンシ増加
- **メモリ使用量**: 高メモリ消費（24GB RAM @ 9 req/sec の報告）
- **セキュリティ脆弱性**: 複数の CVE（CVE-2025-0628, CVE-2024-5710, CVE-2024-4888, CVE-2025-0330, CVE-2024-9606）
- **オーバーヘッド**: 抽象化レイヤーによる追加のレイテンシ
- **複雑性**: 設定が多岐にわたる
- **接続プール問題**: 長時間稼働時の接続枯渇（現在の実装で対処している）

### 1.3 主要な実装項目

| 項目 | 内容 |
|------|------|
| Anthropic SDK の導入 | `anthropic` パッケージを追加 |
| AnthropicProvider の実装 | `LiteLLMProvider` を置き換え |
| レート制限機能の移行 | 既存のレート制限機能を Anthropic SDK に適応 |
| フォールバック機能の削除 | プロバイダー固定のため不要 |
| 依存関係の整理 | `litellm` を削除 |
| 設定の簡素化 | LiteLLM 固有の設定を削除 |

### 1.4 実装期間

約 3-5 日

---

## 2. 目的とスコープ

### 2.1 目的

1. **パフォーマンス向上**: オーバーヘッドの削減、メモリ使用量の削減
2. **セキュリティ向上**: セキュリティリスクの削減
3. **コードのシンプル化**: 依存関係の削減、設定の簡素化
4. **保守性向上**: デバッグの容易さ、プロバイダー固有の機能を直接利用可能

### 2.2 スコープ

- **Anthropic SDK の導入**: `anthropic` パッケージを追加
- **AnthropicProvider の実装**: `src/kotonoha_bot/ai/anthropic_provider.py` を作成
- **LiteLLMProvider の置き換え**: `LiteLLMProvider` を `AnthropicProvider` に置き換え
- **既存の抽象化レイヤーの維持**: `AIProvider` インターフェースは維持
- **レート制限機能の移行**: 既存のレート制限機能を Anthropic SDK に適応
- **フォールバック機能の削除**: プロバイダー固定のため不要
- **依存関係の整理**: `litellm` を削除
- **設定の簡素化**: LiteLLM 固有の設定を削除

### 2.3 スコープ外

- **他のプロバイダーへの対応**: 現在は Anthropic のみを使用するため、他のプロバイダーへの対応は不要
- **フォールバック機能**: プロバイダー固定のため不要
- **LiteLLM の機能の完全な再実装**: 必要な機能のみを実装

---

## 3. 設計方針

### 3.1 Anthropic SDK の採用理由

**Anthropic SDK のメリット**:

- **シンプルさ**: 依存関係が少ない、設定がシンプル、コードが理解しやすい
- **パフォーマンス**: オーバーヘッドが少ない、直接的な API 呼び出し、メモリ使用量が少ない
- **セキュリティ**: セキュリティリスクが少ない、プロバイダー固有の機能を直接利用できる
- **保守性**: コードが理解しやすい、デバッグが容易

**LiteLLM のデメリット**:

- **パフォーマンス劣化**: 長時間稼働時のレイテンシ増加
- **メモリ使用量**: 高メモリ消費（24GB RAM @ 9 req/sec の報告）
- **セキュリティ脆弱性**: 複数の CVE
- **オーバーヘッド**: 抽象化レイヤーによる追加のレイテンシ
- **複雑性**: 設定が多岐にわたる

### 3.2 既存の抽象化レイヤーの維持

`AIProvider` インターフェースは維持し、実装のみを変更する。これにより：

- 既存のコードへの影響を最小化
- 将来の拡張性を維持
- テストの互換性を維持

### 3.3 レート制限機能の移行

既存のレート制限機能（`RateLimitMonitor`、`TokenBucket`）は維持し、Anthropic SDK に適応する。

### 3.4 トークン情報の取得

Anthropic SDK のレスポンスからトークン情報を取得し、Phase 14（コスト管理機能）と Phase 15（監査ログ機能）で使用できるようにする。

**重要**: `anthropic_provider.py` の戻り値を `tuple[str, dict]` に変更する（Phase 14 と Phase 15 で必要）。

```python
async def generate_response(
    self,
    messages: list[Message],
    system_prompt: str | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
) -> tuple[str, dict]:
    """Anthropic SDK 経由で LLM API を呼び出して応答を生成
    
    Returns:
        tuple[str, dict]: (応答テキスト, メタデータ)
        - メタデータには以下のキーが含まれる:
          - "input_tokens": int
          - "output_tokens": int
          - "model": str
    """
```

---

## 4. 実装ステップ

### 4.1 実装ステップと完了状況

| Step | 内容 | 期間 | 完了状況 | 詳細ドキュメント |
|------|------|------|---------|------------------|
| 0 | 依存関係の確認と設計レビュー | 0.5日 | ⏳ 未実装 | - |
| 1 | Anthropic SDK の導入 | 0.5日 | ⏳ 未実装 | - |
| 2 | AnthropicProvider の実装 | 1.5日 | ⏳ 未実装 | - |
| 3 | LiteLLMProvider の置き換え | 0.5日 | ⏳ 未実装 | - |
| 4 | テストの実装と更新 | 0.5日 | ⏳ 未実装 | - |
| 5 | 依存関係の整理 | 0.5日 | ⏳ 未実装 | - |
| **合計** | | **3-5日** | **⏳ 未実装** | |

### 4.2 各ステップの詳細

#### Step 0: 依存関係の確認と設計レビュー

**完了内容**:

- Phase 8の実装状況を確認
- Anthropic SDK のバージョンと互換性を確認
- 設計方針のレビュー

**確認事項**:

- PostgreSQL 18 + pgvector 0.8.1 が正常に動作していること
- `LiteLLMProvider` クラスの実装を確認
- `AIProvider` インターフェースの定義を確認
- 既存のレート制限機能の実装を確認

#### Step 1: Anthropic SDK の導入

**完了内容**:

- `pyproject.toml` に `anthropic` パッケージを追加
- 依存関係のインストール

**実装ファイル**: `pyproject.toml`

**追加する依存関係**:

```toml
[project]
dependencies = [
    # ... 既存の依存関係 ...
    "anthropic>=0.34.0",  # Anthropic SDK
]
```

**注意点**:

- Anthropic SDK の最新バージョンを確認
- 互換性のあるバージョンを選択

#### Step 2: AnthropicProvider の実装

**完了内容**:

- `src/kotonoha_bot/ai/anthropic_provider.py` の作成
- `AnthropicProvider` クラスの実装
- レート制限機能の統合
- トークン情報の取得と返却

**実装ファイル**: `src/kotonoha_bot/ai/anthropic_provider.py`

**クラス構造**:

```python
from anthropic import Anthropic
from ..config import Config
from ..rate_limit.monitor import RateLimitMonitor
from ..rate_limit.token_bucket import TokenBucket
from ..session.models import Message, MessageRole
from .provider import AIProvider

class AnthropicProvider(AIProvider):
    """Anthropic SDK を使用した LLM プロバイダー
    
    Anthropic SDK を直接使用して Claude API を呼び出す。
    - 開発: claude-haiku-4-5（超低コスト）
    - 本番: claude-opus-4-5（最高品質）
    """
    
    def __init__(self, model: str = Config.LLM_MODEL):
        self.model = model
        self.max_retries = Config.LLM_MAX_RETRIES
        self.retry_delay_base = Config.LLM_RETRY_DELAY_BASE
        
        # Anthropic SDK クライアントの初期化
        self.client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        
        # レート制限モニターとトークンバケットの初期化
        self.rate_limit_monitor = RateLimitMonitor(
            window_seconds=Config.RATE_LIMIT_WINDOW,
            warning_threshold=Config.RATE_LIMIT_THRESHOLD,
        )
        self.token_bucket = TokenBucket(
            capacity=Config.RATE_LIMIT_CAPACITY,
            refill_rate=Config.RATE_LIMIT_REFILL,
        )
        # デフォルトのレート制限を設定（1分間に50リクエスト）
        self.rate_limit_monitor.set_rate_limit(
            "claude-api", limit=50, window_seconds=60
        )
    
    async def generate_response(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> tuple[str, dict]:
        """Anthropic SDK 経由で LLM API を呼び出して応答を生成
        
        Returns:
            tuple[str, dict]: (応答テキスト, メタデータ)
            - メタデータには以下のキーが含まれる:
              - "input_tokens": int
              - "output_tokens": int
              - "model": str
        """
        # レート制限チェックとトークン取得
        endpoint = "claude-api"
        self.rate_limit_monitor.record_request(endpoint)
        self.rate_limit_monitor.check_rate_limit(endpoint)
        
        # トークンバケットからトークンを取得（タイムアウト: 30秒）
        if not await self.token_bucket.wait_for_tokens(tokens=1, timeout=30.0):
            raise RuntimeError("Rate limit: Could not acquire token within timeout")
        
        # Anthropic SDK 用のメッセージ形式に変換
        anthropic_messages = self._convert_messages(messages, system_prompt)
        
        # 使用するモデルを決定（LiteLLM の形式から Anthropic SDK の形式に変換）
        use_model = self._convert_model_name(model or self.model)
        use_max_tokens = max_tokens or Config.LLM_MAX_TOKENS
        
        # リトライロジック
        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                # APIリクエスト
                response = await self.client.messages.create(
                    model=use_model,
                    max_tokens=use_max_tokens,
                    temperature=Config.LLM_TEMPERATURE,
                    system=system_prompt,
                    messages=anthropic_messages,
                )
                
                # レスポンスからテキストを取得
                if not response.content or len(response.content) == 0:
                    raise ValueError("No content in response")
                
                # Anthropic SDK のレスポンス形式に合わせて処理
                result_text = ""
                for content_block in response.content:
                    if content_block.type == "text":
                        result_text += content_block.text
                
                if not result_text:
                    raise ValueError("Empty response content")
                
                # メタデータを構築
                metadata = {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "model": response.model,
                }
                
                logger.info(
                    f"Generated response: {len(result_text)} chars, "
                    f"tokens: input={metadata['input_tokens']}, "
                    f"output={metadata['output_tokens']}"
                )
                
                return result_text, metadata
                
            except anthropic.APIError as e:
                # API エラー: リトライ可能なエラーかどうかを判定
                if e.status_code in [429, 500, 502, 503, 504]:
                    # 一時的なエラー: リトライ可能
                    last_exception = e
                    if attempt < self.max_retries:
                        delay = self.retry_delay_base * (2**attempt)
                        logger.warning(
                            f"API error (attempt {attempt + 1}/{self.max_retries + 1}): {e}. "
                            f"Retrying in {delay}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"API error after {self.max_retries + 1} attempts: {e}"
                        )
                        raise
                else:
                    # 認証エラーなど、リトライ不可なエラー
                    logger.error(f"API error (non-retryable): {e}")
                    raise
                    
            except Exception as e:
                # その他の予期しないエラー
                logger.error(f"Unexpected Anthropic API error: {e}")
                raise
        
        # この行には到達しないはずだが、念のため
        if last_exception:
            raise last_exception
        raise RuntimeError("Unexpected error in generate_response")
    
    def _convert_model_name(self, model: str) -> str:
        """LiteLLM のモデル名を Anthropic SDK のモデル名に変換
        
        Args:
            model: LiteLLM 形式のモデル名（例: "anthropic/claude-haiku-4-5"）
        
        Returns:
            Anthropic SDK 形式のモデル名（例: "claude-haiku-4-5"）
        """
        # "anthropic/" プレフィックスを削除
        if model.startswith("anthropic/"):
            return model[len("anthropic/"):]
        return model
    
    def _convert_messages(
        self, messages: list[Message], system_prompt: str | None
    ) -> list[dict]:
        """Anthropic SDK 用のメッセージ形式に変換
        
        Args:
            messages: 会話履歴
            system_prompt: システムプロンプト（Anthropic SDK では messages に含めない）
        
        Returns:
            Anthropic SDK 形式のメッセージリスト
        """
        anthropic_messages = []
        
        # 会話履歴を追加（システムプロンプトは messages.create の system パラメータで指定）
        for message in messages:
            role = "user" if message.role == MessageRole.USER else "assistant"
            anthropic_messages.append({"role": role, "content": message.content})
        
        return anthropic_messages
```

**注意点**:

- Anthropic SDK は非同期 API を提供しているため、`async/await` を使用
- モデル名の変換が必要（LiteLLM 形式: `anthropic/claude-haiku-4-5` → Anthropic SDK 形式: `claude-haiku-4-5`）
- システムプロンプトは `messages.create` の `system` パラメータで指定
- レスポンスの `content` はリスト形式（`content_block.type == "text"` をチェック）

#### Step 3: LiteLLMProvider の置き換え

**完了内容**:

- `LiteLLMProvider` を `AnthropicProvider` に置き換え
- 呼び出し元のコードを更新（戻り値の変更に対応）

**実装ファイル**:

- `src/kotonoha_bot/bot/handlers.py`
- `src/kotonoha_bot/eavesdrop/llm_judge.py`
- `src/kotonoha_bot/main.py`（プロバイダーの初期化部分）

**変更内容**:

```python
# 変更前
from kotonoha_bot.ai.litellm_provider import LiteLLMProvider

provider = LiteLLMProvider()

# 変更後
from kotonoha_bot.ai.anthropic_provider import AnthropicProvider

provider = AnthropicProvider()
```

**戻り値の変更に対応**:

```python
# 変更前
response = await provider.generate_response(messages, system_prompt)

# 変更後
response, metadata = await provider.generate_response(messages, system_prompt)
# metadata は Phase 14, 15 で使用するため、現時点では使用しない
```

**注意点**:

- すべての呼び出し元で戻り値の変更に対応する必要がある
- メタデータは現時点では使用しないが、Phase 14, 15 で使用するため保持する

#### Step 4: テストの実装と更新

**完了内容**:

- `AnthropicProvider` のユニットテスト
- 既存のテストの更新（`LiteLLMProvider` → `AnthropicProvider`）
- 統合テストの更新

**実装ファイル**:

- `tests/unit/test_anthropic_provider.py`: `AnthropicProvider` のユニットテスト
- `tests/unit/test_litellm_provider.py`: 削除または `test_anthropic_provider.py` に統合
- `tests/integration/test_ai_provider.py`: 統合テストの更新

**テスト項目**:

1. **基本機能テスト**:
   - `generate_response` メソッドの基本動作
   - メタデータの返却
   - エラーハンドリング

2. **レート制限テスト**:
   - レート制限の動作確認
   - トークンバケットの動作確認

3. **リトライテスト**:
   - 一時的なエラーに対するリトライ
   - 最大リトライ回数の確認

4. **モデル名変換テスト**:
   - LiteLLM 形式から Anthropic SDK 形式への変換

#### Step 5: 依存関係の整理

**完了内容**:

- `litellm` パッケージの削除
- `pyproject.toml` の更新
- 環境変数の整理（LiteLLM 固有の設定を削除）

**実装ファイル**: `pyproject.toml`, `.env.example`

**削除する依存関係**:

```toml
# 削除
litellm = "^1.0.0"  # または該当するバージョン
```

**削除する環境変数**（`.env.example` から）:

```bash
# LiteLLM 固有の設定（削除）
# LITELLM_* などの環境変数
```

**注意点**:

- 依存関係の削除前に、すべてのテストが通過することを確認
- 環境変数の削除前に、既存の設定ファイルを確認

---

## 5. 完了基準

### 5.1 実装完了基準

- ✅ `anthropic` パッケージが追加されている
- ✅ `AnthropicProvider` クラスが実装されている
- ✅ `LiteLLMProvider` が `AnthropicProvider` に置き換えられている
- ✅ 既存の抽象化レイヤー（`AIProvider` インターフェース）が維持されている
- ✅ レート制限機能が正常に動作している
- ✅ トークン情報が取得できている（メタデータとして返却）
- ✅ テストが実装されている
- ✅ テストが通過する
- ✅ `litellm` パッケージが削除されている
- ✅ LiteLLM 固有の設定が削除されている

### 5.2 品質基準

- **パフォーマンス**: 既存の実装と同等またはそれ以上のパフォーマンス
- **互換性**: 既存の `AIProvider` インターフェースとの互換性を維持
- **セキュリティ**: セキュリティリスクの削減（CVE の解消）
- **コード品質**: コードの可読性、保守性の向上

---

## 6. テスト計画

### 6.1 ユニットテスト

**テストファイル**: `tests/unit/test_anthropic_provider.py`

**テスト項目**:

1. `AnthropicProvider` の基本動作
2. メタデータの返却
3. エラーハンドリング
4. レート制限機能
5. リトライ機能
6. モデル名変換

### 6.2 統合テスト

**テストファイル**: `tests/integration/test_ai_provider.py`

**テスト項目**:

1. `AnthropicProvider` と既存のコードの統合
2. 実際の API 呼び出し（モックを使用）
3. エラーケースの処理

### 6.3 テスト実行方法

```bash
# 全テスト実行
pytest tests/ -v

# AnthropicProvider のテストのみ実行
pytest tests/unit/test_anthropic_provider.py -v
pytest tests/integration/test_ai_provider.py -v

# カバレッジ付きテスト実行
pytest tests/ -v --cov=src/kotonoha_bot --cov-report=term-missing
```

---

## 7. 導入・デプロイ手順

### 7.1 開発環境での導入

1. **Anthropic SDK の導入**

   ```bash
   # 依存関係のインストール
   poetry install
   # または
   pip install -e .
   ```

2. **環境変数の確認**

   ```bash
   # .env ファイルに ANTHROPIC_API_KEY が設定されていることを確認
   ANTHROPIC_API_KEY=sk-ant-...
   ```

3. **Bot の起動**

   ```bash
   docker compose up kotonoha-bot
   ```

4. **動作確認**

   - Bot が正常に起動することを確認
   - メンション応答が正常に動作することを確認
   - ログにエラーが出力されないことを確認

### 7.2 本番環境でのデプロイ

1. **依存関係の更新**

   ```bash
   # Docker イメージの再ビルド
   docker compose build kotonoha-bot
   ```

2. **環境変数の確認**

   - `ANTHROPIC_API_KEY` が設定されていることを確認
   - LiteLLM 固有の環境変数が削除されていることを確認

3. **段階的なデプロイ**

   - まず開発環境で動作確認
   - 問題がなければ本番環境にデプロイ

4. **動作確認**

   - Bot が正常に起動することを確認
   - メンション応答が正常に動作することを確認
   - ログにエラーが出力されないことを確認
   - パフォーマンスの改善を確認

---

## 8. 今後の改善計画

### 8.1 Phase 14: コスト管理機能

**目的**: トークン情報を使用してコスト管理機能を実装

**実装方法**: `AnthropicProvider` から返却されるメタデータを使用

### 8.2 Phase 15: 監査ログ機能

**目的**: トークン情報を使用して監査ログ機能を実装

**実装方法**: `AnthropicProvider` から返却されるメタデータを使用

### 8.3 パフォーマンス最適化

**目的**: Anthropic SDK の機能を活用してパフォーマンスを最適化

**実装方法**: ストリーミング、バッチ処理などの機能を検討

---

## 参考資料

- **ADR-0011**: [LiteLLM の削除とプロバイダー SDK の直接使用](../../20_architecture/22_adrs/0011-remove-litellm-direct-sdk.md)
- **Anthropic Python SDK**: [Anthropic Python SDK Documentation](https://github.com/anthropics/anthropic-sdk-python)
- **Phase 8 実装計画**: [Phase 8 実装計画](./phase08.md)

---

**作成日**: 2026年1月19日  
**最終更新日**: 2026年1月19日  
**バージョン**: 1.0  
**作成者**: kotonoha-bot 開発チーム
