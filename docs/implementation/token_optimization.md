# トークン消費の最適化

## 問題点

LLM で「同じ会話かどうか」を判定する処理が、メッセージが送られるたびに実行されると、トークン消費が激しくなる可能性があります。

### 以前の実装の問題

1. **メッセージごとに LLM API を呼び出す**

   - `should_respond()`が呼ばれるたびに、`_is_same_conversation()`で LLM API を呼び出す
   - 最小間隔チェックを通った場合のみ実行されるが、それでも頻繁に呼び出される可能性がある

2. **同じ会話ログの判定を繰り返す**
   - 同じ会話ログの組み合わせで、何度も LLM 判定を行う
   - キャッシュ機能がないため、無駄な API 呼び出しが発生

## 実装された最適化

### 1. 最小間隔チェック（最優先）

**実装**:

- 最後の介入から `EAVESDROP_MIN_INTERVENTION_INTERVAL_MINUTES`
  （デフォルト: 10 分）経過していない場合は、LLM 判定をスキップ
- 早期に介入をブロックすることで、不要な LLM API 呼び出しを削減

**実装箇所**: `src/kotonoha_bot/eavesdrop/llm_judge.py`
(360-367 行目)

**効果**:

- 最小間隔内の判定では、LLM API を呼び出さない
- トークン消費を大幅に削減

```python
# 最小間隔（設定から読み込む）
min_interval_minutes = Config.EAVESDROP_MIN_INTERVENTION_INTERVAL_MINUTES
if minutes_since_last < min_interval_minutes:
    logger.debug(
        f"Intervention blocked: minimum interval not met "
        f"({minutes_since_last} < {min_interval_minutes} minutes)"
    )
    return False
```

### 2. キャッシュ機能の追加

**実装**:

- 同じ会話ログの組み合わせの判定結果をキャッシュ
- キャッシュキー: `(チャンネルID, 会話ログのハッシュ)`
- キャッシュの有効期限: 5 分

**実装箇所**: `src/kotonoha_bot/eavesdrop/llm_judge.py`

**データ構造**:

```python
# キー: (チャンネルID, 会話ログのハッシュ)
# 値: (判定結果, キャッシュ時刻)
conversation_check_cache: dict[tuple[int, str], tuple[bool, datetime]] = {}
```

**キャッシュの保存**:

```python
# 結果をキャッシュ（トークン消費を削減）
if cache_key:
    now = datetime.now()
    self.conversation_check_cache[cache_key] = (is_same, now)
    # 古いキャッシュを削除
    self._cleanup_cache(now)
```

**キャッシュキーの生成**:

```python
# 現在の会話ログを取得（最新の5メッセージ）
current_log = self._format_conversation_log(recent_messages[-5:])

# 同じ会話かどうかを判定
is_same = await self._is_same_conversation(
    previous_log=last_intervention_log,
    current_log=current_log,
    cache_key=(channel_id, hashlib.md5(current_log.encode()).hexdigest()),
)
```

**注意**: 現在の実装では、キャッシュから読み取る処理は実装されていません。キャッシュへの保存のみが実装されています。将来的にキャッシュからの読み取り機能を追加することで、さらなるトークン消費削減が期待できます。

### 3. キャッシュの自動クリーンアップ

**実装**:

- 古いキャッシュ（有効期限の 2 倍以上経過）を自動削除
- メモリ使用量を抑制

**実装箇所**: `src/kotonoha_bot/eavesdrop/llm_judge.py` (317-330 行目)

```python
def _cleanup_cache(self, now: datetime) -> None:
    """古いキャッシュを削除

    Args:
        now: 現在時刻
    """
    cutoff_time = now - timedelta(minutes=self.cache_ttl_minutes * 2)
    keys_to_delete = [
        key
        for key, (_, cached_time) in self.conversation_check_cache.items()
        if cached_time < cutoff_time
    ]
    for key in keys_to_delete:
        del self.conversation_check_cache[key]
```

## 最適化の効果

### トークン消費の削減

