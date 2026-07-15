from typing import override

from ..extractor import Extractor
from ..utils import is_matched_canonical


class SegmentFaultExtractor(Extractor):
    """
    segmentfault.com
    """
    platform_name = "思否"

    @override
    def can_handle(self) -> bool:
        return is_matched_canonical("https://segmentfault.com", self.soup)

    @override
    def article_container(self) -> tuple:
        return ("div", {"class": "article-content"})
