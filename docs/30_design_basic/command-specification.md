# コマンド・機能仕様書

## 1. スラッシュコマンド一覧

### 1.1 `/chat reset` ✅ 実装済み

**説明**: 現在の会話履歴をリセットします。新しい会話として開始できます。

**構文**:

```text
/chat reset
```

**パラメータ**: なし

**動作**:

1. 現在のセッションの会話履歴をクリア（`session.messages.clear()`）
2. メモリ内のセッションをリセット
3. SQLite に保存（`session.last_active_at` を更新）
4. 応答は ephemeral（本人のみ表示）

**対応セッションタイプ**:

- スレッド型: `thread:{thread_id}`
- DM 型: `dm:{channel_id}`
- メンション応答型: `mention:{user_id}`

**応答例**:

```text
会話履歴をリセットしました。新しい会話として始めましょう。
```

**エラー**:

- セッションが見つからない場合: "会話履歴が見つかりませんでした。"
- その他のエラー: "会話履歴のリセットに失敗しました。"

**実装状況**: ✅ Phase 6 で実装済み

**実装ファイル**: `src/kotonoha_bot/commands/chat.py`

**注意**: `/chat reset` と `!eavesdrop clear` の違いについては、
[「3.3 コマンドの違いについて」](#33-コマンドの違いについて) セクションを参照してください。

---

### 1.2 `/chat status` ✅ 実装済み

**説明**: 現在のセッション状態を表示します。

**構文**:

```text
/chat status
```

**パラメータ**: なし

**動作**:

1. セッションタイプ（メンション応答型/スレッド型/DM 型）を判定
2. セッションタイプを表示
3. 会話履歴の件数を表示
4. セッションの開始時刻を表示
5. 応答は ephemeral（本人のみ表示）

**対応セッションタイプ**:

- スレッド型: `thread:{thread_id}` → "スレッド型"
- DM 型: `dm:{channel_id}` → "DM 型"
- メンション応答型: `mention:{user_id}` → "メンション応答型"

**応答例**:

```text
現在のセッション情報:
- タイプ: スレッド型
- 会話履歴: 15件
- 開始時刻: 2024-01-15 10:30:00
```

**エラー**:

- セッションが見つからない場合: "セッションが見つかりませんでした。"
- その他のエラー: "セッション状態の取得に失敗しました。"

**実装状況**: ✅ Phase 6 で実装済み

**実装ファイル**: `src/kotonoha_bot/commands/chat.py`

---

### 1.3 `/settings` ❌ 未実装

**説明**: Bot の設定を表示・変更します（将来の拡張）。

**構文**:

```text
/settings [key:文字列] [value:文字列]
```

**パラメータ**:

- `key` (オプション): 設定キー
- `value` (オプション): 設定値

**動作**:

- パラメータなし: 現在の設定を表示
- `key` のみ: 指定された設定値を表示
- `key` と `value`: 設定値を変更

**応答例**:

```text
現在の設定:
- 応答温度: 0.7
- 最大トークン数: 2048
```

**実装状況**: ❌ 未実装（Phase 8 で実装予定）

**注意**: 現在は環境変数で設定を管理しています。

---

## 2. メンションコマンド

### 2.1 `@Kotonoha [メッセージ]`

**説明**: Bot にメンションして会話を開始します。

**動作**:

- **メンション応答型**: メンションされたメッセージに応答（セッションキー: `mention:{user_id}`）
- **スレッド型**: メンションされたメッセージを起点にスレッドを作成して応答（セッションキー: `thread:{thread_id}`）

**応答**: AI が生成した自然な応答

**実装状況**: ✅ Phase 1（メンション応答型）、Phase 5（スレッド型）で実装済み

**実装ファイル**: `src/kotonoha_bot/bot/handlers.py`

---

## 3. プレフィックスコマンド（開発用）

### 3.1 `!eavesdrop clear` ✅ 実装済み

**説明**: 聞き耳型の会話ログバッファをクリアします（開発・デバッグ用）。

**構文**:

```text
!eavesdrop clear
```

**パラメータ**: なし

**動作**:

1. 現在のチャンネルの会話ログバッファ（`ConversationBuffer`）をクリア
2. 聞き耳型が会話に参加するかどうかを判断するために使用する一時的なメッセージバッファを削除

**応答例**:

```text
✅ 会話ログバッファをクリアしました。
```

**実装状況**: ✅ Phase 5 で実装済み

**実装ファイル**: `src/kotonoha_bot/bot/handlers.py` の `eavesdrop_command`

**注意**: このコマンドは開発・デバッグ用です。通常のユーザーは使用する必要はありません。

**詳細**: `/chat reset` との違いについては、[「3.3 コマンドの違いについて」](#33-コマンドの違いについて) セクションを参照してください。

---

### 3.2 `!eavesdrop status` ✅ 実装済み

**説明**: 現在のチャンネルの会話ログバッファの状態を表示します（開発・デバッグ用）。

**構文**:

```text
!eavesdrop status
```

**パラメータ**: なし

**動作**:

1. 現在のチャンネルのバッファに保存されているメッセージ数を表示
2. バッファの最大サイズを表示（`EAVESDROP_BUFFER_SIZE`、デフォルト: 20 件）

**応答例**:

```text
📊 現在のバッファ状態:
- メッセージ数: 15件
- 最大サイズ: 20件
```

**実装状況**: ✅ Phase 5 で実装済み

**実装ファイル**: `src/kotonoha_bot/bot/handlers.py` の `eavesdrop_command`

**注意**: このコマンドは開発・デバッグ用です。通常のユーザーは使用する必要はありません。

---

### 3.3 コマンドの違いについて

`/chat reset` と `!eavesdrop clear` は、**異なるデータ構造を操作する別々のコマンド**です。混同しやすいため、ここで詳しく説明します。

#### 基本的な違い

| 項目               | `/chat reset`                                  | `!eavesdrop clear`                           |
| ------------------ | ---------------------------------------------- | -------------------------------------------- |
| **コマンド形式**   | スラッシュコマンド（`/chat reset`）            | プレフィックスコマンド（`!eavesdrop clear`） |
| **対象ユーザー**   | 一般ユーザー向け                               | 開発・デバッグ用                             |
| **操作するデータ** | `ChatSession.messages`（セッションの会話履歴） | `ConversationBuffer`（会話ログバッファ）     |
| **データ構造**     | `ChatSession`（セッション管理）                | `ConversationBuffer`（一時バッファ）         |
| **適用範囲**       | 全タイプ（メンション/スレッド/DM/聞き耳型）    | 聞き耳型のみ                                 |
| **永続化**         | SQLite に保存される                            | メモリのみ（永続化されない）                 |
| **影響範囲**       | Bot との会話履歴全体                           | 聞き耳型の判定用バッファのみ                 |

#### `/chat reset` の詳細

**操作内容**:

```python
# セッションの会話履歴をクリア
session.messages.clear()  # ChatSession の messages リストを空にする
session.last_active_at = datetime.now()
self.handler.session_manager.save_session(session_key)  # SQLite に保存
```

**影響**:

- Bot との会話履歴（`ChatSession.messages`）がクリアされる
- セッション自体は残るが、会話の記憶が消える
- 次回のメッセージから新しい会話として開始される
- SQLite に保存されるため、Bot 再起動後もリセット状態が保持される

**使用例**:

```txt
スレッド内での会話:
ユーザー: 「Pythonについて教えて」
Bot: 「Pythonは...」
ユーザー: 「JavaScriptについて教えて」
Bot: 「JavaScriptは...」

/chat reset を実行
→ 会話履歴がクリアされる
→ 次回のメッセージから新しい会話として開始
→ Botは以前の会話を覚えていない
```

#### `!eavesdrop clear` の詳細

**操作内容**:

```python
# 会話ログバッファをクリア
handler.conversation_buffer.clear(ctx.channel.id)  # ConversationBuffer をクリア
```

**影響**:

- 聞き耳型が会話に参加するかどうかを判断するために使用する一時的なメッセージバッファがクリアされる
- チャンネルごとの直近 20 件のメッセージを保持するバッファが削除される
- セッションの会話履歴には影響しない
- メモリのみの操作で、永続化されない

**使用例**:

```txt
チャンネル内の会話:
ユーザーA: 「今日はいい天気だね」
ユーザーB: 「そうだね」
ユーザーC: 「散歩に行こう」

!eavesdrop clear を実行
→ 会話ログバッファがクリアされる
→ 聞き耳型は「会話が少ない」と判断して参加しない可能性が高い
→ でも、Botの会話履歴（セッション）は残っている
```

#### データ構造の違い

**`ChatSession`（セッションの会話履歴）**:

```python
ChatSession(
    session_key="eavesdrop:123456789",
    session_type="eavesdrop",
    messages=[  # ← これが /chat reset でクリアされる
        Message(role="assistant", content="いい天気ですね！"),
        Message(role="user", content="そうだね"),
        ...
    ],
    ...
)
```

**`ConversationBuffer`（会話ログバッファ）**:

```python
ConversationBuffer(
    buffers={
        123456789: deque([  # ← これが !eavesdrop clear でクリアされる
            discord.Message(...),  # ユーザーAのメッセージ
            discord.Message(...),  # ユーザーBのメッセージ
            discord.Message(...),  # Botのメッセージ
            ...
        ], maxlen=20)
    }
)
```

#### 具体例: 聞き耳型のチャンネルで両方を使う場合

```txt
チャンネル内の会話:
ユーザーA: 「今日はいい天気だね」
ユーザーB: 「そうだね」
Bot: 「いい天気ですね！散歩に最適です」（聞き耳型で参加）

# この時点での状態:
# - ConversationBuffer: [ユーザーAのメッセージ, ユーザーBのメッセージ, Botのメッセージ]
# - ChatSession (eavesdrop:channel_id): [Botのメッセージ]

# ケース1: /chat reset のみ実行
/chat reset を実行
→ ChatSession.messages がクリアされる
→ ConversationBuffer はそのまま残る
→ 次回の聞き耳型判定時、バッファには古いメッセージが残っている
→ 聞き耳型は会話に参加する可能性がある

# ケース2: !eavesdrop clear のみ実行
!eavesdrop clear を実行
→ ConversationBuffer がクリアされる
→ ChatSession はそのまま残る
→ 次回の聞き耳型判定時、バッファは空なので参加しない可能性が高い
→ でも、Botの会話履歴は残っている

# ケース3: 両方実行
/chat reset を実行
!eavesdrop clear を実行
→ ChatSession.messages がクリアされる
→ ConversationBuffer がクリアされる
→ 完全にリセットされた状態になる
```

#### まとめ

- **`/chat reset`**: Bot との会話履歴（セッション）をリセットするユーザー向けコマンド
- **`!eavesdrop clear`**: 聞き耳型の判定用バッファをクリアする開発・デバッグ用コマンド

これらは**別々のデータ構造を操作するため、互いに影響しません**。両方クリアしたい場合は、両方のコマンドを実行する必要があります。

---

## 4. 機能一覧

### 4.1 会話機能

| 機能名               | 説明                           | 実装状況 | 実装 Phase | 実装ファイル                              |
| -------------------- | ------------------------------ | -------- | ---------- | ----------------------------------------- |
| **メンション応答**   | Bot がメンションされた時に応答 | ✅ 完了  | Phase 1    | `src/kotonoha_bot/bot/handlers.py`        |
| **スレッド型会話**   | スレッド内で会話を継続         | ✅ 完了  | Phase 5    | `src/kotonoha_bot/bot/handlers.py`        |
| **DM 会話**          | ダイレクトメッセージで会話     | ✅ 完了  | Phase 5    | `src/kotonoha_bot/bot/handlers.py`        |
| **聞き耳型会話**     | 自然に会話に参加               | ✅ 完了  | Phase 5    | `src/kotonoha_bot/eavesdrop/llm_judge.py` |
| **会話履歴保持**     | 会話の文脈を保持               | ✅ 完了  | Phase 1    | `src/kotonoha_bot/session/manager.py`     |
| **会話履歴リセット** | 会話履歴をクリア               | ✅ 完了  | Phase 6    | `src/kotonoha_bot/commands/chat.py`       |

### 4.2 セッション管理機能

| 機能名             | 説明                         | 実装状況 | 実装 Phase | 実装ファイル                          |
| ------------------ | ---------------------------- | -------- | ---------- | ------------------------------------- |
| **セッション作成** | 新しいセッションを作成       | ✅ 完了  | Phase 1    | `src/kotonoha_bot/session/manager.py` |
| **セッション取得** | 既存セッションを取得         | ✅ 完了  | Phase 1    | `src/kotonoha_bot/session/manager.py` |
| **セッション更新** | 会話履歴を更新               | ✅ 完了  | Phase 1    | `src/kotonoha_bot/session/manager.py` |
| **セッション保存** | SQLite に永続化              | ✅ 完了  | Phase 1    | `src/kotonoha_bot/db/sqlite.py`       |
| **セッション復元** | ボット再起動時に復元         | ✅ 完了  | Phase 1    | `src/kotonoha_bot/session/manager.py` |
| **セッション削除** | 非アクティブセッションを削除 | ✅ 完了  | Phase 4    | `src/kotonoha_bot/session/manager.py` |

### 4.3 AI 機能

| 機能名               | 説明                       | 実装状況 | 実装 Phase | 実装ファイル                              |
| -------------------- | -------------------------- | -------- | ---------- | ----------------------------------------- |
| **基本応答生成**     | Claude API で応答を生成    | ✅ 完了  | Phase 1    | `src/kotonoha_bot/ai/litellm_provider.py` |
| **モデル使い分け**   | タスクに応じてモデルを選択 | ✅ 完了  | Phase 1    | `src/kotonoha_bot/ai/litellm_provider.py` |
| **プロンプト最適化** | 場面緘黙支援向けプロンプト | ✅ 完了  | Phase 1    | `prompts/system_prompt.md`                |
| **判定機能**         | 聞き耳型の判定（Yes/No）   | ✅ 完了  | Phase 5    | `src/kotonoha_bot/eavesdrop/llm_judge.py` |
| **フォールバック**   | API エラー時の代替処理     | ✅ 完了  | Phase 1    | `src/kotonoha_bot/ai/litellm_provider.py` |

### 4.4 エラーハンドリング機能

| 機能名               | 説明                                     | 実装状況 | 実装 Phase | 実装ファイル                              |
| -------------------- | ---------------------------------------- | -------- | ---------- | ----------------------------------------- |
| **API エラー処理**   | Claude/Discord API エラー処理            | ✅ 完了  | Phase 1    | `src/kotonoha_bot/errors/`                |
| **レート制限対応**   | レート制限の監視と対応                   | ✅ 完了  | Phase 6    | `src/kotonoha_bot/rate_limit/`            |
| **リトライロジック** | エラー時の自動リトライ（指数バックオフ） | ✅ 完了  | Phase 1    | `src/kotonoha_bot/ai/litellm_provider.py` |
| **エラーメッセージ** | ユーザーフレンドリーなエラー表示         | ✅ 完了  | Phase 6    | `src/kotonoha_bot/errors/`                |

**リトライロジックの実装詳細**:

- 一時的なエラー（`InternalServerError`, `RateLimitError`）に対して自動リトライ
- 指数バックオフ（1 秒 → 2 秒 → 4 秒）
- 最大リトライ回数: 3 回（`LLM_MAX_RETRIES`で設定可能）
- HTTP 529（Overloaded）エラーに対応

### 4.5 運用機能

| 機能名             | 説明                           | 実装状況  | 実装 Phase | 実装ファイル                 |
| ------------------ | ------------------------------ | --------- | ---------- | ---------------------------- |
| **ログ出力**       | 動作ログの記録                 | ✅ 完了   | Phase 1    | `src/kotonoha_bot/main.py`   |
| **モニタリング**   | パフォーマンス監視             | ⚠️ 部分的 | Phase 8    | -                            |
| **バックアップ**   | データベースの自動バックアップ | ✅ 完了   | Phase 2    | `scripts/backup.sh`          |
| **ヘルスチェック** | システム状態の確認             | ✅ 完了   | Phase 2    | `src/kotonoha_bot/health.py` |

**注意**: モニタリング機能は部分的に実装済み（ヘルスチェック、ログ）。詳細なパフォーマンス監視は Phase 8 で実装予定。

---

## 5. 機能詳細仕様

### 5.1 会話履歴保持機能

**仕様**:

- **保持期間**: セッションがアクティブな間
- **保持件数**: メモリ内 50 件、SQLite 全件
- **保存タイミング**:
  - リアルタイム: 重要な会話
  - バッチ: 5 分ごと（`save_idle_sessions` タスク）
  - セッション終了時: 必ず保存

**データ構造**:

```python
{
    "role": "user" | "assistant" | "system",
    "content": str,
    "timestamp": datetime
}
```

**実装ファイル**: `src/kotonoha_bot/session/models.py`

### 5.2 セッション管理機能

**セッションキー形式**:

- メンション応答型: `mention:{user_id}`
- スレッド型: `thread:{thread_id}`
- DM 型: `dm:{channel_id}`
- 聞き耳型: `eavesdrop:{channel_id}`

**ライフサイクル**:

1. 新規作成: セッション開始
2. アクティブ: 最後のメッセージから 5 分以内
3. アイドル: 5 分〜24 時間経過（`SESSION_TIMEOUT_HOURS`、デフォルト: 24 時間）
4. 非アクティブ: 24 時間以上経過
5. SQLite 保存: アイドル/非アクティブ時に保存
6. 削除: 24 時間経過でメモリから削除（`cleanup_old_sessions` タスク）

**実装ファイル**: `src/kotonoha_bot/session/manager.py`

### 5.3 AI 応答生成機能

**プロンプト構造**:

```text
システムプロンプト
+ 会話履歴（直近N件）
+ ユーザーメッセージ
```

**モデル選択ロジック**:

- **デフォルト**: Claude Sonnet 4.5（`anthropic/claude-sonnet-4-5`）
- **判定用**: Claude Haiku 4.5（`anthropic/claude-haiku-4-5`）
- **フォールバック**: Claude 3 Haiku（`anthropic/claude-3-haiku-20240307`）

**応答処理**:

1. プロンプト生成
2. API 呼び出し（レート制限チェック、トークンバケット）
3. レスポンス処理
4. メッセージ長チェック（2000 文字超の場合は分割）
5. Discord に送信（Embed 形式でモデル情報とレート制限使用率を表示）

**実装ファイル**: `src/kotonoha_bot/ai/litellm_provider.py`, `src/kotonoha_bot/utils/message_splitter.py`

---

**作成日**: 2026 年 1 月 14 日  
**最終更新日**: 2026 年 1 月（現在の実装に基づいて改訂）  
**バージョン**: 2.0  
**作成者**: kotonoha-bot 開発チーム

### 更新履歴

- **v2.0** (2026-01): 現在の実装に基づいて改訂
  - `/chat reset` と `/chat status` の実装詳細を追加（DM 型対応を含む）
  - セッションキーの形式を実装に合わせて更新
  - 実装状況と実装 Phase を追加
  - 実装ファイルのパスを追加
  - 機能一覧に実装状況と実装ファイルを追加
  - `/settings` が未実装であることを明記（Phase 8 で実装予定）
  - セッション管理機能のライフサイクルを実装に合わせて更新
  - AI 応答生成機能のモデル選択ロジックを実装に合わせて更新
- **v1.1** (2026-01-15): `/chat reset` と `!eavesdrop clear` の違いについて詳しい説明を追加
- **v1.0** (2026-01-14): 初版リリース
