from typing import override

from ..extractor import Extractor
from ..utils import is_matched_canonical


class CsdnExtractor(Extractor):
    """
    blog.csdn.net
    """
    platform_name = "CSDN"

    @override
    def can_handle(self) -> bool:
        return is_matched_canonical("https://blog.csdn.net", self.soup)

    @override
    def article_container(self) -> tuple:
        return ("div", {"class": "article_content"})
