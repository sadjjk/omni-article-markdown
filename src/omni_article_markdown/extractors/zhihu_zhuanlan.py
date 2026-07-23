from typing import override

from ..article import Article
from ..extractor import Extractor
from ..utils import filter_tag, get_og_site_name


class ZhihuZhuanlanExtractor(Extractor):
    """知乎专栏"""
    platform_name = "知乎专栏"

    @override
    def can_handle(self) -> bool:
        site_name = get_og_site_name(self.soup)
        return site_name == "知乎专栏"

    @override
    def article_container(self) -> tuple:
        return ("div", {"class": "Post-RichText"})

    @override
    def extract_author(self) -> str:
        author_meta = self.soup.find("meta", attrs={"name": "author"})
        if author_meta and author_meta.get("content"):
            return author_meta["content"].strip()
        return super().extract_author()
