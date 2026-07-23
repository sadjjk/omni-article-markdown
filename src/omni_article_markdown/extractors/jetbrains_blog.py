from typing import override

from ..extractor import Extractor, TagPredicate
from ..utils import filter_tag, get_og_site_name


class JetbrainsBlogExtractor(Extractor):
    """
    blog.jetbrains.com
    """
    platform_name = "JetBrains Blog"

    def __init__(self, soup, url=""):
        super().__init__(soup, url)
        self._cached_author = None

    @override
    def can_handle(self) -> bool:
        return get_og_site_name(self.soup) == "The JetBrains Blog"

    @override
    def get_attrs_to_clean(self) -> list[TagPredicate]:
        return super().get_attrs_to_clean() + [
            lambda el: "class" in el.attrs and "content__row" in el.attrs["class"],
            lambda el: "class" in el.attrs and "content__pagination" in el.attrs["class"],
            lambda el: "class" in el.attrs and "content__form" in el.attrs["class"],
            lambda el: "class" in el.attrs and "tag" in el.attrs["class"],
            lambda el: "class" in el.attrs and "author-post" in el.attrs["class"],
        ]

    @override
    def article_container(self) -> tuple:
        return ("div", {"class": "content"})

    @override
    def pre_handle_soup(self):
        # 在 DOM 清理前缓存作者信息，因为 .author-post 会被 get_attrs_to_clean decompose
        self._cached_author = self._extract_author_impl()

    @override
    def extract_author(self) -> str:
        return self._cached_author if self._cached_author is not None else self._extract_author_impl()

    def _extract_author_impl(self) -> str:
        # JetBrains Blog 文章作者在 .author-post__text-title 中
        author_tag = filter_tag(self.soup.select_one(".author-post__text-title"))
        if author_tag:
            return author_tag.get_text(strip=True)
        # 备用：查 .author 元素（文章列表中的作者信息）
        author_div = filter_tag(self.soup.select_one(".author"))
        if author_div:
            return author_div.get_text(strip=True)
        return ""
