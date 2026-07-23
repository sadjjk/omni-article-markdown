from typing import override

from ..extractor import Extractor
from ..utils import filter_tag, get_og_url


class WoShiPMExtractor(Extractor):
    """
    人人都是产品经理
    """
    platform_name = "人人都是产品经理"

    @override
    def can_handle(self) -> bool:
        return get_og_url(self.soup).startswith("https://www.woshipm.com")

    @override
    def article_container(self) -> tuple:
        return ("div", {"class": "article--content"})

    @override
    def extract_author(self) -> str:
        # 人人都是产品经理文章作者在 .author 元素中，文本包含「关注」后缀需去掉
        author_tag = filter_tag(self.soup.select_one(".author .author-name, .author span:first-child"))
        if author_tag:
            name = author_tag.get_text(strip=True)
            if name:
                return name
        # 备用：直接查 .author 元素文本
        author_div = filter_tag(self.soup.select_one(".author"))
        if author_div:
            text = author_div.get_text(strip=True)
            # 去掉「关注」后缀
            text = text.replace("关注", "").strip()
            if text:
                return text
        return ""
