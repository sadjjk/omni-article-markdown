from typing import override

from ..extractor import Extractor, TagPredicate
from ..utils import filter_tag, is_matched_canonical


class SnowflakeBlogExtractor(Extractor):
    """
    Snowflake 技术博客
    """
    platform_name = "Snowflake Blog"

    @override
    def can_handle(self) -> bool:
        return is_matched_canonical("https://www.snowflake.com/en/blog/", self.soup)

    @override
    def get_attrs_to_clean(self) -> list[TagPredicate]:
        return super().get_attrs_to_clean() + [
            lambda el: "class" in el.attrs and "snowflake-header-container" in el.attrs["class"],
        ]

    @override
    def article_container(self) -> tuple:
        return ("div", {"class": "snowflake-responsive-container-inner-padding-medium"})

    @override
    def extract_author(self) -> str:
        # Snowflake Blog 作者在 .snowflake-blog-author-text-name 中，取第一个（主作者）
        author_tag = filter_tag(self.soup.select_one(".snowflake-blog-author-text-name"))
        if author_tag:
            return author_tag.get_text(strip=True)
        return ""
