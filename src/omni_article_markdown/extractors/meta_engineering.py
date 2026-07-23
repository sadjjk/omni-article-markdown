from typing import override

from ..extractor import Extractor
from ..utils import is_matched_canonical


class MetaEngineeringExtractor(Extractor):
    """
    Engineering at Meta (engineering.fb.com)
    """
    platform_name = "Meta Engineering"

    @override
    def can_handle(self) -> bool:
        return is_matched_canonical("https://engineering.fb.com", self.soup)

    @override
    def article_container(self) -> tuple:
        return ("article", None)
