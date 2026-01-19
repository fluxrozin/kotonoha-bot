# AIProvider の使用例

## 現在の実装：LiteLLMProvider を使う場合

### 1. 実際の使用フロー

```text
Discordユーザーがメッセージを送信
    ↓
MessageHandler.handle_mention() が呼ばれる（リクエストキューに追加）
    ↓
self.ai_provider = LiteLLMProvider()  (40行目、__init__で初期化)
    ↓
_process_mention() が実行される
    ↓
response_text = await self.ai_provider.generate_response(...)  (194行目)
    ↓
LiteLLMProvider.generate_response() が実行される（async）
    ↓
レート制限チェックとトークン取得
    ↓
LiteLLM経由でClaude APIを呼び出し
    ↓
応答テキストを返す
    ↓
Discordに返信（メッセージ分割対応）
```

### 2. コード例

**handlers.py での使用:**

```python
class MessageHandler:
    def __init__(self, bot: KotonohaBot):
        # LiteLLMProvider をインスタンス化
        # これは AIProvider を継承しているので、
        # generate_response() メソッドが使える
        self.ai_provider = LiteLLMProvider()  # 40行目
        # リクエストキューも初期化
        self.request_queue = RequestQueue(max_size=100)

    async def handle_mention(self, message: discord.Message):
        # リクエストキューに追加（優先度: MENTION）
        future = await self.request_queue.enqueue(
            RequestPriority.MENTION,
            self._process_mention,
            message,
        )
        await future

    async def _process_mention(self, message: discord.Message):
        # ...
        # AIProvider の generate_response() を呼び出す（async）
        # 実際には LiteLLMProvider.generate_response() が実行される
        response_text = await self.ai_provider.generate_response(
            messages=session.get_conversation_history(),
            system_prompt=system_prompt,
        )
        # 使用モデル名とレート制限使用率を取得
        model_name = self.ai_provider.get_last_used_model()
        rate_limit_usage = self.ai_provider.get_rate_limit_usage()
```

**LiteLLMProvider の実装:**

```python
class LiteLLMProvider(AIProvider):  # AIProvider を継承
    def __init__(self, model: str = Config.LLM_MODEL):
        self.model = model  # デフォルト: anthropic/claude-sonnet-4-5
        self.fallback_model = Config.LLM_FALLBACK_MODEL
        # レート制限モニターとトークンバケットを初期化
        self.rate_limit_monitor = RateLimitMonitor(...)
        self.token_bucket = TokenBucket(...)
        self._last_used_model: str | None = None

    async def generate_response(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        # AIProvider で定義された抽象メソッドを実装（async）
        # レート制限チェックとトークン取得
        self.rate_limit_monitor.record_request("claude-api")
        await self.token_bucket.wait_for_tokens(tokens=1, timeout=30.0)

        # LiteLLM経由でClaude APIを呼び出す
        response = litellm.completion(
            model=model or self.model,
            messages=self._convert_messages(messages, system_prompt),
            temperature=Config.LLM_TEMPERATURE,
            max_tokens=max_tokens or Config.LLM_MAX_TOKENS,
            fallbacks=[self.fallback_model] if self.fallback_model else None,
        )
        # 最後に使用したモデル名を保存
        self._last_used_model = response.model or self.model
        return response.choices[0].message.content

    def get_last_used_model(self) -> str:
        """最後に使用したモデル名を取得"""
        return self._last_used_model or self.model

    def get_rate_limit_usage(self, endpoint: str = "claude-api") -> float:
        """レート制限の使用率を取得（0.0-1.0）"""
        _, usage_rate = self.rate_limit_monitor.check_rate_limit(endpoint)
        return usage_rate
```

## 別のプロバイダーを追加する場合の例

### 例：OpenAIProvider を追加する場合

**新しいファイル: `src/kotonoha_bot/ai/openai_provider.py`**

```python
from openai import OpenAI
from .provider import AIProvider  # AIProvider を継承
from ..session.models import Message

class OpenAIProvider(AIProvider):  # 同じ AIProvider を継承
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def generate_response(self, messages, system_prompt=None):
        # AIProvider で定義された抽象メソッドを実装
        # OpenAI APIを直接呼び出す
        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=self._convert_messages(messages, system_prompt)
        )
        return response.choices[0].message.content

    def _convert_messages(self, messages, system_prompt):
        # OpenAI用のメッセージ形式に変換
        # ...
```

### handlers.py を変更せずに切り替え可能

#### 方法 1: 環境変数で切り替え

```python
# handlers.py を変更
from ..ai.litellm_provider import LiteLLMProvider
from ..ai.openai_provider import OpenAIProvider

class MessageHandler:
    def __init__(self, bot: KotonohaBot):
        # 環境変数でプロバイダーを選択
        provider_type = os.getenv("AI_PROVIDER", "litellm")

        if provider_type == "openai":
            self.ai_provider = OpenAIProvider()  # OpenAIProvider も AIProvider を継承
        else:
            # LiteLLMProvider も AIProvider を継承
            self.ai_provider = LiteLLMProvider()

        # どちらも同じ generate_response() メソッドを持っているので、
        # 以降のコードは変更不要！

    async def handle_mention(self, message: discord.Message):
        # この部分は全く変更不要！
        response_text = self.ai_provider.generate_response(
            messages=session.get_conversation_history(),
            system_prompt=system_prompt,
        )
```

