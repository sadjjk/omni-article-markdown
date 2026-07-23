import json
import re
from typing import override

from ..article import Article
from ..extractor import Extractor
from ..utils import filter_tag, get_og_site_name, get_og_url, get_canonical_url


class ZhihuQaExtractor(Extractor):
    """知乎问答页"""
    platform_name = "知乎问答"

    @override
    def can_handle(self) -> bool:
        site_name = get_og_site_name(self.soup)
        if site_name == "知乎专栏":
            return False
        if self.soup.find("div", class_="QuestionHeader"):
            return True
        if self.soup.find("meta", attrs={"name": "za-config"}):
            return True
        if site_name == "知乎":
            return True
        return False

    @override
    def article_container(self) -> tuple:
        return ("div", {"class": "RichContent-inner"})

    @override
    def extract_author(self) -> str:
        author_info = self.soup.find(class_="AuthorInfo")
        if author_info:
            name_meta = author_info.find("meta", attrs={"itemprop": "name"})
            if name_meta and name_meta.get("content"):
                return name_meta["content"].strip()
        author_meta = self.soup.find("meta", attrs={"name": "author"})
        if author_meta and author_meta.get("content"):
            return author_meta["content"].strip()
        return ""

    @override
    def extract_url(self) -> str:
        # 1. og:url
        url = get_og_url(self.soup) or get_canonical_url(self.soup)
        if url:
            return url
        # 2. 从 data-zop meta 提取 question_id + answer_id
        data_zop = self.soup.find("meta", attrs={"name": "data-zop"})
        if data_zop and data_zop.get("content"):
            try:
                zop = json.loads(data_zop["content"])
                qid = str(zop.get("questionId", ""))
                aid = str(zop.get("answerId", ""))
                if qid and aid:
                    return f"https://www.zhihu.com/question/{qid}/answer/{aid}"
            except (json.JSONDecodeError, KeyError):
                pass
        # 3. 从页面 href 中提取 /question/{qid}/answer/{aid} 格式的 URL
        for a in self.soup.find_all("a", href=True):
            m = re.search(r'/question/(\d+)/answer/(\d+)', a["href"])
            if m:
                return f"https://www.zhihu.com/question/{m.group(1)}/answer/{m.group(2)}"
        # 4. 回退原始 URL
        return self.url_or_path or ""
