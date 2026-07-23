from typing import override

from ..extractor import Extractor, TagPredicate
from ..utils import filter_tag, get_og_site_name


class AppleDevelopExtractor(Extractor):
    """
    Apple Developer Documentation
    """
    platform_name = "Apple Developer"

    @override
    def can_handle(self) -> bool:
        return get_og_site_name(self.soup) == "Apple Developer Documentation"

    @override
    def get_attrs_to_clean(self) -> list[TagPredicate]:
        return super().get_attrs_to_clean() + [
            lambda el: "class" in el.attrs and "eyebrow" in el.attrs["class"],
            lambda el: "class" in el.attrs and "platform" in el.attrs["class"],
            lambda el: "class" in el.attrs and "title" in el.attrs["class"],
        ]

    @override
    def article_container(self) -> tuple:
        return ("main", {"class": "main"})

    @override
    def extract_author(self) -> str:
        # Apple Developer 文档页面无独立作者信息
        # 尝试从 meta 标签提取
        for prop in ["article:author", "author", "og:article:author"]:
            tag = self.soup.find("meta", attrs={"property": prop}) or self.soup.find("meta", attrs={"name": prop})
            if tag and tag.get("content"):
                return tag["content"]
        return ""
