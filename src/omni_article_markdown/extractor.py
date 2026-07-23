import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import final, override

from bs4 import BeautifulSoup
from bs4.element import Comment, Tag

from .article import Article
from .plugins import load_plugins
from urllib.parse import urlparse

from .utils import filter_tag, get_article_author, get_article_tags, get_attr_text, get_canonical_url, get_og_description, get_og_site_name, get_og_title, get_og_url, get_publish_date, get_title

# 域名 → 平台名映射（无需单独 extractor 的站点）
_DOMAIN_PLATFORM_MAP = {
    "bilibili.com": "Bilibili",
    "b23.tv": "Bilibili",
    "weibo.com": "微博",
    "douyin.com": "抖音",
    "douban.com": "豆瓣",
    "github.com": "GitHub",
    "stackoverflow.com": "Stack Overflow",
    "reddit.com": "Reddit",
    "youtube.com": "YouTube",
    "notion.so": "Notion",
    "figma.com": "Figma",
    "medium.com": "Medium",
    "zhihu.com": "知乎",
    "jianshu.com": "简书",
    "baidu.com": "百度",
    "qq.com": "腾讯",
    "taobao.com": "淘宝",
    "jd.com": "京东",
    "xiaohongshu.com": "小红书",
    " bilibili.com": "Bilibili",
}

type TagPredicate = Callable[[Tag], bool]

TAGS_TO_CLEAN: list[TagPredicate] = [
    lambda el: el.name in ("style", "link", "button", "footer", "header"),
    lambda el: el.name == "script" and "src" not in el.attrs,
    lambda el: (
        el.name == "script"
        and el.has_attr("src")
        and not get_attr_text(el.attrs["src"]).startswith("https://gist.github.com")
    ),
]

ATTRS_TO_CLEAN: list[TagPredicate] = [
    lambda el: (
        "style" in el.attrs
        and re.search(r"display\s*:\s*none", get_attr_text(el.attrs.get("style")), re.IGNORECASE) is not None
    ),
    lambda el: "hidden" in el.attrs,
    lambda el: "class" in el.attrs and "katex-html" in el.attrs["class"],  # katex
    lambda el: "aria-hidden" in el.attrs and "true" in el.attrs["aria-hidden"],
]

ARTICLE_CONTAINERS = [("article", None), ("main", None), ("body", None)]


class Extractor(ABC):
    def __init__(self, soup: BeautifulSoup, url: str = ""):
        self.soup = soup
        self._url = url

    @final
    def extract(self) -> Article | None:
        # print(f"Using extractor: {self.__class__.__name__}")
        self.pre_handle_soup()
        article_container = self.article_container()
        if isinstance(article_container, tuple):
            article_container = [article_container]
        for container in article_container:
            article = self.extract_article()
            if article:
                if not article.platform:
                    article.platform = self.platform_name
                return article
            article_tag = self.extract_article_from_soup(container)
            if article_tag:
                title = self.extract_title()
                description = self.extract_description()
                for el in article_tag.find_all():
                    tag = filter_tag(el)
                    if tag:
                        if any(cond(tag) for cond in self.get_tags_to_clean()):
                            tag.decompose()
                            continue
                        if tag.attrs and any(cond(tag) for cond in self.get_attrs_to_clean()):
                            tag.decompose()
                for comment in article_tag.find_all(string=lambda text: isinstance(text, Comment)):
                    comment.extract()
                self.extract_img(article_tag)
                self.extract_video(article_tag)
                url = self.extract_url()
                author = self.extract_author()
                tags = self.extract_tags()
                publish_date = self.extract_publish_date()
                article = Article(
                    title=title,
                    url=url,
                    description=description,
                    body=article_tag,
                    platform=self.platform_name,
                    author=author,
                    tags=tags,
                    publish_date=publish_date,
                )
                self.remove_duplicate_titles(article)
                return article
        return None

    @abstractmethod
    def can_handle(self) -> bool: ...

    def get_tags_to_clean(self) -> list[Callable[[Tag], bool]]:
        return list(TAGS_TO_CLEAN)

    def get_attrs_to_clean(self) -> list[Callable[[Tag], bool]]:
        return list(ATTRS_TO_CLEAN)

    def article_container(self) -> tuple | list[tuple]:
        return ARTICLE_CONTAINERS

    def extract_title(self) -> str:
        return get_og_title(self.soup) or get_title(self.soup)

    def extract_description(self) -> str:
        return get_og_description(self.soup)

    def extract_url(self) -> str:
        return get_og_url(self.soup) or get_canonical_url(self.soup)

    def extract_img(self, element: Tag) -> Tag:
        return element

    def extract_video(self, element: Tag) -> Tag:
        return element

    platform_name: str = "其他"

    def extract_author(self) -> str:
        return get_article_author(self.soup)

    def extract_tags(self) -> list[str]:
        return get_article_tags(self.soup)

    def extract_publish_date(self) -> str:
        return get_publish_date(self.soup)

    def extract_article(self) -> Article | None:
        return None

    def pre_handle_soup(self):
        return

    def extract_article_from_soup(self, template: tuple) -> Tag | None:
        if template[1] is not None:
            result = self.soup.find(template[0], attrs=template[1])
        else:
            result = self.soup.find(template[0])
        return filter_tag(result)

    def remove_duplicate_titles(self, article: Article):
        if article.body and isinstance(article.body, Tag):
            first_h1 = article.body.find("h1")
            if first_h1:
                h1_text = first_h1.get_text(strip=True)
                if h1_text.lower() in article.title.lower():
                    article.title = h1_text
                    first_h1.decompose()


class ExtractorFactory:
    @staticmethod
    def create(soup: BeautifulSoup, url: str = "") -> Extractor:
        for extract in _load_extractors(soup, url):
            if extract.can_handle():
                return extract
        return DefaultExtractor(soup, url)


class DefaultExtractor(Extractor):
    @override
    def can_handle(self) -> bool:
        return True

    @override
    @property
    def platform_name(self) -> str:
        # 1. 先从 og:site_name 取
        site = get_og_site_name(self.soup)
        if site:
            return site
        # 2. 从 canonical / og:url 取域名
        url = get_canonical_url(self.soup) or get_og_url(self.soup) or self._url
        if url:
            try:
                netloc = urlparse(url).netloc.lower()
                # 去掉 www. 前缀
                if netloc.startswith("www."):
                    netloc = netloc[4:]
                # 精确匹配
                if netloc in _DOMAIN_PLATFORM_MAP:
                    return _DOMAIN_PLATFORM_MAP[netloc]
                # 后缀匹配（子域名）
                for domain, name in _DOMAIN_PLATFORM_MAP.items():
                    if netloc.endswith(domain):
                        return name
            except ValueError:
                pass
        return "其他"


def _load_extractors(soup: BeautifulSoup, url: str = "") -> list[Extractor]:
    return load_plugins(Extractor, "extractors", soup, url)
