"""AIプロンプト定義

Markdownファイルからプロンプトを読み込む
"""

from pathlib import Path


def _load_prompt_from_markdown(filename: str) -> str:
    """Markdownファイルからプロンプトを読み込む

    Args:
        filename: 読み込むMarkdownファイル名

    Returns:
        プロンプトテキスト（Markdownの見出しを除く）
    """
    # このファイルと同じディレクトリのMarkdownファイルを読み込む
    prompts_dir = Path(__file__).parent
    md_file = prompts_dir / filename

    if not md_file.exists():
        raise FileNotFoundError(f"Prompt file not found: {md_file}")

    content = md_file.read_text(encoding="utf-8")

    # Markdownの見出し（# で始まる行）を除去
    lines = content.split("\n")
    # 最初の見出し行をスキップ
    if lines and lines[0].startswith("#"):
        lines = lines[1:]

    # 先頭と末尾の空行を除去
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()

    return "\n".join(lines)


# デフォルトのシステムプロンプト（Markdownファイルから読み込む）
DEFAULT_SYSTEM_PROMPT = _load_prompt_from_markdown("prompts.md")
