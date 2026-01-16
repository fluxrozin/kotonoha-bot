"""スレッド型ハンドラーのテスト"""

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from kotonoha_bot.bot.handlers import MessageHandler


@pytest.fixture
def mock_bot():
    """モックBot"""
    bot = MagicMock()
    bot.user = MagicMock()
    bot.user.id = 123456789
    return bot


@pytest.fixture
def mock_session_manager():
    """モックSessionManager"""
    manager = MagicMock()
    manager.get_session = MagicMock(return_value=None)
    manager.create_session = MagicMock(return_value=MagicMock())
    manager.add_message = MagicMock()
    manager.save_session = MagicMock()
    return manager


@pytest.fixture
def mock_ai_provider():
    """モックAIProvider"""
    provider = MagicMock()
    # generate_responseは非同期メソッドなのでAsyncMockを使用
    provider.generate_response = AsyncMock(return_value="テスト応答")
    provider.get_last_used_model = MagicMock(return_value="test-model")
    provider.get_rate_limit_usage = MagicMock(return_value=0.5)
    return provider


@pytest.fixture
def mock_router():
    """モックMessageRouter"""
    router = MagicMock()
    router.register_bot_thread = MagicMock()
    return router


@pytest.fixture
def mock_request_queue():
    """モックRequestQueue"""
    import asyncio

    queue = MagicMock()

    # enqueueは非同期メソッドなのでAsyncMockを使用
    # 直接処理関数を呼び出すように設定（キューを経由せずに直接実行）
    async def enqueue_side_effect(_priority, func, *args, **kwargs):
        # 直接関数を実行して結果を返す
        result = await func(*args, **kwargs)
        # Futureを作成して結果を設定
        future = asyncio.Future()
        future.set_result(result)
        return future

    queue.enqueue = AsyncMock(side_effect=enqueue_side_effect)
    return queue


@pytest.fixture
def handler(
    mock_bot, mock_session_manager, mock_ai_provider, mock_router, mock_request_queue
):
    """MessageHandlerのフィクスチャ"""
    handler = MessageHandler(mock_bot)
    handler.session_manager = mock_session_manager
    handler.ai_provider = mock_ai_provider
    handler.router = mock_router
    handler.request_queue = mock_request_queue
    return handler


@pytest.fixture
def mock_message():
    """モックメッセージ"""
    message = MagicMock()
    message.author = MagicMock()
    message.author.bot = False
    message.author.id = 987654321
    message.author.display_name = "テストユーザー"
    message.channel = MagicMock()
    message.channel.id = 111222333
    message.mentions = []
    message.content = "テストメッセージ"
    message.id = 123456789
    message.thread = None
    message.reply = AsyncMock()
    return message


@pytest.fixture
def mock_thread():
    """モックスレッド"""
    thread = MagicMock()
    thread.id = 444555666
    thread.parent_id = 111222333
    thread.name = "テストスレッド"
    thread.send = AsyncMock()
    thread.typing = MagicMock()
    thread.typing.__aenter__ = AsyncMock()
    thread.typing.__aexit__ = AsyncMock(return_value=None)
    return thread


@pytest.mark.asyncio
async def test_handle_thread_bot_message_ignored(handler, mock_message):
    """Bot自身のメッセージは無視される"""
    mock_message.author.bot = True
    await handler.handle_thread(mock_message)
    # 何も実行されないことを確認（エラーが発生しない）
    handler.session_manager.get_session.assert_not_called()


@pytest.mark.asyncio
async def test_handle_thread_create_new_thread(handler, mock_message, mock_thread):
    """メンション時に新規スレッドが作成される"""
    mock_message.mentions = [handler.bot.user]
    mock_message.content = "<@123456789> こんにちは"
    mock_message.create_thread = AsyncMock(return_value=mock_thread)

    with (
        patch("kotonoha_bot.bot.handlers.split_message") as mock_split,
        patch("kotonoha_bot.bot.handlers.format_split_messages") as mock_format,
    ):
        mock_split.return_value = ["テスト応答"]
        mock_format.return_value = ["テスト応答"]

        await handler.handle_thread(mock_message)

        # スレッドが作成されたことを確認
        mock_message.create_thread.assert_called_once()
        # スレッドが記録されたことを確認
        handler.router.register_bot_thread.assert_called_once_with(mock_thread.id)
        # セッションが作成されたことを確認
        handler.session_manager.create_session.assert_called_once()
        # メッセージが追加されたことを確認
        assert handler.session_manager.add_message.call_count == 2  # USER + ASSISTANT
        # セッションが保存されたことを確認
        handler.session_manager.save_session.assert_called_once()


