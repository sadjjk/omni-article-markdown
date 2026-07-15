from typing import override

from ..extractor import Extractor
from ..utils import extract_domain, get_og_site_name


class ZhihuExtractor(Extractor):
    """
    知乎专栏 / 知乎问题页
    """
    platform_name = "知乎"

    @override
    def can_handle(self) -> bool:
        site_name = get_og_site_name(self.soup)
        if site_name == "知乎专栏":
            return True
        # 知乎问题页：检查知乎特有特征，但 article_container 不匹配问题页
        # 问题页走 DefaultExtractor，platform 为"其他"
        return False

    @override
    def article_container(self) -> tuple:
        return ("div", {"class": "Post-RichText"})
