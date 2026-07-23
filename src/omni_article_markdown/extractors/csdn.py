from typing import override

from ..extractor import Extractor
from ..utils import filter_tag, is_matched_canonical


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

    @override
    def extract_author(self) -> str:
        # CSDN 页面左侧栏 #uid 链接内含作者昵称
        uid_tag = filter_tag(self.soup.select_one("#uid .name"))
        if uid_tag:
            return uid_tag.get_text(strip=True)
        # 备用：直接查 #uid
        uid_link = filter_tag(self.soup.select_one("#uid"))
        if uid_link:
            return uid_link.get_text(strip=True)
        return ""