@pytest.mark.asyncio
async def test_handle_thread_existing_thread(handler, mock_message, mock_thread):
    """既存スレッド内での会話継続"""
    # スレッドをチャンネルとして設定
    import discord

    # isinstanceチェックを通すため、__class__を設定
    mock_thread.__class__ = type("Thread", (discord.Thread,), {})
    mock_message.channel = mock_thread

    with (
        patch("kotonoha_bot.bot.handlers.split_message") as mock_split,
        patch("kotonoha_bot.bot.handlers.format_split_messages") as mock_format,
    ):
        mock_split.return_value = ["テスト応答"]
        mock_format.return_value = ["テスト応答"]

        await handler._process_thread_message(mock_message)

        # セッションが作成されたことを確認
        handler.session_manager.create_session.assert_called_once()
        # メッセージが追加されたことを確認
        assert handler.session_manager.add_message.call_count == 2  # USER + ASSISTANT
        # セッションが保存されたことを確認
        handler.session_manager.save_session.assert_called_once()
        # スレッド内で返信されたことを確認
        mock_message.reply.assert_called_once()


@pytest.mark.asyncio
async def test_create_thread_and_respond_thread_name_generation(
    handler, mock_message, mock_thread
):
    """スレッド名の生成が正しく動作する"""
    mock_message.mentions = [handler.bot.user]
    mock_message.content = "<@123456789> こんにちは。元気ですか？"
    mock_message.create_thread = AsyncMock(return_value=mock_thread)

    with (
        patch("kotonoha_bot.bot.handlers.split_message") as mock_split,
        patch("kotonoha_bot.bot.handlers.format_split_messages") as mock_format,
    ):
        mock_split.return_value = ["テスト応答"]
        mock_format.return_value = ["テスト応答"]

        await handler._create_thread_and_respond(mock_message)

        # スレッド名が正しく生成されたことを確認（文の区切りで切られる）
        call_args = mock_message.create_thread.call_args
        assert call_args is not None
        # kwargsからnameを取得
        if call_args.kwargs:
            thread_name = call_args.kwargs.get("name")
        elif call_args.args:
            # 位置引数の場合、nameはキーワード引数として渡される可能性がある
            thread_name = None
        else:
            thread_name = None
        assert thread_name is not None
        # 文の区切り（。）で切られていることを確認
        assert "。" not in thread_name or thread_name.split("。")[0] == thread_name


@pytest.mark.asyncio
async def test_create_thread_and_respond_default_thread_name(
    handler, mock_message, mock_thread
):
    """メンションのみの場合、デフォルトのスレッド名が使用される"""
    mock_message.mentions = [handler.bot.user]
    mock_message.content = "<@123456789>"
    mock_message.create_thread = AsyncMock(return_value=mock_thread)

    with (
        patch("kotonoha_bot.bot.handlers.split_message") as mock_split,
        patch("kotonoha_bot.bot.handlers.format_split_messages") as mock_format,
    ):
        mock_split.return_value = ["テスト応答"]
        mock_format.return_value = ["テスト応答"]

        await handler._create_thread_and_respond(mock_message)

        # デフォルトのスレッド名が使用されたことを確認
        call_args = mock_message.create_thread.call_args
        assert call_args is not None
        # kwargsからnameを取得
        thread_name = call_args.kwargs.get("name") if call_args.kwargs else None
        assert thread_name == "会話"


@pytest.mark.asyncio
async def test_create_thread_and_respond_permission_error(handler, mock_message):
    """スレッド作成権限がない場合、メンション応答型にフォールバック"""
    mock_message.mentions = [handler.bot.user]
    mock_message.content = "<@123456789> こんにちは"
    mock_message.create_thread = AsyncMock(
        side_effect=discord.errors.Forbidden(MagicMock(), "Forbidden")
    )

    # handle_mentionをモック化
    handler.handle_mention = AsyncMock()

    result = await handler._create_thread_and_respond(mock_message)

    # メンション応答型にフォールバックされたことを確認
    handler.handle_mention.assert_called_once_with(mock_message)
    # 成功として扱われることを確認
    assert result is True


