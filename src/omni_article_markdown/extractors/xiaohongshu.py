import json
import re
from typing import override

from bs4 import BeautifulSoup
from bs4.element import Tag

from ..extractor import Article, Extractor


class XhsExtractor(Extractor):
    """
    小红书笔记 Extractor

    小红书页面内容通过 SSR 渲染在 __INITIAL_STATE__ JSON 中。
    从 JSON 提取标题、正文、图片、标签，构造 BeautifulSoup Tag 返回。
    """

    @override
    def can_handle(self) -> bool:
        return "xiaohongshu.com" in (self.extract_url() or "")

    @override
    def extract_article(self) -> Article | None:
        # 从 __INITIAL_STATE__ 提取 JSON
        json_data = self._extract_initial_state()
        if not json_data:
            return None

        note_map = json_data.get("note", {}).get("noteDetailMap", {})
        if not note_map:
            return None

        # 取第一个笔记
        for nid, ninfo in note_map.items():
            note = ninfo.get("note", {})
            if not note:
                continue

            title = note.get("title", "") or ""
            desc = note.get("desc", "") or ""
            image_list = note.get("imageList", [])
            tag_list = note.get("tagList", [])
            interact = note.get("interactInfo", {})

            # 从 desc 中移除标签文本（小红书把 #话题# 混在正文末尾）
            tag_names = [t.get("name", "") for t in tag_list if t.get("name")]
            clean_desc = desc
            for name in tag_names:
                # 移除 #话题名[话题]# 和 #话题名 两种形式
                clean_desc = clean_desc.replace(f"#{name}[话题]#", "")
                clean_desc = re.sub(r"#" + re.escape(name) + r"(?![\w])", "", clean_desc)
            clean_desc = clean_desc.strip()

            # 构造 body Tag
            body = self._build_body_tag(title, clean_desc, image_list, tag_names, interact)

            url = self.extract_url()
            article = Article(title=title or "无标题", url=url, description=clean_desc, body=body)
            self.remove_duplicate_titles(article)
            return article

        return None

    def _extract_initial_state(self) -> dict | None:
        """从 HTML 中提取 __INITIAL_STATE__ JSON"""
        for script in self.soup.find_all("script"):
            text = script.string or script.get_text()
            if not text:
                continue
            start = text.find("__INITIAL_STATE__=")
            if start == -1:
                continue
            start += len("__INITIAL_STATE__=")
            json_str = text[start:].strip().rstrip(";").replace(":undefined", ":null")
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                # 尝试截取到第一个合法的 JSON 结尾
                continue
        return None

    def _build_body_tag(
        self,
        title: str,
        desc: str,
        image_list: list,
        tag_names: list[str],
        interact: dict,
    ) -> Tag:
        """构造 body Tag，让 Parser 正常处理"""
        soup = BeautifulSoup("", "html5lib")
        body = soup.new_tag("body")

        # 标题
        if title:
            h1 = soup.new_tag("h1")
            h1.string = title
            body.append(h1)

        # 正文（按换行分段）
        if desc:
            for line in desc.split("\n"):
                line = line.strip()
                if not line:
                    continue
                p = soup.new_tag("p")
                p.string = line
                body.append(p)

        # 图片（每张独占一行，加序号）
        for idx, img_info in enumerate(image_list, 1):
            img_url = img_info.get("urlDefault") or img_info.get("url") or ""
            if not img_url:
                continue
            # 确保 https
            if img_url.startswith("http://"):
                img_url = "https://" + img_url[7:]
            img_tag = soup.new_tag("img", attrs={"src": img_url, "alt": f"图片 {idx}"})
            body.append(img_tag)
            # 用 <br> 强制换行
            br = soup.new_tag("br")
            body.append(br)

        # 标签
        if tag_names:
            tag_p = soup.new_tag("p")
            tag_p.string = " ".join(f"#{t}" for t in tag_names)
            body.append(tag_p)

        # 互动数据
        liked = interact.get("likedCount", "")
        collected = interact.get("collectedCount", "")
        comment = interact.get("commentCount", "")
        if liked or collected or comment:
            interact_p = soup.new_tag("p")
            parts = []
            if liked:
                parts.append(f"{liked} 赞")
            if collected:
                parts.append(f"{collected} 收藏")
            if comment:
                parts.append(f"{comment} 评论")
            interact_p.string = " / ".join(parts)
            body.append(interact_p)

        return body

    @override
    def extract_img(self, element: Tag) -> Tag:
        """图片已在 _build_body_tag 中处理，这里直接返回"""
        return element
