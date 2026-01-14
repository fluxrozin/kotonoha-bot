"""Discord イベントハンドラー"""

import logging
from datetime import datetime

import discord

from ..ai.litellm_provider import DEFAULT_SYSTEM_PROMPT, LiteLLMProvider
from ..session.manager import SessionManager
from ..session.models import MessageRole
from .client import KotonohaBot

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

                # 現在の日付情報を含むシステムプロンプトを生成
                now = datetime.now()
                weekday_names = ["月", "火", "水", "木", "金", "土", "日"]
                current_date_info = (
                    f"\n\n【現在の日付情報】\n"
                    f"現在の日時: {now.strftime('%Y年%m月%d日 %H:%M:%S')}\n"
                    f"今日の曜日: {weekday_names[now.weekday()]}曜日\n"
                    f"日付や曜日に関する質問には、この情報を基に具体的に回答してください。"
                    f"プレースホルダー（[明日の曜日]など）は使用せず、実際の日付や曜日を回答してください。"
                )
                system_prompt = DEFAULT_SYSTEM_PROMPT + current_date_info

                # AI応答を生成
                response_text = self.ai_provider.generate_response(
                    messages=session.get_conversation_history(),
                    system_prompt=system_prompt,
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
        # Bot自身のメッセージは無視
        if message.author.bot:
            await bot.process_commands(message)
            return

        # メンション処理（メンションされている場合のみ）
        if bot.user in message.mentions:
            await handler.handle_mention(message)
            # メンション処理後はコマンド処理をスキップ（重複応答を防ぐ）
            return

        # コマンド処理（メンションでない場合のみ）
        await bot.process_commands(message)

    logger.info("Event handlers registered")

    return handler
