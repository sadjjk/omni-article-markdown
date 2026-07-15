from typing import override

from ..extractor import Extractor
from ..utils import is_matched_canonical


class InfoQCNExtractor(Extractor):
    """
    www.infoq.cn
    """
    platform_name = "InfoQ中文"

    @override
    def can_handle(self) -> bool:
        return is_matched_canonical("https://www.infoq.cn", self.soup)

    @override
    def article_container(self) -> tuple:
        return ("div", {"class": "article-content-wrap"})
