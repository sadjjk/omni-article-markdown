from typing import override

from bs4.element import Tag

from ..extractor import Extractor
from ..utils import filter_tag, get_attr_text

import json


class ToutiaoExtractor(Extractor):
    """
    今日头条
    """
    platform_name = "今日头条"

    @override
    def can_handle(self) -> bool:
        title_tag = self.soup.title
        title = title_tag.get_text(strip=True) if title_tag else None
        return title is not None and title.endswith(" - 今日头条")

    @override
    def article_container(self) -> tuple:
        return ("div", {"class": "article-content"})

    @override
    def extract_img(self, element: Tag) -> Tag:
        img_els = element.find_all("img")
        for img_el in img_els:
            img_tag = filter_tag(img_el)
            if img_tag:
                src = get_attr_text(img_tag.attrs.get("data-src"))
                if src:
                    img_tag.attrs["src"] = src
        return element

    @override
    def extract_author(self) -> str:
        # 今日头条文章作者在 JSON-LD 的 author 字段中
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
        # 备用：从 .article-meta .name 中提取
        name_tag = filter_tag(self.soup.select_one(".article-meta .name"))
        if name_tag:
            return name_tag.get_text(strip=True)
        # 备用：a.user-name
        user_link = filter_tag(self.soup.select_one("a.user-name"))
        if user_link:
            return user_link.get_text(strip=True)
        return ""
