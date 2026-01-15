"""メッセージ分割機能のテスト"""

from kotonoha_bot.utils.message_splitter import (
    DISCORD_MESSAGE_MAX_LENGTH,
    format_split_messages,
    split_message,
)


def test_split_short_message():
    """短いメッセージは分割されない"""
    content = "これは短いメッセージです。"
    chunks = split_message(content)
    assert len(chunks) == 1
    assert chunks[0] == content


def test_split_long_message():
    """長いメッセージは分割される"""
    # 3000文字のメッセージを作成
    content = "。" * 3000
    chunks = split_message(content)
    assert len(chunks) > 1
    assert all(len(chunk) <= DISCORD_MESSAGE_MAX_LENGTH for chunk in chunks)


def test_split_at_sentence_boundary():
    """文の区切りで分割される"""
    content = "最初の文です。\n\n2番目の文です。\n\n3番目の文です。"
    # 長いメッセージにするために繰り返す
    long_content = content * 1000
    chunks = split_message(long_content)
    # 各チャンクが適切に分割されていることを確認
    assert len(chunks) > 1


def test_format_split_messages():
    """連番が正しく付与される"""
    chunks = ["チャンク1", "チャンク2", "チャンク3"]
    formatted = format_split_messages(chunks, len(chunks))
    assert len(formatted) == 3
    assert "(1/3)" in formatted[0]
    assert "(2/3)" in formatted[1]
    assert "(3/3)" in formatted[2]


def test_format_single_message():
    """単一メッセージには連番が付与されない"""
    chunks = ["単一のメッセージ"]
    formatted = format_split_messages(chunks, len(chunks))
    assert len(formatted) == 1
    assert formatted[0] == "単一のメッセージ"


def test_split_at_period():
    """句点で分割される"""
    # 2000文字を超えるメッセージを作成（句点を含む）
    base_text = "これはテストメッセージです。"
    content = base_text * 200  # 約2600文字（13文字 * 200 = 2600文字）
    chunks = split_message(content)
    assert len(chunks) > 1
    # 各チャンクが最大長を超えていないことを確認
    assert all(len(chunk) <= DISCORD_MESSAGE_MAX_LENGTH for chunk in chunks)


def test_split_at_newline():
    """改行で分割される"""
    # 2000文字を超えるメッセージを作成（改行を含む）
    base_text = "これはテストメッセージです。\n"
    content = base_text * 200  # 約2800文字（14文字 * 200 = 2800文字）
    chunks = split_message(content)
    assert len(chunks) > 1
    assert all(len(chunk) <= DISCORD_MESSAGE_MAX_LENGTH for chunk in chunks)


def test_split_no_delimiter():
    """区切り文字がない場合は強制的に分割される"""
    # 区切り文字なしの長いメッセージ
    content = "あ" * 3000
    chunks = split_message(content)
    assert len(chunks) > 1
    # 各チャンクが最大長以下であることを確認
    assert all(len(chunk) <= DISCORD_MESSAGE_MAX_LENGTH for chunk in chunks)
