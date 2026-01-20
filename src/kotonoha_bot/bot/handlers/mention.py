"""メンション応答ハンドラー。."""

import asyncio
import logging

import discord

from kotonoha_bot.bot.client import KotonohaBot
from kotonoha_bot.config import Config
from kotonoha_bot.db.models import MessageRole
from kotonoha_bot.errors.database import (
    classify_database_error,
    get_database_error_message,
)
from kotonoha_bot.errors.discord import (
    classify_discord_error,
    get_user_friendly_message,
)
from kotonoha_bot.errors.messages import ErrorMessages
from kotonoha_bot.rate_limit.request_queue import RequestPriority, RequestQueue
from kotonoha_bot.services.ai import AIProvider
from kotonoha_bot.services.session import SessionManager
from kotonoha_bot.utils.datetime import format_datetime_for_prompt
from kotonoha_bot.utils.message import (
    create_response_embed,
    format_split_messages,
    split_message,
)
from kotonoha_bot.utils.prompts import DEFAULT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class MentionHandler:
    """メンション応答ハンドラー."""

    def __init__(
        self,
        bot: KotonohaBot,
        session_manager: SessionManager,
        ai_provider: AIProvider,
        request_queue: RequestQueue,
        config: Config | None = None,
    ):
        """MentionHandler を初期化.

        Args:
            bot: Discord クライアント
            session_manager: セッションマネージャー
            ai_provider: AIプロバイダー
            request_queue: リクエストキュー
            config: 設定インスタンス（省略可）
        """
        self.bot = bot
        self.session_manager = session_manager
        self.ai_provider = ai_provider
        self.request_queue = request_queue
        self.config = config

    async def handle(self, message: discord.Message) -> None:
        """メンション時の処理（リクエストキューに追加）.

        Args:
            message: Discord メッセージ
        """
        # Bot自身のメッセージは無視
        if message.author.bot:
            return

        # Botがメンションされているか確認
        if self.bot.user not in message.mentions:
            return

        logger.info(f"Mention from {message.author} in {message.channel}")

        # リクエストキューに追加（優先度: MENTION）
        try:
            future = await self.request_queue.enqueue(
                RequestPriority.MENTION,
                self._process,
                message,
            )
            # 結果を待機（エラーハンドリングは内部で行う）
            await future
        except Exception as e:
            logger.exception(f"Error enqueuing mention request: {e}")
            # キューが満杯などの場合のフォールバック
            try:
                await self._process(message)
            except Exception as inner_e:
                logger.exception(f"Error in fallback mention processing: {inner_e}")

    async def _process(self, message: discord.Message) -> None:
        """メンション処理の実装.

        Args:
            message: Discord メッセージ
        """
        try:
            # タイピングインジケーターを表示
            async with message.channel.typing():
                # セッションキーを生成（ユーザーIDベース）
                session_key = f"mention:{message.author.id}"

                # セッションを取得または作成
                session = await self.session_manager.get_session(session_key)
                if not session:
                    # ⚠️ 重要: guild_id は Discord URL生成に必要
                    guild_id = message.guild.id if message.guild else None
                    session = await self.session_manager.create_session(
                        session_key=session_key,
                        session_type="mention",
                        guild_id=guild_id,
                        channel_id=message.channel.id,
                        user_id=message.author.id,
                    )
                    logger.info(f"Created new session: {session_key}")

                # メンション部分を除去したメッセージ
                user_message = message.content
                for mention in message.mentions:
                    user_message = user_message.replace(f"<@{mention.id}>", "").strip()

                # ユーザーメッセージを追加
                await self.session_manager.add_message(
                    session_key=session_key,
                    role=MessageRole.USER,
                    content=user_message,
                )

                # 現在の日付情報を含むシステムプロンプトを生成
                current_date_info = format_datetime_for_prompt()
                system_prompt = DEFAULT_SYSTEM_PROMPT + current_date_info

                # AI応答を生成
                response_text, token_info = await self.ai_provider.generate_response(
                    messages=session.get_conversation_history(),
                    system_prompt=system_prompt,
                )

                # アシスタントメッセージを追加
                await self.session_manager.add_message(
                    session_key=session_key,
                    role=MessageRole.ASSISTANT,
                    content=response_text,
                )

                # セッションを保存
                await self.session_manager.save_session(session_key)

                # 返信（メッセージ分割対応）
                response_chunks = split_message(response_text)
                formatted_chunks = format_split_messages(
                    response_chunks, len(response_chunks)
                )

                # 使用モデル名とレート制限使用率を取得
                model_name = self.ai_provider.get_last_used_model()
                rate_limit_usage = self.ai_provider.get_rate_limit_usage()

                # 最初のメッセージは reply で送信（フッター付き）
                if formatted_chunks:
                    # 最初のメッセージのみEmbedで送信（フッター付き）
                    embed = create_response_embed(
                        formatted_chunks[0], model_name, rate_limit_usage
                    )
                    await message.reply(embed=embed)

                    # 残りのメッセージは順次送信
                    for chunk in formatted_chunks[1:]:
                        await message.channel.send(chunk)
                        # レート制限を考慮して少し待機
                        await asyncio.sleep(0.5)

                logger.info(f"Sent response to {message.author}")

        except discord.errors.DiscordException as e:
            logger.exception(f"Discord error handling mention: {e}")
            error_type = classify_discord_error(e)
            error_message = get_user_friendly_message(error_type)
            try:
                await message.reply(error_message)
            except Exception as reply_error:
                logger.error(f"Failed to send error message: {reply_error}")
        except Exception as e:
            logger.exception(f"Error handling mention: {e}")
            # データベースエラーの可能性をチェック
            if "sqlite" in str(type(e)).lower() or "database" in str(e).lower():
                error_type = classify_database_error(e)
                error_message = get_database_error_message(error_type)
                try:
                    await message.reply(error_message)
                except Exception as reply_error:
                    logger.error(f"Failed to send error message: {reply_error}")
            else:
                try:
                    await message.reply(ErrorMessages.GENERIC)
                except Exception as reply_error:
                    logger.error(f"Failed to send error message: {reply_error}")
