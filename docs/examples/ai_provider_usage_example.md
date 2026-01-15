# AIProvider の使用例

## 現在の実装：LiteLLMProvider を使う場合

### 1. 実際の使用フロー

```text
Discordユーザーがメッセージを送信
    ↓
MessageHandler.handle_mention() が呼ばれる
    ↓
self.ai_provider = LiteLLMProvider()  (23行目)
    ↓
response_text = self.ai_provider.generate_response(...)  (99行目)
    ↓
LiteLLMProvider.generate_response() が実行される
    ↓
LiteLLM経由でClaude APIを呼び出し
    ↓
応答テキストを返す
    ↓
Discordに返信
```

### 2. コード例

**handlers.py での使用:**

```python
class MessageHandler:
    def __init__(self, bot: KotonohaBot):
        # LiteLLMProvider をインスタンス化
        # これは AIProvider を継承しているので、
        # generate_response() メソッドが使える
        self.ai_provider = LiteLLMProvider()

    async def handle_mention(self, message: discord.Message):
        # ...
        # AIProvider の generate_response() を呼び出す
        # 実際には LiteLLMProvider.generate_response() が実行される
        response_text = self.ai_provider.generate_response(
            messages=session.get_conversation_history(),
            system_prompt=system_prompt,
        )
```

**LiteLLMProvider の実装:**

```python
class LiteLLMProvider(AIProvider):  # AIProvider を継承
    def generate_response(self, messages, system_prompt=None):
        # AIProvider で定義された抽象メソッドを実装
        # LiteLLM経由でClaude APIを呼び出す
        response = litellm.completion(...)
        return response.choices[0].message.content
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
            self.ai_provider = LiteLLMProvider()  # LiteLLMProvider も AIProvider を継承

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
            self.ai_provider = LiteLLMProvider()
```

## なぜこの設計が便利か？

### メリット 1: コードの再利用

- `MessageHandler` のコードは変更不要
- `generate_response()` の呼び出し方は同じ

### メリット 2: 型安全性

```python
# AIProvider を継承しているので、型チェックが効く
def use_ai_provider(provider: AIProvider):  # 型ヒント
    response = provider.generate_response(...)  # このメソッドがあることが保証される

# どちらのプロバイダーでも使える
use_ai_provider(LiteLLMProvider())
use_ai_provider(OpenAIProvider())
```

### メリット 3: テストが簡単

```python
# モックプロバイダーを作成
class MockAIProvider(AIProvider):
    def generate_response(self, messages, system_prompt=None):
        return "テスト応答"

# テスト時にモックを使える
handler = MessageHandler(bot)
handler.ai_provider = MockAIProvider()  # 実際のAPIを呼ばずにテストできる
```

## 実際の動作例

### シナリオ：ユーザーが「こんにちは」とメンション

1. **Discord メッセージ受信**

   ```text
   ユーザー: @コトノハ こんにちは
   ```

2. **MessageHandler.handle_mention() が呼ばれる**

   ```python
   # handlers.py 99行目
   response_text = self.ai_provider.generate_response(
       messages=[Message(role=USER, content="こんにちは")],
       system_prompt="あなたはコトノハです..."
   )
   ```

3. **LiteLLMProvider.generate_response() が実行される**

   ```python
   # litellm_provider.py 75行目
   def generate_response(self, messages, system_prompt=None):
       # LiteLLM経由でClaude APIを呼び出す
       response = litellm.completion(
           model="anthropic/claude-3-haiku-20240307",
           messages=[...]
       )
       return "こんにちは！お話しできて嬉しいです。"
   ```

4. **Discord に返信**

   ```text
   コトノハ: こんにちは！お話しできて嬉しいです。
   ```

## まとめ

- **AIProvider**: 「AI 応答を生成する」という機能の約束事（インターフェース）
- **LiteLLMProvider**: その約束事を実装した具体的なクラス（Claude API を使う）
- **MessageHandler**: どちらの実装でも使える（AIProvider の約束事だけを知っていれば OK）

これにより、プロバイダーを追加・変更しても、使う側のコードは変更不要になります！
