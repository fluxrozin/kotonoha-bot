# ADR-0006: aiosqlite への移行

**ステータス**: Accepted

**日付**: 2026-01-15

**実装完了日**: 2026-01-15

**決定者**: kotonoha-bot 開発チーム

## コンテキスト

現在の実装では、Python 標準ライブラリの `sqlite3` を使用して SQLite
データベースにアクセスしています。しかし、`sqlite3` は**同期的（Sync）**な
ライブラリであり、非同期処理を前提とする Discord Bot では以下の問題が発生します:

1. **Bot 全体のブロッキング**: DB 操作中に Bot 全体の動き（他の人への返信など）が完全に止まる
2. **パフォーマンスの低下**: 複数のメッセージが同時に来た場合、順番に処理される（並行処理ができない）
3. **非同期処理の利点が活かせない**: Discord.py の非同期イベントハンドラーから同期的な DB 操作を呼び出すと、イベントループがブロックされる

### 現在の実装状況

- `src/kotonoha_bot/db/sqlite.py`: 標準の `sqlite3` を使用
- `src/kotonoha_bot/session/manager.py`: 同期的な DB 操作を非同期イベントハンドラーから呼び出している
- `src/kotonoha_bot/bot/handlers.py`: `batch_sync_task` などの非同期タスクから同期的な DB 操作を呼び出している

### 影響範囲

以下のメソッドが同期的な DB 操作を使用しています:

- `SQLiteDatabase.save_session()`: セッション保存
- `SQLiteDatabase.load_session()`: セッション読み込み
- `SQLiteDatabase.load_all_sessions()`: 全セッション読み込み
- `SQLiteDatabase.delete_session()`: セッション削除

これらは以下の非同期コンテキストから呼び出されています:

- `on_message` イベントハンドラー
- `on_thread_update` イベントハンドラー
- `cleanup_task` (1 時間ごと)
- `batch_sync_task` (5 分ごと)

## 決定

**`aiosqlite` ライブラリへの移行**を実施する。

### 移行方針

1. **依存関係の追加**: `pyproject.toml` に `aiosqlite` を追加
2. **`SQLiteDatabase` クラスの非同期化**: すべてのメソッドを `async def` に変更
3. **`SessionManager` クラスの非同期化**: DB 操作を呼び出すメソッドを `async def` に変更
4. **呼び出し元の修正**: すべての呼び出し箇所で `await` を追加

## 理由

### 1. 非同期処理との整合性

- Discord Bot は非同期処理を前提としている
- `aiosqlite` を使用することで、DB 操作中も他のイベントを処理できる
- イベントループがブロックされない

### 2. パフォーマンスの向上

- 複数の DB 操作を並行して実行できる
- 他の処理（メッセージ送信、API 呼び出しなど）と並行して DB 操作を実行できる
- レスポンス時間の改善が期待できる

### 3. プロの Discord Bot 開発の定石

- 非同期処理が必要なアプリケーションでは、非同期対応のライブラリを使用するのが標準
- 同期的な DB 操作はアンチパターンとされる

### 4. 軽量で手軽

- `aiosqlite` は軽量なライブラリ（追加の依存関係が少ない）
- SQLite の機能をそのまま使用できる
- 既存の SQL クエリをそのまま使用できる

## 代替案

### 代替案 A: 現状維持（`sqlite3` のまま）

**メリット**:

- 追加の依存関係が不要
- 実装変更が不要

**デメリット**:

- Bot 全体がブロックされる問題が解決しない
- パフォーマンスが低下する
- 非同期処理の利点が活かせない
- プロの開発手法に反する

**採用しなかった理由**:

- **パフォーマンスとユーザー体験を優先**
- 非同期処理が必要なアプリケーションでは必須

---

### 代替案 B: `asyncio.to_thread()` でラップ

**メリット**:

- 既存のコードを大きく変更せずに済む
- 追加の依存関係が不要

**デメリット**:

- スレッドプールのオーバーヘッドが発生
- パフォーマンスが `aiosqlite` より劣る
- スレッドセーフティの問題が発生する可能性
- 実装が複雑になる

**採用しなかった理由**:

- **`aiosqlite` の方がシンプルで高性能**
- スレッドプールのオーバーヘッドを避けたい

---

### 代替案 C: PostgreSQL + `asyncpg`

**メリット**:

- 本格的な非同期データベース
- 高いスケーラビリティ
- マルチサーバー対応可能

**デメリット**:

- セットアップが複雑（別プロセスが必要）
- Synology NAS 上での運用が煩雑
- リソース消費が大きい
- 小規模プロジェクトには over-engineering