@pytest.mark.asyncio
async def test_create_thread_and_respond_existing_thread(
    handler, mock_message, mock_thread
):
    """既存のスレッドがある場合、既存のスレッドを使用する"""
    mock_message.mentions = [handler.bot.user]
    mock_message.content = "<@123456789> こんにちは"
    mock_message.thread = mock_thread

    with (
        patch("kotonoha_bot.bot.handlers.split_message") as mock_split,
        patch("kotonoha_bot.bot.handlers.format_split_messages") as mock_format,
    ):
        mock_split.return_value = ["テスト応答"]
        mock_format.return_value = ["テスト応答"]

        await handler._create_thread_and_respond(mock_message)

        # 新しいスレッドが作成されなかったことを確認
        mock_message.create_thread.assert_not_called()
        # 既存のスレッドが使用されたことを確認
        handler.router.register_bot_thread.assert_called_once_with(mock_thread.id)


@pytest.mark.asyncio
async def test_handle_thread_message_session_creation(
    handler, mock_message, mock_thread
):
    """既存スレッド内でのセッション作成"""
    import discord

    mock_thread.__class__ = type("Thread", (discord.Thread,), {})
    mock_message.channel = mock_thread
    mock_message.content = "続きのメッセージ"

    # セッションが存在しない場合
    handler.session_manager.get_session.return_value = None

    with (
        patch("kotonoha_bot.bot.handlers.split_message") as mock_split,
        patch("kotonoha_bot.bot.handlers.format_split_messages") as mock_format,
    ):
        mock_split.return_value = ["テスト応答"]
        mock_format.return_value = ["テスト応答"]

        await handler._process_thread_message(mock_message)

        # セッションが作成されたことを確認
        handler.session_manager.create_session.assert_called_once()
        # セッションキーが正しいことを確認
        call_args = handler.session_manager.create_session.call_args
        assert call_args is not None
        # kwargsからsession_keyを取得
        if call_args.kwargs:
            session_key = call_args.kwargs.get("session_key")
        elif call_args.args:
            session_key = call_args.args[0] if call_args.args else None
        else:
            session_key = None
        assert session_key == f"thread:{mock_thread.id}"


@pytest.mark.asyncio
async def test_handle_thread_message_existing_session(
    handler, mock_message, mock_thread
):
    """既存スレッド内で既存セッションを使用"""
    import discord

    mock_thread.__class__ = type("Thread", (discord.Thread,), {})
    mock_message.channel = mock_thread
    mock_message.content = "続きのメッセージ"

    # 既存のセッションを返す
    existing_session = MagicMock()
    existing_session.get_conversation_history = MagicMock(return_value=[])
    handler.session_manager.get_session.return_value = existing_session

    with (
        patch("kotonoha_bot.bot.handlers.split_message") as mock_split,
        patch("kotonoha_bot.bot.handlers.format_split_messages") as mock_format,
    ):
        mock_split.return_value = ["テスト応答"]
        mock_format.return_value = ["テスト応答"]

        await handler._process_thread_message(mock_message)

        # 新しいセッションが作成されなかったことを確認
        handler.session_manager.create_session.assert_not_called()
        # 既存のセッションが使用されたことを確認
        handler.session_manager.get_session.assert_called_once_with(
            f"thread:{mock_thread.id}"
        )


@pytest.mark.asyncio
async def test_handle_thread_error_handling(handler, mock_message):
    """エラーハンドリングが正しく動作する"""
    mock_message.mentions = [handler.bot.user]
    mock_message.content = "<@123456789> こんにちは"
    mock_message.create_thread = AsyncMock(side_effect=Exception("テストエラー"))

    await handler.handle_thread(mock_message)

    # エラーメッセージが送信されたことを確認（複数回呼ばれる可能性があるため、少なくとも1回は呼ばれることを確認）
    assert mock_message.reply.call_count >= 1
    # エラーメッセージの内容を確認
    call_args = mock_message.reply.call_args
    assert call_args is not None
    error_message = call_args.args[0] if call_args.args else None
    assert error_message is not None
    assert "すみません" in error_message or "反応できませんでした" in error_message
