"""Discord イベントハンドラー"""
import discord
import logging

from .client import KotonohaBot
from ..session.manager import SessionManager
from ..session.models import MessageRole
from ..ai.litellm_provider import LiteLLMProvider, DEFAULT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class MessageHandler:
    """メッセージハンドラー"""

    def __init__(self, bot: KotonohaBot):
        self.bot = bot
        self.session_manager = SessionManager()
        self.ai_provider = LiteLLMProvider()

    async def handle_mention(self, message: discord.Message):
        """メンション時の処理"""
        # Bot自身のメッセージは無視
        if message.author.bot:
            return

        # Botがメンションされているか確認
        if self.bot.user not in message.mentions:
            return

        logger.info(f"Mention from {message.author} in {message.channel}")

        try:
            # タイピングインジケーターを表示
            async with message.channel.typing():
                # セッションキーを生成（ユーザーIDベース）
                session_key = f"mention:{message.author.id}"

                # セッションを取得または作成
                session = self.session_manager.get_session(session_key)
                if not session:
                    session = self.session_manager.create_session(
                        session_key=session_key,
                        session_type="mention",
                        channel_id=message.channel.id,
                        user_id=message.author.id,
                    )
                    logger.info(f"Created new session: {session_key}")

                # メンション部分を除去したメッセージ
                user_message = message.content
                for mention in message.mentions:
                    user_message = user_message.replace(f"<@{mention.id}>", "").strip()

                # ユーザーメッセージを追加
                self.session_manager.add_message(
                    session_key=session_key,
                    role=MessageRole.USER,
                    content=user_message,
                )

                # AI応答を生成
                response_text = self.ai_provider.generate_response(
                    messages=session.get_conversation_history(),
                    system_prompt=DEFAULT_SYSTEM_PROMPT,
                )

                # アシスタントメッセージを追加
                self.session_manager.add_message(
                    session_key=session_key,
                    role=MessageRole.ASSISTANT,
                    content=response_text,
                )

                # セッションを保存
                self.session_manager.save_session(session_key)

                # 返信
                await message.reply(response_text)
                logger.info(f"Sent response to {message.author}")

        except Exception as e:
            logger.exception(f"Error handling mention: {e}")
            await message.reply(
                "申し訳ありません。エラーが発生しました。少し時間をおいて再度お試しください。"
            )


def setup_handlers(bot: KotonohaBot):
    """イベントハンドラーをセットアップ"""
    handler = MessageHandler(bot)

    @bot.event
    async def on_message(message: discord.Message):
        """メッセージ受信時"""
        await handler.handle_mention(message)
        # コマンド処理も継続
        await bot.process_commands(message)

    logger.info("Event handlers registered")

    return handler
