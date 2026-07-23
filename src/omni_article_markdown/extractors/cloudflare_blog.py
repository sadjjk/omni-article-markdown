from typing import override

from ..extractor import Extractor
from ..utils import filter_tag, is_matched_canonical


class CloudflareBlogExtractor(Extractor):
    """
    blog.cloudflare.com
    """
    platform_name = "Cloudflare Blog"

    @override
    def can_handle(self) -> bool:
        return is_matched_canonical("https://blog.cloudflare.com", self.soup)

    @override
    def article_container(self) -> tuple:
        return ("section", {"class": "post-full-content"})

    @override
    def extract_author(self) -> str:
        # Cloudflare 博客作者在 .author-name-tooltip 中，取第一个
        author_tag = filter_tag(self.soup.select_one(".author-name-tooltip"))
        if author_tag:
            return author_tag.get_text(strip=True).rstrip(",")
        # 备用：查 author-lists 下的链接
        author_link = filter_tag(self.soup.select_one(".author-lists a"))
        if author_link:
            return author_link.get_text(strip=True)
        return ""
