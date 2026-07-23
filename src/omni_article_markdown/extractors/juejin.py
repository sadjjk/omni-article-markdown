from typing import override

from ..extractor import Extractor
from ..utils import filter_tag, is_matched_canonical


class JuejinExtractor(Extractor):
    """
    juejin.cn
    """
    platform_name = "掘金"

    @override
    def can_handle(self) -> bool:
        return is_matched_canonical("https://juejin.cn/", self.soup)

    @override
    def article_container(self) -> tuple:
        return ("div", {"id": "article-root"})

    @override
    def extract_title(self) -> str:
        title_tag = filter_tag(self.soup.find("h1", {"class": "article-title"}))
        return title_tag.get_text(strip=True) if title_tag else super().extract_title()

    @override
    def extract_author(self) -> str:
        # 掘金文章作者在 .author-name 元素中
        author_tag = filter_tag(self.soup.select_one(".author-info-block .author-name"))
        if author_tag:
            return author_tag.get_text(strip=True)
        # 备用：查 itemprop=name 的 meta 标签
        name_tag = filter_tag(self.soup.find("meta", attrs={"itemprop": "name"}))
        if name_tag:
            return name_tag.get("content", "")
        return ""