**採用しなかった理由**:

- **シンプルさを優先**（ADR-0003 の決定を維持）
- SQLite で十分な機能を提供
- 将来的にスケールが必要になった場合に移行を検討

---

## 結果

### メリット

1. **非同期処理との整合性**: イベントループがブロックされない
2. **パフォーマンスの向上**: 並行処理が可能になる
3. **レスポンス時間の改善**: DB 操作中も他の処理を実行できる
4. **プロの開発手法**: 非同期処理が必要なアプリケーションでは標準的な実装

### デメリット

1. **依存関係の追加**: `aiosqlite` を追加する必要がある
2. **実装変更の必要**: 既存のコードを修正する必要がある
3. **テストの更新**: テストコードも非同期対応が必要

### トレードオフ

- **シンプルさ vs パフォーマンス**: パフォーマンスを優先し、軽量な `aiosqlite` を採用
- **実装コスト vs 長期的なメリット**: 短期的な実装コストを払って、長期的なパフォーマンスと保守性を向上

### 実装への影響

#### 1. 依存関係の追加

`pyproject.toml` に追加:

```toml
dependencies = [
    # ... 既存の依存関係 ...
    "aiosqlite>=0.20.0",
]
```

#### 2. `SQLiteDatabase` クラスの変更

**変更前**:

```python
import sqlite3

class SQLiteDatabase:
    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(...)
        return conn

    def save_session(self, session: ChatSession) -> None:
        with self._get_connection() as conn:
            # ...
```

**変更後**:

```python
import aiosqlite

class SQLiteDatabase:
    async def _get_connection(self) -> aiosqlite.Connection:
        conn = await aiosqlite.connect(str(self.db_path))
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        await conn.execute("PRAGMA busy_timeout=30000")
        return conn

    async def save_session(self, session: ChatSession) -> None:
        async with await self._get_connection() as conn:
            # ...
            await conn.commit()
```

#### 3. `SessionManager` クラスの変更

**変更前**:

```python
class SessionManager:
    def save_session(self, session_key: str) -> None:
        self.db.save_session(session)
```

**変更後**:

```python
class SessionManager:
    async def save_session(self, session_key: str) -> None:
        await self.db.save_session(session)
```

#### 4. 呼び出し元の修正

**変更前**:

```python
async def batch_sync_task(self):
    self.session_manager.save_session(session_key)
```

**変更後**:

```python
async def batch_sync_task(self):
    await self.session_manager.save_session(session_key)
```

#### 5. 初期化処理の変更

**変更前**:

```python
def __init__(self):
    self.db = SQLiteDatabase()
    self._load_active_sessions()  # 同期的
```

**変更後**:

```python
def __init__(self):
    self.db = SQLiteDatabase()
    # 非同期初期化は on_ready イベントで実行

async def _load_active_sessions(self) -> None:
    all_sessions = await self.db.load_all_sessions()
    # ...
```

### 移行手順

1. **依存関係の追加**: `pyproject.toml` に `aiosqlite` を追加
2. **`SQLiteDatabase` クラスの非同期化**: すべてのメソッドを `async def` に変更
3. **`SessionManager` クラスの非同期化**: DB 操作を呼び出すメソッドを `async def` に変更
4. **呼び出し元の修正**: すべての呼び出し箇所で `await` を追加
5. **初期化処理の修正**: 非同期初期化を `on_ready` イベントで実行
6. **テストの更新**: テストコードを非同期対応に更新
7. **動作確認**: 既存の機能が正常に動作することを確認

### 注意事項

1. **WAL モード**: `aiosqlite` でも WAL モードを使用可能（既存の設定を維持）
2. **トランザクション**: `aiosqlite` でもトランザクション処理が可能
3. **接続管理**: `aiosqlite` は接続プールを自動管理
4. **エラーハンドリング**: エラーハンドリングのロジックは基本的に同じ

### パフォーマンス目標

- DB 操作のブロッキング時間: **0ms**（非同期処理によりブロッキングなし）
- 並行 DB 操作: **可能**（複数のセッションを同時に保存可能）
- レスポンス時間の改善: **10-50ms の改善を期待**

## 参考資料

- [aiosqlite Documentation](https://aiosqlite.omnilib.dev/)
- [ADR-0003: SQLite の採用](./0003-use-sqlite.md)
- [ADR-0004: ハイブリッドセッション管理](./0004-hybrid-session-management.md)
- [database-design.md](../database-design.md)

---

**作成日**: 2026 年 1 月 15 日
**最終更新日**: 2026 年 1 月 15 日