#### 方法 2: 設定ファイルで切り替え

```python
# config.py に追加
AI_PROVIDER = os.getenv("AI_PROVIDER", "litellm")  # "litellm" または "openai"

# handlers.py
from ..config import Config
from ..ai.litellm_provider import LiteLLMProvider
from ..ai.openai_provider import OpenAIProvider

class MessageHandler:
    def __init__(self, bot: KotonohaBot):
        if Config.AI_PROVIDER == "openai":
            self.ai_provider = OpenAIProvider()
        else:
            self.ai_provider = LiteLLMProvider()  # デフォルトモデル: claude-sonnet-4-5
```

## なぜこの設計が便利か？

### メリット 1: コードの再利用

- `MessageHandler` のコードは変更不要
- `generate_response()` の呼び出し方は同じ

### メリット 2: 型安全性

```python
# AIProvider を継承しているので、型チェックが効く
async def use_ai_provider(provider: AIProvider):  # 型ヒント
    response = await provider.generate_response(...)  # async メソッド

# どちらのプロバイダーでも使える
await use_ai_provider(LiteLLMProvider())
await use_ai_provider(OpenAIProvider())
```

### メリット 3: テストが簡単

```python
# モックプロバイダーを作成
class MockAIProvider(AIProvider):
    async def generate_response(
        self, messages, system_prompt=None, model=None, max_tokens=None
    ):
        return "テスト応答"

    def get_last_used_model(self) -> str:
        return "mock-model"

    def get_rate_limit_usage(self, endpoint: str = "claude-api") -> float:
        return 0.0

# テスト時にモックを使える
handler = MessageHandler(bot)
handler.ai_provider = MockAIProvider()  # 実際のAPIを呼ばずにテストできる
```

## 実際の動作例

### シナリオ：ユーザーが「こんにちは」とメンション

1. **Discord メッセージ受信**

   ```text
   ユーザー: @KOTONOHA こんにちは
   ```

2. **MessageHandler.handle_mention() が呼ばれる**

   ```python
   # handlers.py 121行目
   # リクエストキューに追加（優先度: MENTION）
   future = await self.request_queue.enqueue(
       RequestPriority.MENTION,
       self._process_mention,
       message,
   )
   await future
   ```

3. **\_process_mention() が実行される**

   ```python
   # handlers.py 194行目
   response_text = await self.ai_provider.generate_response(
       messages=session.get_conversation_history(),
       system_prompt=system_prompt,
   )
   ```

4. **LiteLLMProvider.generate_response() が実行される**

   ```python
   # litellm_provider.py 100行目
   async def generate_response(self, messages, system_prompt=None, model=None, max_tokens=None):
       # レート制限チェックとトークン取得
       self.rate_limit_monitor.record_request("claude-api")
       await self.token_bucket.wait_for_tokens(tokens=1, timeout=30.0)

       # LiteLLM経由でClaude APIを呼び出す
       response = litellm.completion(
           model=model or self.model,  # デフォルト: anthropic/claude-sonnet-4-5
           messages=self._convert_messages(messages, system_prompt),
           temperature=Config.LLM_TEMPERATURE,
           max_tokens=max_tokens or Config.LLM_MAX_TOKENS,
       )
       self._last_used_model = response.model or self.model
       return response.choices[0].message.content
   ```

5. **Discord に返信**

   ```text
   KOTONOHA: こんにちは！お話しできて嬉しいです。
   ```

## まとめ

- **AIProvider**: 「AI 応答を生成する」という機能の約束事（抽象クラス）
- **LiteLLMProvider**: その約束事を実装した具体的なクラス（Claude API を使う）
  - デフォルトモデル: `anthropic/claude-sonnet-4-5`
  - レート制限機能付き
  - リトライ機能付き（一時的なエラーに対して）
- **MessageHandler**: どちらの実装でも使える（AIProvider の約束事だけを知っていれば OK）
  - リクエストキューを使用して優先度付き処理
  - `generate_response()` は `async` メソッド

これにより、プロバイダーを追加・変更しても、使う側のコードは変更不要になります！

## 主な機能

### レート制限

- トークンバケットアルゴリズムを使用
- デフォルト: 1 分間に 50 リクエストまで
- 使用率を取得可能: `get_rate_limit_usage()`

### リトライ機能

- 一時的なエラー（InternalServerError, RateLimitError）に対して自動リトライ
- 指数バックオフ: 1 秒 → 2 秒 → 4 秒
- 最大リトライ回数: 3 回（デフォルト）

### モデル管理

- デフォルトモデル: `anthropic/claude-sonnet-4-5`
- フォールバックモデル: 設定可能（`LLM_FALLBACK_MODEL`）
- 最後に使用したモデル名を取得可能: `get_last_used_model()`
