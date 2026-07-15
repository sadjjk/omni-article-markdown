import base64
import re
from collections.abc import Callable
from datetime import datetime, timezone
from urllib.parse import urljoin

from bs4.element import NavigableString, Tag

from .extractor import Article
from .http_client import get_session
from .utils import (
    collapse_spaces,
    detect_language,
    filter_tag,
    get_attr_text,
    is_sequentially_increasing,
    move_spaces,
)

LB_SYMBOL = "[|lb_bl|]"

POST_HANDLERS: list[Callable[[str], str]] = [
    # 添加换行使文章更美观
    lambda el: re.sub(f"(?:{re.escape(LB_SYMBOL)})+", LB_SYMBOL, el).replace(LB_SYMBOL, "\n\n").strip(),
    # 纠正不规范格式 `**code**` 替换为 **`code`**
    lambda el: re.sub(r"`\*\*(.*?)\*\*`", r"**`\1`**", el),
    # 纠正不规范格式 `*code*` 替换为 *`code`*
    lambda el: re.sub(r"`\*(.*?)\*`", r"*`\1`*", el),
    # 纠正不规范格式 `[code](url)` 替换为 [`code`](url)
    lambda el: re.sub(r"`\s*\[([^\]]+)\]\(([^)]+)\)\s*`", r"[`\1`](\2)", el),
    # 将 \( ... \) 替换为 $ ... $
    lambda el: re.sub(r"\\\((.+?)\\\)", r"$\1$", el),
    # 将 \[ ... \] 替换为 $$ ... $$
    lambda el: re.sub(r"\\\[(.+?)\\\]", r"$$\1$$", el),
]

INLINE_ELEMENTS = ["span", "code", "li", "a", "strong", "em", "b", "i", "sup"]

BLOCK_ELEMENTS = [
    "p",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "ul",
    "ol",
    "blockquote",
    "pre",
    "img",
    "picture",
    "hr",
    "figcaption",
    "table",
    "section",
    "svg",
]

TRUSTED_ELEMENTS = INLINE_ELEMENTS + BLOCK_ELEMENTS


