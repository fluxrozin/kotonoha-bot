"""AI関連の例外（抽象化の徹底）。.

Handler層が具体的なライブラリの例外を知っている必要があるのは抽象化の漏れ（Leaky Abstraction）です。
将来AIライブラリを変える際にHandlerも修正が必要になります。

対策: 独自例外を定義し、services/ai.py で Anthropic SDK の例外を独自例外にラッピングします。
"""


class AIError(Exception):
    """AI関連の基底例外."""

    pass


class AIAuthenticationError(AIError):
    """AI認証エラー.

    APIキーが無効な場合に発生します。
    """

    pass


class AIRateLimitError(AIError):
    """AIレート制限エラー.

    リトライ上限を超えてレート制限にかかった場合に発生します。
    """

    pass


class AIServiceError(AIError):
    """AIサービスエラー.

    AIサービスで予期しないエラーが発生した場合に発生します。
    """

    pass
