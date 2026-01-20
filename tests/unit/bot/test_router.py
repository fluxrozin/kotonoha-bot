"""メッセージルーターのテスト"""

from unittest.mock import MagicMock

import pytest

from kotonoha_bot.bot.router import MessageRouter


@pytest.fixture
def mock_bot():
    """モックBot"""
    bot = MagicMock()
    bot.user = MagicMock()
    bot.user.id = 123456789
    return bot


@pytest.fixture
def router(mock_bot):
    """メッセージルーター"""
    return MessageRouter(mock_bot)


@pytest.fixture
def mock_message():
    """モックメッセージ"""
    message = MagicMock()
    message.author = MagicMock()
    message.author.bot = False
    message.author.id = 987654321
    message.channel = MagicMock()
    message.channel.id = 111222333
    message.mentions = []
    message.content = "テストメッセージ"
    return message


@pytest.mark.asyncio
async def test_route_bot_message_ignored(router, mock_message):
    """Bot自身のメッセージは無視される"""
    mock_message.author.bot = True
    result = await router.route(mock_message)
    assert result == "none"


@pytest.mark.asyncio
async def test_route_mention_default_thread(router, mock_message):
    """メンション時、デフォルトでスレッド型が返される"""
    mock_message.mentions = [router.bot.user]
    result = await router.route(mock_message)
    assert result == "thread"


@pytest.mark.asyncio
async def test_route_mention_mention_mode(router, mock_message):
    """メンション時、スレッド型が無効ならメンション応答型が返される"""
    # 特定のチャンネルでスレッド型を有効化し、別のチャンネルでは無効にする
    router.enable_thread_for_channel(999888777)  # 別のチャンネルを有効化
    mock_message.mentions = [router.bot.user]
    mock_message.channel.id = 111222333  # 有効化されていないチャンネル

    result = await router.route(mock_message)
    # thread_enabled_channels が空でないが、このチャンネルは含まれていないため
    # _should_create_thread が False を返し、"mention" が返される
    assert result == "mention"


@pytest.mark.asyncio
async def test_route_thread_message(router, mock_message):
    """既存スレッド内のメッセージはスレッド型として処理される"""
    import discord

    # discord.Threadのモックを作成（isinstanceチェックを通すため）
    thread = MagicMock()
    # isinstance(thread, discord.Thread) を True にするため、__class__ を設定
    thread.__class__ = type("Thread", (discord.Thread,), {})
    thread.id = 444555666
    thread.parent_id = 111222333
    thread.owner_id = router.bot.user.id
    thread.owner = None
    mock_message.channel = thread
    router.register_bot_thread(thread.id)

    result = await router.route(mock_message)
    # bot_threads に登録されているため thread を返す
    assert result == "thread"


@pytest.mark.asyncio
async def test_route_eavesdrop_enabled(router, mock_message):
    """聞き耳型が有効なチャンネルでは聞き耳型が返される"""
    router.enable_eavesdrop_for_channel(mock_message.channel.id)
    result = await router.route(mock_message)
    assert result == "eavesdrop"


@pytest.mark.asyncio
async def test_route_eavesdrop_disabled(router, mock_message):
    """聞き耳型が無効なチャンネルではnoneが返される"""
    result = await router.route(mock_message)
    assert result == "none"


@pytest.mark.asyncio
async def test_register_bot_thread(router):
    """Botが作成したスレッドを記録できる"""
    thread_id = 777888999
    router.register_bot_thread(thread_id)
    assert thread_id in router.bot_threads


@pytest.mark.asyncio
async def test_enable_disable_thread_for_channel(router):
    """チャンネルごとにスレッド型を有効/無効化できる"""
    channel_id = 111222333
    router.enable_thread_for_channel(channel_id)
    assert channel_id in router.thread_enabled_channels

    router.disable_thread_for_channel(channel_id)
    assert channel_id not in router.thread_enabled_channels


@pytest.mark.asyncio
async def test_enable_disable_eavesdrop_for_channel(router):
    """チャンネルごとに聞き耳型を有効/無効化できる"""
    channel_id = 111222333
    router.enable_eavesdrop_for_channel(channel_id)
    assert channel_id in router.eavesdrop_enabled_channels

    router.disable_eavesdrop_for_channel(channel_id)
    assert channel_id not in router.eavesdrop_enabled_channels


@pytest.mark.asyncio
async def test_route_mention_with_thread_enabled_channel(router, mock_message):
    """thread_enabled_channels が設定されている場合の動作"""
    # 特定のチャンネルでスレッド型を有効化
    router.enable_thread_for_channel(mock_message.channel.id)
    mock_message.mentions = [router.bot.user]

    result = await router.route(mock_message)
    # thread_enabled_channels に含まれているため "thread" が返される
    assert result == "thread"


@pytest.mark.asyncio
async def test_is_bot_thread_with_owner_id(router):
    """owner_id でBotスレッドを判定する"""
    import discord

    thread = MagicMock()
    thread.__class__ = type("Thread", (discord.Thread,), {})
    thread.id = 444555666
    thread.owner_id = router.bot.user.id
    thread.owner = None

    # bot_threads に登録されていない場合
    result = await router._is_bot_thread(thread)
    # owner_id が一致するため True
    assert result is True


@pytest.mark.asyncio
async def test_is_bot_thread_with_owner_attribute(router):
    """owner 属性でBotスレッドを判定する"""
    import discord

    thread = MagicMock()
    thread.__class__ = type("Thread", (discord.Thread,), {})
    thread.id = 444555666
    thread.owner_id = None
    thread.owner = MagicMock()
    thread.owner.id = router.bot.user.id

    # bot_threads に登録されていない場合
    result = await router._is_bot_thread(thread)
    # owner.id が一致するため True
    assert result is True


@pytest.mark.asyncio
async def test_is_bot_thread_not_bot_thread(router):
    """Botスレッドでない場合"""
    import discord

    thread = MagicMock()
    thread.__class__ = type("Thread", (discord.Thread,), {})
    thread.id = 444555666
    thread.owner_id = 999999999  # BotのIDと異なる
    thread.owner = None

    # bot_threads に登録されていない場合
    result = await router._is_bot_thread(thread)
    # owner_id が一致しないため False
    assert result is False


@pytest.mark.asyncio
async def test_is_bot_thread_no_owner_info(router):
    """owner_id も owner も None の場合"""
    import discord

    thread = MagicMock()
    thread.__class__ = type("Thread", (discord.Thread,), {})
    thread.id = 444555666
    thread.owner_id = None
    thread.owner = None

    # bot_threads に登録されていない場合
    result = await router._is_bot_thread(thread)
    # 情報がないため False
    assert result is False
