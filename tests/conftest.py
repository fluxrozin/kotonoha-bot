"""pytest フィクスチャ"""

import logging
import os
import tempfile
from pathlib import Path

import pytest

# テスト環境ではログファイルを無効化（main.pyのインポート前に設定）
if "LOG_FILE" not in os.environ:
    os.environ["LOG_FILE"] = ""

from kotonoha_bot.db.sqlite import SQLiteDatabase
from kotonoha_bot.session.manager import SessionManager


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """テスト環境のセットアップ（テストセッション開始時に実行）"""
    # 既存のログハンドラーをクリーンアップ
    for handler in logging.root.handlers[:]:
        if hasattr(handler, "close"):
            handler.close()
        logging.root.removeHandler(handler)

    yield

    # テスト終了後にログハンドラーをクリーンアップ
    for handler in logging.root.handlers[:]:
        if hasattr(handler, "close"):
            handler.close()
        logging.root.removeHandler(handler)


@pytest.fixture
def temp_db_path():
    """一時的なデータベースパス"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    yield db_path
    db_path.unlink(missing_ok=True)


@pytest.fixture
def db(temp_db_path):
    """SQLite データベースのフィクスチャ"""
    return SQLiteDatabase(db_path=temp_db_path)


@pytest.fixture
def session_manager(temp_db_path):
    """SessionManager のフィクスチャ"""
    # 一時的なデータベースを使用
    # SessionManager の初期化前にデータベースパスを設定する必要があるため、
    # 一時的なデータベースインスタンスを作成してから SessionManager に渡す
    temp_db = SQLiteDatabase(db_path=temp_db_path)
    manager = SessionManager()
    # データベースインスタンスを置き換え
    manager.db = temp_db
    # セッション辞書をクリア（_load_active_sessions で読み込まれたセッションを削除）
    manager.sessions = {}
    return manager


@pytest.fixture(autouse=True)
def cleanup_log_handlers():
    """テスト後にログハンドラーをクリーンアップ"""
    yield
    # テスト後にすべてのログハンドラーを閉じる
    for handler in logging.root.handlers[:]:
        if hasattr(handler, "close"):
            handler.close()
        logging.root.removeHandler(handler)
