# 会話状態判定の LLM 判定実装

## 概要

会話の状態（ENDING, MISUNDERSTANDING, CONFLICT, ACTIVE）を判定する機能について、キーワードリストベースから LLM 判定への移行を実装しました。

## 背景

### 以前の実装（キーワードリストベース）

以前は、キーワードリストを使用して会話の状態を判定していました：

```python
# 旧実装（キーワードリストベース）
ending_indicators = [
    "これ以上", "以上です", "以上になります",
    "申し上げることはありません", "以上で", "終了", "おわり",
    "締めくくり", "以上", "以上です。"
]

misunderstanding_indicators = [
    "誤解", "勘違い", "違う", "そうではない", "間違い",
    "理解していない", "分かっていない"
]
```

**問題点**:

- 表現のバリエーションに対応できない
- 文脈を理解できない
- 誤検出が多い
- キーワードリストの保守が必要

### 新しい実装（LLM 判定）

LLM 判定を使用することで、以下の利点があります：

- **文脈理解**: キーワードだけでなく、会話の流れと雰囲気を判断
- **柔軟性**: 表現のバリエーションに対応
- **精度向上**: 誤検出を減らし、より正確な判定が可能
- **保守性**: キーワードリストの更新が不要

## 実装詳細

### 1. プロンプトファイル

`prompts/eavesdrop_conversation_state_prompt.md` を作成し、会話状態判定用のプロンプトを定義しました。

**判定すべき状態**:

- **ENDING**: 会話が終了しようとしている
- **MISUNDERSTANDING**: 参加者間の誤解が発生している
- **CONFLICT**: 対立や緊張感が高まっている
- **ACTIVE**: 会話が順調に進行している

**判定の優先順位**:

1. 最優先: 会話が終了しようとしているか（ENDING）
2. 次に重要: 参加者間の誤解が発生しているか（MISUNDERSTANDING）
3. 次に重要: 対立や緊張感が高まっているか（CONFLICT）
4. デフォルト: 会話が順調に進行している（ACTIVE）

**重要な判定基準**:

- **決めつけ的な発言**: 「あなたは〜だと思っている」「〜という前提で話している」など、
  相手の意図や考えを勝手に決めつけている発言は MISUNDERSTANDING または CONFLICT と判定
- **建設的な議論と対立の区別**: 建設的な議論は ACTIVE、対立や緊張感が高まっている場合は CONFLICT
- **話題の変化と会話終了の区別**: 単に話題が変わっただけの場合は ENDING ではない

### 2. 実装コード

`src/kotonoha_bot/eavesdrop/llm_judge.py` の `_analyze_conversation_state` メソッドを実装しました。

**実装箇所**: `src/kotonoha_bot/eavesdrop/llm_judge.py` (432-484 行目)

```python
async def _analyze_conversation_state(
    self, recent_messages: list[discord.Message]
) -> str:
    """会話の状態を分析（LLM判定を使用）

    Args:
        recent_messages: 直近のメッセージリスト

    Returns:
        会話の状態（"active", "ending", "misunderstanding", "conflict"）
    """
    if not recent_messages:
        return "active"

    # 会話ログをフォーマット（全体）
    # 会話ログの最後に最新のメッセージが含まれるため、LLMが優先的に確認できる
    conversation_log = self._format_conversation_log(recent_messages)

    # 判定用プロンプトを作成
    state_prompt = CONVERSATION_STATE_PROMPT_TEMPLATE.format(
        conversation_log=conversation_log
    )

    try:
        # 判定用 AI に問い合わせ（軽量モデルを使用）
        judge_message = Message(role=MessageRole.USER, content=state_prompt)
        response = await self.ai_provider.generate_response(
            messages=[judge_message],
            system_prompt="",
            model=self.judge_model,
            max_tokens=20,  # ENDING/MISUNDERSTANDING/CONFLICT/ACTIVE のみなので短く
        )

        # 応答を解析
        response_upper = response.strip().upper()

        # 状態を判定
        if response_upper.startswith("ENDING"):
            return "ending"
        elif response_upper.startswith("MISUNDERSTANDING"):
            return "misunderstanding"
        elif response_upper.startswith("CONFLICT"):
            return "conflict"
        else:
            # デフォルトは active
            return "active"

    except Exception as e:
        logger.error(f"Error in conversation state analysis: {e}")
        # エラー時は安全側に倒して、active として扱う
        return "active"
```

**実装の特徴**:

- **非同期処理**: `async def` を使用して非同期で実行
- **エラーハンドリング**: エラー時は安全側に倒して `"active"` を返す
- **軽量モデル**: 判定用モデル（`EAVESDROP_JUDGE_MODEL`）を使用
- **最小トークン**: 最大 20 トークン（状態名のみなので短く）

### 3. プロンプトテンプレートの読み込み

プロンプトテンプレートを読み込む処理を追加しました：

```python
CONVERSATION_STATE_PROMPT_TEMPLATE = _load_prompt_from_markdown(
    "eavesdrop_conversation_state_prompt.md"
)
```

**実装箇所**: `src/kotonoha_bot/eavesdrop/llm_judge.py` (60-62 行目)

