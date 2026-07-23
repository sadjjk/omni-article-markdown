from typing import override

from ..extractor import Extractor, TagPredicate
from ..utils import filter_tag, get_og_site_name


class QuantamagazineExtractor(Extractor):
    """
    quantamagazine.org
    """
    platform_name = "Quanta Magazine"

    @override
    def can_handle(self) -> bool:
        return get_og_site_name(self.soup) == "Quanta Magazine"

    @override
    def get_attrs_to_clean(self) -> list[TagPredicate]:
        return super().get_attrs_to_clean() + [
            lambda el: "class" in el.attrs and "post__title__title" in el.attrs["class"],
        ]

    @override
    def article_container(self) -> tuple:
        return ("div", {"id": "postBody"})

    @override
    def extract_author(self) -> str:
        # Quanta Magazine 文章作者在 .byline__author span 中
        author_tag = filter_tag(self.soup.select_one(".byline__author"))
        if author_tag:
            return author_tag.get_text(strip=True)
        return ""
