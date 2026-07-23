from typing import override

from ..extractor import Extractor
from ..utils import get_title


class ClaudeDocExtractor(Extractor):
    """
    Anthropic
    """
    platform_name = "Anthropic"

    @override
    def can_handle(self) -> bool:
        return get_title(self.soup).endswith(" \\ Anthropic")

    @override
    def article_container(self) -> tuple:
        return ("article", None)

    @override
    def extract_url(self) -> str:
        return "https://www.anthropic.com/"

    @override
    def extract_author(self) -> str:
        # Anthropic 文章页面无独立作者 DOM 元素
        # 使用 twitter:creator meta 标签作为作者来源
        twitter_tag = self.soup.find("meta", attrs={"name": "twitter:creator"})
        if twitter_tag:
            return twitter_tag.get("content", "")
        return ""