class HtmlMarkdownParser:
    def __init__(self, article: Article):
        self.article = article
        self._media_videos: list[tuple[str, str]] = []  # (url, description)
        self._media_images: list[tuple[str, str]] = []  # (url, alt)

    def parse(self) -> tuple[str, str]:
        if isinstance(self.article.body, str):
            markdown = self.article.body
        else:
            markdown = self._process_children(self.article.body)
        for handler in POST_HANDLERS:
            markdown = handler(markdown)
        frontmatter = self._build_frontmatter()
        media_section = self._build_media_section()
        result = f"{frontmatter}\n# {self.article.title}\n\n{markdown}{media_section}"
        # print(result)
        return (self.article.title, result)

    def _process_element(self, element: Tag, level: int = 0, is_pre: bool = False) -> str:
        parts = []
        tag = element.name
        match tag:
            case "br":
                parts.append(LB_SYMBOL)
            case "hr":
                parts.append("---")
            case "h1" | "h2" | "h3" | "h4" | "h5" | "h6":
                heading = self._process_children(element, level, is_pre=is_pre)
                parts.append(f"{'#' * int(element.name[1])} {heading}")
            case "sup":
                sup = element.get_text(strip=True)
                if sup:
                    parts.append(f"<sup>{sup}</sup>")
            case "a":
                link_text = self._process_children(element, level, is_pre=is_pre).replace(LB_SYMBOL, "")
                if link_text:
                    parts.append(self._process_link(element, link_text))
            case "strong" | "b":
                s = self._process_children(element, level, is_pre=is_pre).replace(LB_SYMBOL, "")
                if s:
                    parts.append(move_spaces(f"**{s}**", "**"))
            case "em" | "i":
                s = self._process_children(element, level, is_pre=is_pre).replace(LB_SYMBOL, "")
                if s:
                    parts.append(move_spaces(f"*{s}*", "*"))
            case "ul" | "ol":
                parts.append(self._process_list(element, level))
            case "img":
                parts.append(self._process_image(element, None))
            case "blockquote":
                blockquote = self._process_children(element, level, is_pre=is_pre)
                if blockquote.startswith(LB_SYMBOL):
                    blockquote = blockquote.removeprefix(LB_SYMBOL)
                if blockquote.endswith(LB_SYMBOL):
                    blockquote = blockquote.removesuffix(LB_SYMBOL)
                parts.append("\n".join(f"> {line}" for line in blockquote.split(LB_SYMBOL)))
            case "pre":
                parts.append(self._process_codeblock(element, level))
            case "code":  # inner code
                code = self._process_children(element, level, is_pre=is_pre)
                if LB_SYMBOL not in code:
                    parts.append(f"`{code}`")
                else:
                    parts.append(code)
            case "picture":
                source_elements = element.find_all("source")
                img_element = filter_tag(element.find("img"))
                if img_element and source_elements:
                    el = source_elements[0]
                    src_el = filter_tag(el)
                    if src_el:
                        parts.append(self._process_image(img_element, src_el))
                elif img_element:
                    parts.append(self._process_image(img_element, None))
            case "figcaption":
                figcaption = self._process_children(element, level, is_pre=is_pre).replace(LB_SYMBOL, "\n").strip()
                figcaptions = figcaption.replace("\n\n", "\n").split("\n")
                parts.append("\n".join([f"*{caption}*" for caption in figcaptions]))
            case "table":
                parts.append(self._process_table(element, level))
            case "math":  # 处理latex公式
                semantics = filter_tag(element.find("semantics"))
                if semantics:
                    tex = filter_tag(semantics.find(attrs={"encoding": "application/x-tex"}))
                    if tex:
                        parts.append(f"$$ {tex.text} $$")
            case "script":  # 处理github gist
                parts.append(self._process_gist(element))
            case "svg":  # 处理svg图片
                if element.get("data-id") == "omnimd":
                    parts.append(self._process_svg(element))
            case "video" | "iframe" | "embed":
                parts.append(self._process_video(element))
            case _:
                parts.append(self._process_children(element, level, is_pre=is_pre))
        result = "".join(parts)
        if result and is_block_element(element.name) and (not element.children or not is_pure_block_children(element)):
            result = f"{LB_SYMBOL}{result}{LB_SYMBOL}"
        return result

    def _process_children(self, element: Tag, level: int = 0, is_pre: bool = False) -> str:
        parts = []
        if element.children:
            # new_level = level + 1 if element.name in HtmlMarkdownParser.TRUSTED_ELEMENTS else level
            for child in element.children:
                if isinstance(child, NavigableString):
                    if is_pre:
                        parts.append(child)
                    else:
                        result = collapse_spaces(child).replace("<", "&lt;").replace(">", "&gt;")
                        if result.strip():
                            parts.append(result)
                        # print(element.name, level, result)
                elif isinstance(child, Tag):
                    result = self._process_element(child, level, is_pre=is_pre)
                    if is_pre or result.strip():
                        parts.append(result)
        return "".join(parts) if is_pre or level > 0 else "".join(parts)

    def _process_list(self, element: Tag, level: int) -> str:
        indent = "  " * level
        child_list = element.find_all(recursive=False)
        is_ol = element.name == "ol"
        parts = []
        for i, child in enumerate(child_list):
            child = filter_tag(child)
            if child:
                if child.name == "li":
                    content = self._process_children(child, level).replace(LB_SYMBOL, "\n").strip()
                    if content:  # 忽略空内容
                        prefix = f"{i + 1}." if is_ol else "-"
                        parts.append(f"{indent}{prefix} {content}")
                elif child.name == "ul" or child.name == "ol":
                    content = self._process_element(child, level + 1)
                    if content:  # 忽略空内容
                        parts.append(f"{content.replace(LB_SYMBOL, '\n')}")
        if not parts:
            return ""  # 所有内容都为空则返回空字符串
        return "\n".join(parts)

    def _process_codeblock(self, element: Tag, level: int) -> str:
        # 找出所有 code 标签（可能为 0 个、1 个或多个）
        code_elements = element.find_all("code") or [element]

        # 处理每一个 code 标签并拼接
        code_parts = [
            self._process_children(code_el, level, is_pre=True).replace(LB_SYMBOL, "\n")
            for code_el in code_elements
            if isinstance(code_el, Tag)
        ]
        code = "\n".join(code_parts).strip()

        if is_sequentially_increasing(code):
            return ""  # 忽略行号

        # 尝试提取语言：从第一个 code 标签的 class 中提取 language
        first_code_el = code_elements[0]
        language = (
            next((cls.split("-")[1] for cls in (first_code_el.get("class") or []) if cls.startswith("language-")), "")
            if isinstance(first_code_el, Tag)
            else ""
        )
        if not language:
            language = detect_language(None, code)
        return f"```{language}\n{code}\n```" if language else f"```\n{code}\n```"

    def _process_table(self, element: Tag, level: int) -> str:
        if element.find("pre"):
            return self._process_children(element, level)
        # 获取所有行，包括 thead 和 tbody
        rows = element.find_all("tr")
        if not rows:
            return ""
        # 解析表头（如果有）
        headers = []
        first_row = filter_tag(rows.pop(0))
        if first_row and first_row.find("th"):
            headers = [th.get_text(strip=True) for th in first_row.find_all("th")]
        # 解析表身
        body = [[td.get_text(strip=True) for td in row.find_all("td")] for row in rows if isinstance(row, Tag)]
        # 处理缺失的表头
        if not headers and body:
            headers = body.pop(0)
        # 统一列数
        col_count = max(len(headers), max((len(row) for row in body), default=0))
        headers += [""] * (col_count - len(headers))
        for row in body:
            row += [""] * (col_count - len(row))
        # 生成 Markdown 表格
        markdown_table = []
        markdown_table.append("| " + " | ".join(headers) + " |")
        markdown_table.append("|-" + "-|-".join(["-" * len(h) for h in headers]) + "-|")
        for row in body:
            markdown_table.append("| " + " | ".join(row) + " |")
        return "\n".join(markdown_table)

    def _process_image(self, element: Tag, source: Tag | None) -> str:
        src = (
            get_attr_text(element.attrs.get("src"))
            if source is None
            else get_attr_text(source.attrs.get("srcset")).split()[0]
        )
        alt = get_attr_text(element.attrs.get("alt"))
        if src:
            if not src.startswith("http") and self.article.url:
                src = urljoin(self.article.url, src)
            # 收集图片到媒体列表（排除 SVG base64）
            if not src.startswith("data:image/svg+xml"):
                # alt 为空时自动编号
                if not alt:
                    alt = f"图片 {len(self._media_images) + 1}"
                self._media_images.append((src, alt))
            return f"![{alt}]({src})"
        return ""

    def _process_video(self, element: Tag) -> str:
        # 提取视频/嵌入内容 URL，收集到媒体列表，正文不输出
        tag_name = element.name
        src = ""

        if tag_name == "video":
            src = element.get("src", "")
            if not src:
                source = element.find("source", src=True)
                if source:
                    src = source.get("src", "")
            # poster 封面图收集到图片列表
            poster = element.get("poster", "")
            if poster and not any(url == poster for url, _ in self._media_images):
                poster_alt = f"图片 {len(self._media_images) + 1}"
                self._media_images.append((poster, poster_alt))
        elif tag_name in ("iframe", "embed"):
            src = element.get("src", "")

        # 跳过空 src 和 about:blank
        if not src or src.startswith("about:blank"):
            return ""

        # urljoin 补全
        src = urljoin(self.article.url, src)

        # 去重
        if any(url == src for url, _ in self._media_videos):
            return ""

        # 描述：title → figcaption → 默认编号
        desc = element.get("title", "")
        if not desc:
            figure = element.find_parent("figure")
            if figure:
                caption = figure.find("figcaption")
                if caption:
                    desc = caption.get_text(strip=True)
        if not desc:
            video_num = len(self._media_videos) + 1
            desc = f"嵌入内容 {video_num}" if tag_name == "iframe" else f"视频 {video_num}"

        self._media_videos.append((src, desc))
        return ""

    def _build_frontmatter(self) -> str:
        # 构建 YAML frontmatter
        lines = ["---"]
        article = self.article

        def _yaml_escape(val: str) -> str:
            # 含特殊字符时用双引号包裹
            if any(c in val for c in (':', '"', '[', ']', '{', '}', '#', '&', '*', '?', '|', '-', '<', '>', '=', '!', '%', '@', '`')):
                return f'"{val.replace(chr(34), chr(92) + chr(34))}"'
            return val

        if article.title:
            lines.append(f"title: {_yaml_escape(article.title)}")
        if article.description:
            # 归一化空白：换行/制表符/多空格 → 单个空格
            desc = re.sub(r"\s+", " ", article.description).strip()
            if desc and len(desc) > 150:
                desc = desc[:150].rstrip() + "..."
            if desc:
                lines.append(f"description: {_yaml_escape(desc)}")
        if article.url:
            lines.append(f"source: {article.url}")
        if article.platform:
            lines.append(f"platform: {_yaml_escape(article.platform)}")
        if article.author:
            lines.append(f"author: {_yaml_escape(article.author)}")
        if article.tags:
            lines.append(f"tags: [{', '.join(article.tags)}]")
        if article.publish_date:
            lines.append(f"published: {article.publish_date}")
        lines.append(f"created: {datetime.now(tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')}")
        lines.append("---")
        return "\n".join(lines)

    def _build_media_section(self) -> str:
        # 构建末尾媒体文件段
        if not self._media_videos and not self._media_images:
            return ""

        sections = ["\n\n---\n\n## 媒体文件\n\n"]

        if self._media_videos:
            sections.append("### 视频\n\n")
            for i, (url, desc) in enumerate(self._media_videos, 1):
                sections.append(f"{i}. [{desc}]({url})\n")
            sections.append("\n")

        if self._media_images:
            sections.append("### 图片\n\n")
            for i, (url, alt) in enumerate(self._media_images, 1):
                sections.append(f"{i}. ![{alt}]({url})\n")
            sections.append("\n")

        return "".join(sections)

    def _process_link(self, element: Tag, link_text: str) -> str:
        link = get_attr_text(element.get("href"))
        if link:
            if self.article.url and not link.startswith("http"):
                link = urljoin(self.article.url, link)
            return f"[{link_text}]({link})"
        return link_text

    def _process_svg(self, element: Tag) -> str:
        svg_content = str(element)
        if svg_content:
            return f"![](data:image/svg+xml;base64,{base64.b64encode(svg_content.encode()).decode()})"
        return ""

    def _process_gist(self, element: Tag) -> str:
        src = get_attr_text(element.attrs.get("src"))
        pattern = r"/([0-9a-f]+)(?:\.js)?$"
        match = re.search(pattern, src)
        if match:
            gist_id = match.group(1)
            url = f"https://api.github.com/gists/{gist_id}"
            response = get_session().get(url)
            response.encoding = "utf-8"
            if response.status_code == 200:
                data = response.json()
                gists = []
                for filename, info in data["files"].items():
                    code = info["content"]
                    language = detect_language(filename, code)
                    gists.append(f"```{language}\n{code}\n```")
                return "\n\n".join(gists)
            print(f"Fetch gist error: {response.status_code}")
        return ""


def is_block_element(element_name: str) -> bool:
    return element_name in BLOCK_ELEMENTS


def is_pure_block_children(element: Tag) -> bool:
    for child in element.children:
        if isinstance(child, NavigableString):
            if child.strip():  # 有非空文本
                return False
        elif isinstance(child, Tag) and not is_block_element(child.name):
            return False
    return True
