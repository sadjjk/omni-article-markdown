from typing import override

from bs4.element import Tag

from ..extractor import Extractor
from ..utils import filter_tag, get_attr_text, get_canonical_url, get_og_description, get_og_site_name


class JianshuExtractor(Extractor):
    """
    www.jianshu.com
    """
    platform_name = "简书"

    @override
    def can_handle(self) -> bool:
        return get_og_site_name(self.soup) == "简书"

    @override
    def extract_url(self) -> str:
        return get_canonical_url(self.soup)

    @override
    def extract_img(self, element: Tag) -> Tag:
        img_els = element.find_all("img")
        for img_el in img_els:
            img_tag = filter_tag(img_el)
            if img_tag:
                src = get_attr_text(img_tag.attrs.get("data-original-src"))
                if src:
                    img_tag.attrs["src"] = src
        return element

    @override
    def extract_author(self) -> str:
        # 简书页面作者信息在 JSON-LD 中，但 name 字段常为空
        # 备用：从页面 DOM 中的 .follow-detail 或 .info .name 提取
        author_tag = filter_tag(self.soup.select_one(".follow-detail .name"))
        if author_tag:
            return author_tag.get_text(strip=True)
        # 备用：从 meta 标签提取
        return super().extract_author()
