from typing import override
import json

from ..extractor import Extractor, TagPredicate
from ..utils import filter_tag, get_og_site_name


class SspaiExtractor(Extractor):
    """
    少数派
    """
    platform_name = "少数派"

    @override
    def can_handle(self) -> bool:
        return get_og_site_name(self.soup) == "少数派 - 高品质数字消费指南"

    @override
    def get_attrs_to_clean(self) -> list[TagPredicate]:
        return super().get_attrs_to_clean() + [
            lambda el: "class" in el.attrs and "comment__list" in el.attrs["class"],
            lambda el: "class" in el.attrs and "comment__footer__wrapper" in el.attrs["class"],
        ]

    @override
    def article_container(self) -> tuple:
        return ("div", {"class": "article__main__wrapper"})

    @override
    def extract_author(self) -> str:
        # 少数派文章作者在 JSON-LD 的 author 字段中
        for script in self.soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                if isinstance(data, dict):
                    author = data.get("author", {})
                    if isinstance(author, dict):
                        name = author.get("name", "")
                        if name:
                            return name
                    elif isinstance(author, str) and author:
                        return author
            except (json.JSONDecodeError, TypeError):
                continue
        # 备用：从 DOM 中提取
        author_tag = filter_tag(self.soup.select_one(".article__header__author .author__info .author__name"))
        if author_tag:
            return author_tag.get_text(strip=True)
        return ""