### 4. 呼び出し元の更新

`should_respond` メソッドで、会話状態の分析を 2 回呼び出すように実装しました：

**1 回目: 会話終了チェック** (105-111 行目):

```python
# 会話の状態を判定（終了しようとしている場合は介入しない）
conversation_state = await self._analyze_conversation_state(recent_messages)
if conversation_state == "ending":
    logger.debug(
        f"Intervention blocked for channel {channel_id}: conversation is ending"
    )
    return False
```

**2 回目: 会話状態の確認** (137-144 行目):

```python
# 会話の状態を判定（LLM判定を使用）
# 場が荒れている、誤解が発生しているなどの状態を検出
conversation_state = await self._analyze_conversation_state(recent_messages)
if conversation_state in ("conflict", "misunderstanding"):
    logger.debug(
        f"Conversation state detected: {conversation_state}, "
        "proceeding to LLM judgment"
    )
    # LLM判定に任せる（場が荒れている、誤解が発生している可能性があるため）
```

**呼び出しの理由**:

- **1 回目**: 会話が終了しようとしている場合は、早期に介入をブロック
- **2 回目**: 会話の状態を確認し、`conflict` や `misunderstanding` の場合は LLM 判定に進む（介入が必要な可能性があるため）

## 使用方法

### 1. プロンプトファイルの配置

`prompts/eavesdrop_conversation_state_prompt.md` をプロジェクトルートの `prompts/` フォルダに配置します。

### 2. 環境変数の設定

判定用モデルを設定します（デフォルト: `anthropic/claude-haiku-4-5`）：

```bash
EAVESDROP_JUDGE_MODEL=anthropic/claude-haiku-4-5
```

**設定ファイル**: `src/kotonoha_bot/config.py`

```python
EAVESDROP_JUDGE_MODEL: str = os.getenv(
    "EAVESDROP_JUDGE_MODEL", "anthropic/claude-haiku-4-5"
)
```

### 3. 実装の確認

`src/kotonoha_bot/eavesdrop/llm_judge.py` の `_analyze_conversation_state` メソッドが正しく実装されているか確認します。

## パフォーマンス

### トークン消費

- **判定用モデル**: 軽量モデル（`EAVESDROP_JUDGE_MODEL`）を使用
- **最大トークン数**: 20（ENDING/MISUNDERSTANDING/CONFLICT/ACTIVE のみなので短く）
- **呼び出し頻度**: メッセージが送られるたびに実行される可能性がある（`should_respond` メソッド内で 2 回呼び出される可能性がある）

### エラーハンドリング

エラー時は安全側に倒して `"active"` を返します。これにより、エラーが発生しても会話の進行を妨げません。

**エラー時の動作**:

```python
except Exception as e:
    logger.error(f"Error in conversation state analysis: {e}")
    # エラー時は安全側に倒して、active として扱う
    return "active"
```

## 判定結果の使用

### 1. 会話終了の判定

`should_respond` メソッドの最初で、会話が終了しようとしている場合は介入をブロックします：

```python
conversation_state = await self._analyze_conversation_state(recent_messages)
if conversation_state == "ending":
    return False  # 介入しない
```

### 2. 会話状態の確認

会話の状態が `conflict` や `misunderstanding` の場合は、LLM 判定に進みます（介入が必要な可能性があるため）：

```python
conversation_state = await self._analyze_conversation_state(recent_messages)
if conversation_state in ("conflict", "misunderstanding"):
    # LLM判定に任せる（場が荒れている、誤解が発生している可能性があるため）
    pass
```

## 改善点

### 実装済み

- ✅ LLM 判定による会話状態の分析
- ✅ プロンプトファイルの分離
- ✅ エラーハンドリングの実装
- ✅ 非同期処理の実装
- ✅ 決めつけ的な発言の判定
- ✅ 建設的な議論と対立の区別

### 今後の改善案

- **キャッシュ機能**: 同じ会話ログの組み合わせで短時間内はキャッシュから取得
- **判定精度の向上**: プロンプトの最適化
- **ログの追加**: 判定結果をログに記録し、精度を測定
- **呼び出し回数の最適化**: 同じメッセージに対して 2 回呼び出すのを避ける（キャッシュ機能の実装）

## 関連ドキュメント

- [聞き耳型介入機能 詳細仕様書](../specifications/eavesdrop-specification.md)
- [「同じ会話」の定義](./conversation_definition.md)
- [Phase 5 実装計画](./phases/phase5.md)

## 変更履歴

- **2025-01-15**: LLM 判定による会話状態判定を実装
  - キーワードリストベースから LLM 判定に移行
  - プロンプトファイル `eavesdrop_conversation_state_prompt.md` を追加
  - `_analyze_conversation_state` メソッドを非同期処理に変更
- **2026-01**: 現在の実装に基づいて改訂
  - 実装コードの詳細を追加
  - 呼び出し元の更新内容を追加
  - 判定結果の使用方法を追加

---

**作成日**: 2025 年 1 月 15 日  
**最終更新日**: 2026 年 1 月（現在の実装に基づいて改訂）  
**実装状況**: ✅ 実装完了
