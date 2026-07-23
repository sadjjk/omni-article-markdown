from typing import override

from ..extractor import Extractor
from ..utils import filter_tag, is_matched_canonical


class AliyunDeveloperExtractor(Extractor):
    """
    developer.aliyun.com
    """
    platform_name = "阿里云开发者"

    @override
    def can_handle(self) -> bool:
        return is_matched_canonical("https://developer.aliyun.com", self.soup)

    @override
    def article_container(self) -> tuple:
        return ("div", {"class": "article-content"})

    @override
    def extract_author(self) -> str:
        # 阿里云文章内容中作者信息格式为「作者 | xxx」或「作者：xxx」
        # 在文章正文开头的 p 标签中
        for p in self.soup.select(".article-content p"):
            text = p.get_text(strip=True)
            if text.startswith("作者") and ("|" in text or "：" in text):
                # 提取竖线或冒号后的名字
                for sep in ["|", "｜", "：", ":"]:
                    if sep in text:
                        name = text.split(sep, 1)[1].strip()
                        # 去掉「来源 | xxx」部分
                        if "来源" in name:
                            name = name.split("来源")[0].strip()
                            name = name.rstrip("|｜").strip()
                        if name:
                            return name
        return ""