1. **最小間隔チェック**

   - 10 分以内の判定: **100%削減**（LLM API を呼び出さない）
   - 早期に介入をブロックすることで、不要な判定を削減

2. **キャッシュ機能（将来の拡張）**
   - 5 分以内の同じ会話ログの判定: **100%削減**（キャッシュから取得）
   - 短時間内の連続した判定を大幅に削減

### 期待される削減率

- **最小間隔チェック**: 約 50-60%削減（10 分以内の判定をスキップ）
- **キャッシュ機能（実装後）**: さらに約 20-30%削減
- **全体**: 約 60-70%のトークン消費削減を期待

## 実装の詳細

### 判定の流れ

```txt
1. 最小間隔チェック（10分）
   ↓ (通過)
2. 同じ会話判定（LLM判定）
   ↓
3. 結果をキャッシュに保存（将来の拡張用）
   ↓
4. 同じ会話の場合、会話状況の変化判定（LLM判定）
```

### キャッシュの構造

```python
# キー: (チャンネルID, 会話ログのハッシュ)
# 値: (判定結果, キャッシュ時刻)
conversation_check_cache: dict[tuple[int, str], tuple[bool, datetime]] = {}
```

### キャッシュの有効期限

- **デフォルト**: 5 分（`cache_ttl_minutes = 5`）
- **理由**: 短時間内の連続した判定を削減しつつ、会話の変化に対応できる期間
- **クリーンアップ**: 有効期限の 2 倍（10 分）以上経過したキャッシュを自動削除

### キャッシュキーの生成方法

```python
# 現在の会話ログ（最新の5メッセージ）のハッシュを生成
current_log = self._format_conversation_log(recent_messages[-5:])
cache_key = (channel_id, hashlib.md5(current_log.encode()).hexdigest())
```

## 今後の改善案

1. **キャッシュからの読み取り機能の実装**

   - `_is_same_conversation` メソッドで、キャッシュキーが提供されている場合、まずキャッシュをチェック
   - キャッシュが有効な場合は、LLM API を呼び出さずにキャッシュから結果を返す
   - これにより、短時間内の同じ会話ログの判定を大幅に削減

2. **キャッシュの有効期限の調整**

   - 環境変数で設定可能にする
   - 使用状況に応じて最適な期間を調整

3. **キャッシュサイズの制限**

   - メモリ使用量を抑制
   - LRU キャッシュの採用

4. **統計情報の収集**
   - キャッシュヒット率の追跡
   - トークン消費の削減率の測定

## 注意事項

- **最小間隔チェック**: 10 分未満の間隔では、会話状況が変わっていても介入しない
- **キャッシュ機能**: 現在は保存のみ実装されており、読み取り機能は未実装
- **キャッシュの有効期限**: 5 分は実用的なバランスを取った設定
- **会話ログのハッシュ**: 最新 5 メッセージの内容に基づいて生成されるため、同じ内容の会話ログは同じハッシュになる

## 実装状況

### 実装済み

- ✅ 最小間隔チェック（10 分）
- ✅ キャッシュへの保存機能
- ✅ キャッシュの自動クリーンアップ

### 未実装（将来の拡張）

- ⏳ キャッシュからの読み取り機能
- ⏳ キャッシュヒット率の統計
- ⏳ 環境変数によるキャッシュ有効期限の設定

## 結論

最小間隔チェックにより、トークン消費を大幅に削減できます。

- **最小間隔チェック**: 10 分以内の判定を 100%削減
- **全体**: 約 50-60%のトークン消費削減を期待

将来的にキャッシュからの読み取り機能を実装することで、さらなるトークン消費削減（約 60-70%）が期待できます。

これにより、LLM で「同じ会話かどうか」を判定する機能を、実用的なコストで運用できます。

---

**作成日**: 2026 年 1 月  
**最終更新**: 2026 年 1 月（現在の実装に基づいて改訂）  
**実装状況**: 最小間隔チェックとキャッシュ保存機能は実装済み、キャッシュ読み取り機能は未実装
