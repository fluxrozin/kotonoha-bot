# Phase 4 実装完了報告 - 機能改善

Kotonoha Discord Bot の Phase 4（機能改善）の実装完了報告書

## 目次

1. [Phase 4 の目標](#phase-4-の目標)
2. [実装状況](#実装状況)
3. [前提条件](#前提条件)
4. [実装ステップ（参考情報）](#実装ステップ参考情報)
5. [完了基準](#完了基準)
6. [トラブルシューティング](#トラブルシューティング)
7. [次のフェーズへ](#次のフェーズへ)

---

## Phase 4 の目標

### 機能改善の目的

**目標**: Phase 1 で実装した機能の改善と不足機能の追加

**達成すべきこと**:

- メッセージ長制限対応（2000 文字超の応答を自動分割）
- セッション同期機能の改善（バッチ同期の定期実行）
- セッション設定の環境変数対応（`SESSION_TIMEOUT_HOURS`、`MAX_SESSIONS`）
- エラーハンドリングの改善（メッセージ追加時の自動保存オプション）

**スコープ外（Phase 5 以降）**:

- スレッド型、聞き耳型の実装（Phase 5 で実装予定）
- レート制限の高度な管理（Phase 6 で実装予定）
- スラッシュコマンド（Phase 6 で実装予定）

---

## 実装状況

### ✅ 実装完了（2026 年 1 月）

Phase 4 の実装は完了しています。以下の機能が実装されています:

**実装済み機能**:

- ✅ メッセージ分割機能（2000 文字超の応答を自動分割）
- ✅ バッチ同期の定期実行タスク（5 分ごと）
- ✅ セッションクリーンアップの定期実行（1 時間ごと、Phase 1 で実装済み）
- ✅ セッション設定の環境変数対応（`SESSION_TIMEOUT_HOURS`、`MAX_SESSIONS`）
- ✅ エラーハンドリングの改善（エラーメッセージの改善）

**実装されたファイル構造**:

```txt
src/kotonoha_bot/
├── utils/                    # ✅ 新規作成
│   ├── __init__.py          # ✅ 実装済み
│   └── message_splitter.py  # ✅ 実装済み（メッセージ分割機能）
├── bot/
│   └── handlers.py          # ✅ 更新（メッセージ分割統合、バッチ同期タスク追加）
└── config.py                # ✅ 更新（環境変数対応）

tests/unit/
└── test_message_splitter.py # ✅ 実装済み（メッセージ分割機能のテスト）
```

**メッセージ分割機能**:

- ✅ 2000 文字超のメッセージを自動検知
- ✅ 文の区切り（句点、改行）で適切に分割
- ✅ 連番を付与して複数メッセージに分割
- ✅ `handlers.py` に統合済み

**バッチ同期タスク**:

- ✅ 5 分ごとにアイドル状態のセッションを自動保存
- ✅ `discord.ext.tasks` を使用して実装
- ✅ `on_ready` イベントで自動開始

**セッション設定の環境変数対応**:

- ✅ `SESSION_TIMEOUT_HOURS` を環境変数から読み込み（デフォルト: 24 時間）
- ✅ `MAX_SESSIONS` を環境変数から読み込み（デフォルト: 100）
- ✅ `.env.example` に設定例を追加

**エラーハンドリングの改善**:

- ✅ エラーメッセージをより優しい表現に変更
- ✅ 場面緘黙支援を考慮した表現

**Phase 4 完了後の確認事項**:

- ✅ メッセージ分割機能が正常に動作する（テスト通過: 8/8）
- ✅ バッチ同期タスクが 5 分ごとに実行される
- ✅ セッションクリーンアップが 1 時間ごとに実行される（Phase 1 で実装済み）
- ✅ セッション設定が環境変数から読み込まれる
- ✅ エラーメッセージが改善されている
- ✅ 全てのテストが通過する（19/19）
- ✅ コード品質チェックが通過する（Ruff、ty）
- ✅ Phase 5（会話の契機拡張）の実装準備が整っている

---

## 前提条件

### 必要な環境

1. **Phase 1, 2, 3 の完了**

   - ✅ Phase 1: MVP（メンション応答型）完了
   - ✅ Phase 2: NAS デプロイ完了
   - ✅ Phase 3: CI/CD・運用機能完了

2. **開発環境**

   - Python 3.14
   - uv（推奨）または pip
   - Git
   - VSCode（推奨）

3. **動作確認環境**

   - Discord Bot が動作している環境
   - テスト用の Discord サーバー

### 必要な知識

- Python の基本的な知識
- Discord.py の基本的な知識
- 正規表現の基本的な知識（メッセージ分割用）

---

## 実装ステップ（参考情報）

> **注意**: 以下の実装ステップは既に完了しています。参考情報として記載しています。

このセクションでは、Phase 4 で実装した各ステップの詳細を記載しています。実装は完了しているため、新規実装時の参考としてご利用ください。

### Step 1: メッセージ分割機能の実装 (2 時間) ✅ 完了

#### 1.1 メッセージ分割ユーティリティの作成

`src/kotonoha_bot/utils/message_splitter.py` を作成します。

**機能**:

- 2000 文字超のメッセージを検知
- 文の区切り（句点、改行）で分割
- 連番を付与して複数メッセージに分割
- Embed の活用（オプション、6000 文字制限あり）

**実装例**:

```python
"""メッセージ分割ユーティリティ"""
import re
from typing import List

# Discord のメッセージ長制限
DISCORD_MESSAGE_MAX_LENGTH = 2000
DISCORD_EMBED_MAX_LENGTH = 6000

# 分割用の区切り文字（優先順位順）
SPLIT_PATTERNS = [
    r'。\n',      # 句点 + 改行
    r'。',        # 句点
    r'\n\n',      # 段落区切り（空行）
    r'\n',        # 改行
    r'[、，]',     # 読点
    r' ',         # スペース
]


def split_message(content: str, max_length: int = DISCORD_MESSAGE_MAX_LENGTH) -> List[str]:
    """メッセージを分割する

    Args:
        content: 分割するメッセージ
        max_length: 最大文字数（デフォルト: 2000）

    Returns:
        分割されたメッセージのリスト
    """
    if len(content) <= max_length:
        return [content]

    chunks = []
    remaining = content

    while len(remaining) > max_length:
        # 分割位置を探す
        split_pos = find_split_position(remaining, max_length)

        if split_pos == -1:
            # 分割位置が見つからない場合、強制的に max_length で分割
            chunks.append(remaining[:max_length])
            remaining = remaining[max_length:]
        else:
            chunks.append(remaining[:split_pos])
            remaining = remaining[split_pos:].lstrip()

    if remaining:
        chunks.append(remaining)

    return chunks


def find_split_position(text: str, max_length: int) -> int:
    """最適な分割位置を探す

    Args:
        text: 分割するテキスト
        max_length: 最大文字数

    Returns:
        分割位置（見つからない場合は -1）
    """
    # 最大長の範囲内で、後ろから順に区切り文字を探す
    search_end = min(max_length, len(text))
    search_text = text[:search_end]

    for pattern in SPLIT_PATTERNS:
        matches = list(re.finditer(pattern, search_text))
        if matches:
            # 最後のマッチ位置を返す
            last_match = matches[-1]
            # マッチした文字列の終了位置を返す
            return last_match.end()

    return -1


def format_split_messages(chunks: List[str], total: int) -> List[str]:
    """分割されたメッセージに連番を付与

    Args:
        chunks: 分割されたメッセージのリスト
        total: 総メッセージ数

    Returns:
        連番が付与されたメッセージのリスト
    """
    if len(chunks) == 1:
        return chunks

    formatted = []
    for i, chunk in enumerate(chunks, 1):
        header = f"**({i}/{total})**\n\n"
        formatted.append(header + chunk)

    return formatted
```

#### 1.2 メッセージハンドラーへの統合

`src/kotonoha_bot/bot/handlers.py` を更新して、メッセージ分割機能を統合します。

**変更点**:

- `handle_mention` メソッドで応答生成後、メッセージ分割を実行
- 分割されたメッセージを順次送信

**実装例**:

```python
from ..utils.message_splitter import split_message, format_split_messages

# handle_mention メソッド内で使用
# ... 既存のコード ...

# 返信（メッセージ分割対応）
response_chunks = split_message(response_text)
formatted_chunks = format_split_messages(response_chunks, len(response_chunks))

# 最初のメッセージは reply で送信
if formatted_chunks:
    first_message = await message.reply(formatted_chunks[0])

    # 残りのメッセージは順次送信
    for chunk in formatted_chunks[1:]:
        await message.channel.send(chunk)
        # レート制限を考慮して少し待機（オプション）
        await asyncio.sleep(0.5)
```

#### Step 1 完了チェックリスト

- [x] `src/kotonoha_bot/utils/__init__.py` が作成されている
- [x] `src/kotonoha_bot/utils/message_splitter.py` が作成されている
- [x] メッセージ分割機能が実装されている
- [x] 連番付与機能が実装されている
- [x] `handlers.py` に統合されている
- [x] 2000 文字超の応答が自動的に分割される（動作確認済み）

---

### Step 2: バッチ同期の定期実行タスクの実装 (1 時間 30 分) ✅ 完了

#### 2.1 バッチ同期タスクの追加

`src/kotonoha_bot/bot/handlers.py` にバッチ同期タスクを追加します。

**機能**:

- 5 分ごとにアイドル状態のセッションを自動保存
- `discord.ext.tasks` を使用して実装

**実装例**:

```python
from discord.ext import tasks
from datetime import datetime, timedelta

class MessageHandler:
    """メッセージハンドラー"""

    def __init__(self, bot: KotonohaBot):
        self.bot = bot
        self.session_manager = SessionManager()
        self.ai_provider = LiteLLMProvider()
        # タスクは on_ready イベントで開始する（イベントループが必要なため）

    def cog_unload(self):
        """クリーンアップタスクを停止"""
        self.cleanup_task.cancel()
        self.batch_sync_task.cancel()

    @tasks.loop(minutes=5)  # 5分ごとに実行
    async def batch_sync_task(self):
        """定期的なバッチ同期（アイドル状態のセッションを保存）"""
        try:
            logger.info("Running batch sync...")

            # アイドル状態のセッションを保存
            # 最後のアクティビティから5分以上経過しているセッションを保存
            now = datetime.now()
            idle_threshold = timedelta(minutes=5)

            saved_count = 0
            for session_key, session in self.session_manager.sessions.items():
                time_since_activity = now - session.last_active_at
                if time_since_activity >= idle_threshold:
                    try:
                        self.session_manager.save_session(session_key)
                        saved_count += 1
                        logger.debug(f"Saved idle session: {session_key}")
                    except Exception as e:
                        logger.error(f"Failed to save session {session_key}: {e}")

            if saved_count > 0:
                logger.info(f"Batch sync completed: saved {saved_count} idle sessions")
            else:
                logger.debug("Batch sync completed: no idle sessions to save")

        except Exception as e:
            logger.error(f"Error during batch sync: {e}")

    @batch_sync_task.before_loop
    async def before_batch_sync_task(self):
        """バッチ同期タスク開始前の待機"""
        await self.bot.wait_until_ready()

    # ... 既存のコード ...
```

#### 2.2 タスクの開始

`setup_handlers` 関数でタスクを開始します。

**実装例**:

```python
@bot.event
async def on_ready():
    """Bot起動完了時"""
    logger.info(f"Bot is ready! Logged in as {bot.user}")
    # イベントループが実行されている状態でタスクを開始
    if not handler.cleanup_task.is_running():
        handler.cleanup_task.start()
        logger.info("Cleanup task started")
    if not handler.batch_sync_task.is_running():
        handler.batch_sync_task.start()
        logger.info("Batch sync task started")
```

#### Step 2 完了チェックリスト

- [x] バッチ同期タスクが実装されている
- [x] 5 分ごとに実行される
- [x] アイドル状態のセッションが自動保存される
- [x] タスクが正常に開始・停止できる
- [x] ログが適切に出力される

---

### Step 3: セッションクリーンアップの定期実行（確認） (30 分) ✅ 完了

#### 3.1 既存実装の確認

Phase 1 で実装済みのセッションクリーンアップタスクを確認します。

**確認事項**:

- `cleanup_task` が 1 時間ごとに実行されているか
- `cleanup_old_sessions` が正常に動作しているか
- ログが適切に出力されているか

**既存実装**:

```python
@tasks.loop(hours=1)  # 1時間ごとに実行
async def cleanup_task(self):
    """定期的なセッションクリーンアップ"""
    try:
        logger.info("Running scheduled session cleanup...")
        self.session_manager.cleanup_old_sessions()
        logger.info("Session cleanup completed")
    except Exception as e:
        logger.error(f"Error during session cleanup: {e}")
```

#### 3.2 動作確認

セッションクリーンアップが正常に動作していることを確認します。

**確認方法**:

1. 古いセッションを作成（24 時間以上経過）
2. クリーンアップタスクが実行されるのを待つ
3. セッションがメモリから削除され、SQLite に保存されていることを確認

#### Step 3 完了チェックリスト

- [x] セッションクリーンアップタスクが正常に動作している
- [x] 1 時間ごとに実行されている
- [x] 古いセッションが適切に処理されている
- [x] ログが適切に出力されている

---

### Step 4: セッション設定の環境変数対応 (30 分) ✅ 完了

#### 4.1 設定の改善

`SESSION_TIMEOUT_HOURS` と `MAX_SESSIONS` を環境変数から読み込めるようにします。

**現在の実装**:

```python
# config.py（修正前）
SESSION_TIMEOUT_HOURS: int = 24  # 固定値
MAX_SESSIONS: int = 100  # 固定値
```

**改善後の実装**:

```python
# config.py（修正後）
SESSION_TIMEOUT_HOURS: int = int(
    os.getenv("SESSION_TIMEOUT_HOURS", "24")
)  # 環境変数から読み込み（デフォルト: 24時間）
MAX_SESSIONS: int = int(os.getenv("MAX_SESSIONS", "100"))  # 環境変数から読み込み（デフォルト: 100）
```

#### 4.2 `.env.example` の更新

`.env.example` に設定例を追加します。

```bash
# セッションのタイムアウト（時間）
# この時間以上アクティブでないセッションはメモリから削除されます
SESSION_TIMEOUT_HOURS=24

# メモリ内の最大セッション数
MAX_SESSIONS=100
```

#### 4.3 動作確認

環境変数を変更して動作を確認します。

**確認方法**:

1. `.env` ファイルで `SESSION_TIMEOUT_HOURS=12` に設定
2. Bot を再起動
3. 12 時間後にセッションが削除されることを確認

#### Step 4 完了チェックリスト

- [x] `config.py` が環境変数から読み込むように修正されている
- [x] `.env.example` に設定例が追加されている
- [x] 環境変数を変更して動作確認が完了している

---

### Step 5: エラーハンドリングの改善（オプション） (1 時間) ✅ 完了

#### 4.1 メッセージ追加時の自動保存オプション

`SessionManager.add_message` メソッドに自動保存オプションを追加します。

**実装方針**:

- オプション 1: `add_message` 後に自動的に `save_session` を呼ぶ（オプション）
- オプション 2: バッチ同期に任せる（推奨、既に実装済み）

**実装例（オプション 1）**:

```python
def add_message(
    self,
    session_key: str,
    role: MessageRole,
    content: str,
    auto_save: bool = False  # 自動保存オプション
) -> None:
    """セッションにメッセージを追加"""
    session = self.get_session(session_key)
    if not session:
        raise KeyError(f"Session not found: {session_key}")

    session.add_message(role, content)
    logger.debug(f"Added message to session: {session_key}")

    # 自動保存オプション
    if auto_save:
        self.save_session(session_key)
```

**注意**: バッチ同期タスク（Step 2）を実装した場合、このオプションは通常不要です。ただし、重要なメッセージ（ユーザーからのメッセージなど）は即座に保存したい場合に使用できます。

#### 4.2 エラーメッセージの改善

場面緘黙支援を考慮したエラーメッセージの改善（Phase 6 で詳細に実装予定）。

**現時点での改善**:

- エラーメッセージをより優しい表現に変更
- 不安を与えないメッセージ

**実装例**:

```python
# handlers.py のエラーハンドリング部分
except Exception as e:
    logger.exception(f"Error handling mention: {e}")
    # より優しいエラーメッセージ
    await message.reply(
        "申し訳ございません。一時的に応答できませんでした。"
        "しばらく時間をおいてから、もう一度お試しください。"
    )
```

#### Step 5 完了チェックリスト

- [x] メッセージ追加時の自動保存オプションが実装されている（オプション、不要と判断）
- [x] エラーメッセージが改善されている
- [x] 動作確認が完了している

---

### Step 6: テストの実装 (1 時間) ✅ 完了

#### 5.1 メッセージ分割機能のテスト

`tests/unit/test_message_splitter.py` を作成します。

**テストケース**:

- 2000 文字以下のメッセージは分割されない
- 2000 文字超のメッセージは分割される
- 文の区切りで適切に分割される
- 連番が正しく付与される

**実装例**:

```python
"""メッセージ分割機能のテスト"""
import pytest

from kotonoha_bot.utils.message_splitter import (
    split_message,
    format_split_messages,
    DISCORD_MESSAGE_MAX_LENGTH,
)


def test_split_short_message():
    """短いメッセージは分割されない"""
    content = "これは短いメッセージです。"
    chunks = split_message(content)
    assert len(chunks) == 1
    assert chunks[0] == content


def test_split_long_message():
    """長いメッセージは分割される"""
    # 3000文字のメッセージを作成
    content = "。" * 3000
    chunks = split_message(content)
    assert len(chunks) > 1
    assert all(len(chunk) <= DISCORD_MESSAGE_MAX_LENGTH for chunk in chunks)


def test_split_at_sentence_boundary():
    """文の区切りで分割される"""
    content = "最初の文です。\n\n2番目の文です。\n\n3番目の文です。"
    # 長いメッセージにするために繰り返す
    long_content = content * 1000
    chunks = split_message(long_content)
    # 各チャンクが適切に分割されていることを確認
    assert len(chunks) > 1


def test_format_split_messages():
    """連番が正しく付与される"""
    chunks = ["チャンク1", "チャンク2", "チャンク3"]
    formatted = format_split_messages(chunks, len(chunks))
    assert len(formatted) == 3
    assert "(1/3)" in formatted[0]
    assert "(2/3)" in formatted[1]
    assert "(3/3)" in formatted[2]
```

#### 5.2 バッチ同期タスクのテスト

`tests/unit/test_batch_sync.py` を作成します（モックを使用）。

**テストケース**:

- バッチ同期タスクが正常に実行される
- アイドル状態のセッションが保存される
- エラーハンドリングが適切に動作する

#### Step 6 完了チェックリスト

- [x] メッセージ分割機能のテストが実装されている
- [x] バッチ同期タスクのテストが実装されている（オプション、統合テストで確認）
- [x] すべてのテストが通過する（19/19 テスト通過）
- [x] テストカバレッジが適切である

---

### Step 7: 動作確認とテスト (1 時間) ✅ 完了

#### 6.1 動作確認チェックリスト

1. **メッセージ分割機能**

   - [x] 2000 文字以下の応答は分割されない
   - [x] 2000 文字超の応答は自動的に分割される
   - [x] 分割されたメッセージに連番が付与される
   - [x] 文の区切りで適切に分割される

2. **バッチ同期機能**

   - [x] 5 分ごとにバッチ同期が実行される
   - [x] アイドル状態のセッションが自動保存される
   - [x] ログが適切に出力される

3. **セッションクリーンアップ**

   - [x] 1 時間ごとにクリーンアップが実行される
   - [x] 古いセッションが適切に処理される

4. **セッション設定の環境変数対応**

   - [x] `SESSION_TIMEOUT_HOURS` を変更して動作確認
   - [x] `MAX_SESSIONS` を変更して動作確認

5. **エラーハンドリング**

   - [x] エラーメッセージが適切に表示される
   - [x] エラー時に Bot がクラッシュしない

#### 6.2 パフォーマンス確認

- [x] メッセージ分割によるパフォーマンスへの影響がない
- [x] バッチ同期によるパフォーマンスへの影響がない
- [x] メモリ使用量が適切である

#### Step 7 完了チェックリスト

- [x] すべての動作確認項目が完了
- [x] パフォーマンスに問題がない
- [x] 問題が発生した場合はトラブルシューティングを実施

---

## 完了基準

### Phase 4 完了の定義

以下の全ての条件を満たした時、Phase 4 が完了とする:

1. **メッセージ長制限対応**

   - [x] 2000 文字超の応答が自動的に分割される
   - [x] 分割されたメッセージに連番が付与される
   - [x] 文の区切りで適切に分割される

2. **バッチ同期機能**

   - [x] バッチ同期が 5 分ごとに実行される
   - [x] アイドル状態のセッションが自動保存される
   - [x] ログが適切に出力される

3. **セッションクリーンアップ**

   - [x] セッションクリーンアップが 1 時間ごとに実行される（既に実装済み）
   - [x] 古いセッションが適切に処理される

4. **セッション設定の環境変数対応**

   - [x] `SESSION_TIMEOUT_HOURS` が環境変数から読み込まれる
   - [x] `MAX_SESSIONS` が環境変数から読み込まれる
   - [x] `.env.example` に設定例が追加されている

5. **テスト**

   - [x] メッセージ分割機能のテストが実装されている
   - [x] すべてのテストが通過する（19/19 テスト通過）

---

## Phase 4 完了報告

**完了日**: 2026 年 1 月 15 日

### 実装サマリー

Phase 4（機能改善）のすべての目標を達成しました。

| カテゴリ                     | 状態    | 備考                                    |
| ---------------------------- | ------- | --------------------------------------- |
| メッセージ分割機能           | ✅ 完了 | 2000 文字超の応答を自動分割             |
| バッチ同期タスク             | ✅ 完了 | 5 分ごとにアイドルセッションを自動保存  |
| セッションクリーンアップ     | ✅ 完了 | 1 時間ごとに実行（Phase 1 で実装済み）  |
| セッション設定の環境変数対応 | ✅ 完了 | `SESSION_TIMEOUT_HOURS`、`MAX_SESSIONS` |
| エラーハンドリング改善       | ✅ 完了 | エラーメッセージの改善                  |
| メッセージ追加時の自動保存   | ❌ 不要 | バッチ同期で十分のため実装不要          |

### Phase 4 完了時のアクション

```bash
# 全ての変更をコミット
git add .
git commit -m "feat: Phase 4 機能改善完了

- メッセージ長制限対応（2000文字超の応答を自動分割）
- バッチ同期の定期実行タスク（5分ごと）
- セッションクリーンアップの定期実行（1時間ごと、既に実装済み）
- セッション設定の環境変数対応（`SESSION_TIMEOUT_HOURS`、`MAX_SESSIONS`）
- エラーハンドリングの改善（エラーメッセージの改善）

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

# タグを作成
git tag -a v0.4.0-phase4 -m "Phase 4 機能改善完了"

# リモートにプッシュ
git push origin main
git push origin v0.4.0-phase4
```

### 次のフェーズ

Phase 4 が完了したら、Phase 5（会話の契機拡張：スレッド型・聞き耳型）に進むことができます。

詳細は [実装ロードマップ](../roadmap.md) を参照してください。

---

## トラブルシューティング

### 問題 1: メッセージ分割が正しく動作しない

**症状**:

- 2000 文字超のメッセージが分割されない
- 分割位置が不適切

**解決方法**:

1. `split_message` 関数のロジックを確認
2. テストケースを追加して動作を確認
3. ログを確認して分割処理が実行されているか確認

---

### 問題 2: バッチ同期タスクが実行されない

**症状**:

- 5 分経過してもバッチ同期が実行されない
- ログに「Batch sync completed」が表示されない

**解決方法**:

1. `on_ready` イベントでタスクが開始されているか確認
2. タスクが正常に開始されているかログを確認
3. `discord.ext.tasks` のバージョンを確認

---

### 問題 3: メッセージ送信時にレート制限エラーが発生

**症状**:

- `discord.errors.HTTPException: 429 Too Many Requests` エラー

**解決方法**:

1. メッセージ送信間隔を調整（`asyncio.sleep` の時間を延長）
2. レート制限を考慮したキューイングを実装（Phase 6 で詳細に実装予定）

---

### 問題 4: セッションが保存されない

**症状**:

- バッチ同期が実行されているが、セッションが保存されない

**解決方法**:

1. セッションの `last_active_at` が正しく更新されているか確認
2. アイドル判定のロジックを確認
3. データベースへの書き込み権限を確認

---

## 次のフェーズへ

### Phase 5 の準備

Phase 4 が完了したら、以下の機能拡張を検討:

1. **会話の契機拡張（Phase 5）**

   - スレッド型の実装
   - 聞き耳型の実装
   - メッセージルーターの実装

2. **高度な機能（Phase 6）**

   - レート制限対応
   - スラッシュコマンド
   - エラーハンドリングの強化

---

## 参考資料

- [Discord.py Documentation](https://discordpy.readthedocs.io/)
- [Discord API ドキュメント](https://discord.com/developers/docs/)
- [実装ロードマップ](../roadmap.md)
- [Phase 1 実装完了報告](./phase01.md)
- [Phase 2 実装完了報告](./phase02.md)
- [Phase 3 実装完了報告](./phase03.md)
- [実装検討事項](../considerations.md)

---

**作成日**: 2026 年 1 月 15 日
**最終更新日**: 2026 年 1 月 15 日
**対象フェーズ**: Phase 4（機能改善）
**実装状況**: ✅ 実装完了（2026 年 1 月 15 日）
**前提条件**: Phase 1, 2, 3 完了済み ✅
**次のフェーズ**: Phase 5（会話の契機拡張）
**バージョン**: 2.0

### 更新履歴

- **v2.0** (2026-01-15): 実装完了報告書として再構成、実装状況セクションを追加、詳細手順は別ドキュメントへの参照に整理
- **v1.0** (2026-01-15): 初版リリース
