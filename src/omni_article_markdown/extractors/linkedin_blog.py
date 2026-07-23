from typing import override

from bs4.element import Tag

from ..extractor import Extractor, TagPredicate
from ..utils import filter_tag, get_attr_text, get_og_url

import re


class LinkedInBlogExtractor(Extractor):
    """
    www.linkedin.com
    """
    platform_name = "LinkedIn"

    def __init__(self, soup, url=""):
        super().__init__(soup, url)
        self._cached_author = None

    @override
    def can_handle(self) -> bool:
        return get_og_url(self.soup).startswith("https://www.linkedin.com/blog/")

    @override
    def get_attrs_to_clean(self) -> list[TagPredicate]:
        return super().get_attrs_to_clean() + [
            lambda el: "data-component-type" in el.attrs and "articleHeadline" in el.attrs["data-component-type"],
            lambda el: "data-component-type" in el.attrs and "postList" in el.attrs["data-component-type"],
        ]

    @override
    def extract_img(self, element: Tag) -> Tag:
        img_els = element.find_all("img")
        for img_el in img_els:
            img_tag = filter_tag(img_el)
            if img_tag:
                src = get_attr_text(img_tag.attrs.get("data-delayed-url"))
                if src:
                    img_tag.attrs["src"] = src
        return element

    @override
    def pre_handle_soup(self):
        # 在 DOM 清理前缓存作者信息，因为 author 元素可能在 article_container 内被 decompose
        self._cached_author = self._extract_author_impl()

    @override
    def extract_author(self) -> str:
        return self._cached_author if self._cached_author is not None else self._extract_author_impl()

    def _extract_author_impl(self) -> str:
        # LinkedIn Blog 作者在 .author-profile__author-container 中，格式为「Authored byBohan YangDecember 3, 2025」
        author_div = filter_tag(self.soup.select_one(".author-profile__author-container"))
        if author_div:
            text = author_div.get_text(strip=True)
            # 提取 "Authored by" 或 "Co-authored by" 后面的名字
            match = re.search(r'(?:Authored by|Co-authored by)(.+?)(?:December|January|February|March|April|May|June|July|August|September|October|November)', text)
            if match:
                name = match.group(1).strip()
                if name:
                    return name
        # 备用：查 list-post 作者
        list_author = filter_tag(self.soup.select_one(".list-post__content-container__author"))
        if list_author:
            return list_author.get_text(strip=True)
        return ""
