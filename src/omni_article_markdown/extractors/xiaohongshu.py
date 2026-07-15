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
    platform_name = "小红书"

    @override
    def extract_tags(self) -> list[str]:
        # 从 JSON tagList 提取标签
        json_data = self._extract_initial_state()
        if not json_data:
            return super().extract_tags()
        note_map = json_data.get("note", {}).get("noteDetailMap", {})
        tags: list[str] = []
        for nid, ninfo in note_map.items():
            note = ninfo.get("note", {})
            for t in note.get("tagList", []):
                name = t.get("name", "")
                if name:
                    tags.append(name)
            if tags:
                break
        return tags

    @override
    def extract_author(self) -> str:
        # 从 JSON user.nickname 提取作者
        json_data = self._extract_initial_state()
        if json_data:
            note_map = json_data.get("note", {}).get("noteDetailMap", {})
            for ninfo in note_map.values():
                nickname = ninfo.get("note", {}).get("user", {}).get("nickname", "")
                if nickname:
                    return nickname
        return super().extract_author()

    @override
    def extract_publish_date(self) -> str:
        # 从 JSON note.time 提取发布时间（毫秒时间戳）
        json_data = self._extract_initial_state()
        if json_data:
            note_map = json_data.get("note", {}).get("noteDetailMap", {})
            for ninfo in note_map.values():
                ts = ninfo.get("note", {}).get("time", 0)
                if ts:
                    from ..utils import _normalize_date
                    return _normalize_date(str(ts))
        return super().extract_publish_date()

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
            note_type = note.get("type", "normal")
            video_info = note.get("video", {})

            # 从 desc 中移除标签文本（小红书把 #话题# 混在正文末尾）
            tag_names = [t.get("name", "") for t in tag_list if t.get("name")]
            clean_desc = desc
            for name in tag_names:
                # 移除 #话题名[话题]# 和 #话题名 两种形式
                clean_desc = clean_desc.replace(f"#{name}[话题]#", "")
                clean_desc = re.sub(r"#" + re.escape(name) + r"(?![\w])", "", clean_desc)
            clean_desc = clean_desc.strip()

            # 构造 body Tag
            body = self._build_body_tag(title, clean_desc, image_list, tag_names, interact, note_type, video_info)

            url = self.extract_url()
            article = Article(
                title=title or "无标题",
                url=url,
                description="",
                body=body,
                platform=self.platform_name,
                author=self.extract_author(),
                tags=self.extract_tags(),
                publish_date=self.extract_publish_date(),
            )
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
        note_type: str = "normal",
        video_info: dict | None = None,
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

        # 视频（视频类笔记提取视频地址）
        if note_type == "video" and video_info:
            video_url = self._extract_video_url(video_info)
            if video_url:
                video_p = soup.new_tag("p")
                a_tag = soup.new_tag("a", attrs={"href": video_url})
                a_tag.string = "视频"
                video_p.append(a_tag)
                # 同时加 video 标签让 parser 收集到媒体段
                video_tag = soup.new_tag("video", attrs={"src": video_url, "title": "视频"})
                video_p.append(video_tag)
                body.append(video_p)

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

    def _extract_video_url(self, video_info: dict) -> str:
        """从 video_info 中提取视频地址"""
        # mediaV2 可能是 JSON 字符串
        media_v2 = video_info.get("mediaV2", {})
        if isinstance(media_v2, str):
            try:
                media_v2 = json.loads(media_v2)
            except json.JSONDecodeError:
                media_v2 = {}
        stream = media_v2.get("stream", {})
        h264_list = stream.get("h264", [])
        if h264_list:
            url = h264_list[0].get("master_url", "")
            if url:
                return url
        # 降级 media.stream.h264[0].master_url
        media = video_info.get("media", {})
        media_stream = media.get("stream", {})
        h264_list = media_stream.get("h264", [])
        if h264_list:
            url = h264_list[0].get("master_url", "")
            if url:
                return url
        return ""

    @override
    def extract_img(self, element: Tag) -> Tag:
        """图片已在 _build_body_tag 中处理，这里直接返回"""
        return element

    @override
    def extract_video(self, element: Tag) -> Tag:
        """视频已在 _build_body_tag 中处理，这里直接返回"""
        return element
