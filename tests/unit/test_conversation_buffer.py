"""会話ログバッファのテスト"""

from unittest.mock import MagicMock

import pytest

from kotonoha_bot.eavesdrop.conversation_buffer import ConversationBuffer


@pytest.fixture
def buffer():
    """会話ログバッファ"""
    return ConversationBuffer(max_size=5)


@pytest.fixture
def mock_message():
    """モックメッセージ"""
    message = MagicMock()
    message.content = "テストメッセージ"
    message.author = MagicMock()
    message.author.display_name = "テストユーザー"
    return message


def test_add_message(buffer, mock_message):
    """メッセージを追加できる"""
    channel_id = 123456789
    buffer.add_message(channel_id, mock_message)
    messages = buffer.get_recent_messages(channel_id)
    assert len(messages) == 1
    assert messages[0] == mock_message


def test_get_recent_messages_limit(buffer):
    """取得件数を制限できる"""
    channel_id = 123456789
    for i in range(10):
        msg = MagicMock()
        msg.content = f"メッセージ{i}"
        buffer.add_message(channel_id, msg)

    messages = buffer.get_recent_messages(channel_id, limit=3)
    assert len(messages) == 3


def test_buffer_max_size(buffer):
    """バッファサイズの上限が機能する"""
    channel_id = 123456789
    for i in range(10):
        msg = MagicMock()
        msg.content = f"メッセージ{i}"
        buffer.add_message(channel_id, msg)

    messages = buffer.get_recent_messages(channel_id)
    assert len(messages) == 5  # max_size


def test_get_recent_messages_empty(buffer):
    """存在しないチャンネルでは空リストが返される"""
    messages = buffer.get_recent_messages(999999999)
    assert messages == []


def test_clear(buffer, mock_message):
    """バッファをクリアできる"""
    channel_id = 123456789
    buffer.add_message(channel_id, mock_message)
    buffer.clear(channel_id)
    messages = buffer.get_recent_messages(channel_id)
    assert messages == []


def test_multiple_channels(buffer):
    """複数のチャンネルを独立して管理できる"""
    channel1 = 111111111
    channel2 = 222222222

    msg1 = MagicMock()
    msg1.content = "チャンネル1のメッセージ"
    msg2 = MagicMock()
    msg2.content = "チャンネル2のメッセージ"

    buffer.add_message(channel1, msg1)
    buffer.add_message(channel2, msg2)

    messages1 = buffer.get_recent_messages(channel1)
    messages2 = buffer.get_recent_messages(channel2)

    assert len(messages1) == 1
    assert len(messages2) == 1
    assert messages1[0].content == "チャンネル1のメッセージ"
    assert messages2[0].content == "チャンネル2のメッセージ"
