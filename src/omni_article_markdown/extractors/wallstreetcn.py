from typing import override

from ..extractor import Extractor
from ..utils import get_og_site_name


class WallstreetcnExtractor(Extractor):
    """
    华尔街见闻 (wallstreetcn.com)
    """
    platform_name = "华尔街见闻"

    @override
    def can_handle(self) -> bool:
        return get_og_site_name(self.soup) == "华尔街见闻"

    @override
    def article_container(self) -> tuple:
        return ("article", None)
