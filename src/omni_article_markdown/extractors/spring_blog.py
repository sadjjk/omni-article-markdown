from typing import override

from ..extractor import Extractor
from ..utils import filter_tag, get_og_url


class SpringBlogExtractor(Extractor):
    """
    spring.io/blog
    """
    platform_name = "Spring Blog"

    @override
    def can_handle(self) -> bool:
        return get_og_url(self.soup).startswith("https://spring.io/blog/")

    @override
    def article_container(self) -> tuple:
        return ("div", {"class": "markdown"})

    @override
    def extract_author(self) -> str:
        # Spring Blog 文章作者在 .meta 元素中，格式为「Engineering|Christian Tzolov|  January 13, 2026 |  8 min read」
        meta_tag = filter_tag(self.soup.select_one(".markdown + .meta, .meta"))
        if meta_tag:
            text = meta_tag.get_text(strip=True)
            # 按 | 分割，第二个部分是作者名
            parts = text.split("|")
            if len(parts) >= 2:
                author = parts[1].strip()
                if author:
                    return author
        # 备用：twitter:creator
        twitter_tag = self.soup.find("meta", attrs={"name": "twitter:creator"})
        if twitter_tag:
            return twitter_tag.get("content", "")
        return ""
