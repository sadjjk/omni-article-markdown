from dataclasses import dataclass, field
from pathlib import Path

from bs4 import BeautifulSoup

from .extractor import Article, ExtractorFactory
from .parser import HtmlMarkdownParser
from .reader import ReaderFactory
from .reporter import Reporter
from .utils import to_snake_case


@dataclass
class ReaderContext:
    raw_html: str


@dataclass
class ExtractorContext:
    article: Article


@dataclass
class ParserContext:
    title: str
    markdown: str
    media_images: list[tuple[str, str]] = field(default_factory=list)
    media_videos: list[tuple[str, str]] = field(default_factory=list)


class OmniArticleMarkdown:
    DEFAULT_SAVE_PATH = "./"

    def __init__(self, url_or_path: str, reporter: Reporter | None = None, verify_ssl: bool = True):
        self.url_or_path = url_or_path
        self.reporter = reporter
        self.verify_ssl = verify_ssl
        self.parser_ctx: ParserContext | None = None

    def parse(self):
        reader_ctx = self._read_html(self.url_or_path)
        extractor_ctx = self._extract_article(reader_ctx)
        self.parser_ctx = self._parse_html(extractor_ctx)

    def result(self):
        if not self.parser_ctx:
            raise ValueError("No parsed content available. Please call parse() first.")
        return self.parser_ctx.markdown

    def save(
        self,
        save_path: str = "",
        is_save_imgs: bool = False,
        is_save_videos: bool = False,
        save_imgs_dir: str = "imgs",
        save_videos_dir: str = "videos",
        json_output: bool = False,
    ) -> str:
        if not self.parser_ctx:
            raise ValueError("No parsed content to save. Please call parse() first.")
        save_path = save_path or self.DEFAULT_SAVE_PATH
        file_path = Path(save_path)
        # 路径不存在且无后缀 → 当目录处理
        if not file_path.exists() and not file_path.suffix:
            file_path.mkdir(parents=True, exist_ok=True)
        if file_path.is_dir():
            from datetime import datetime, timezone
            from .utils import to_snake_case
            from .media_downloader import (
                MediaDownloader, compute_hash, read_cache, write_cache,
                resolve_save_dir, replace_urls, rebuild_media_section, _relative_path,
            )
            import re as _re

            created_str = datetime.now(tz=timezone.utc).strftime("%Y%m%d")
            m = _re.search(r"^platform: (.+)$", self.parser_ctx.markdown, _re.MULTILINE)
            platform = m.group(1).strip() if m else "其他"
            file_prefix = f"{created_str}-{platform}"
            filename = f"{file_prefix}-{to_snake_case(self.parser_ctx.title)}.md"
            file_path = file_path / filename
        else:
            from .media_downloader import (
                MediaDownloader, compute_hash, read_cache, write_cache,
                resolve_save_dir, replace_urls, rebuild_media_section, _relative_path,
            )
            from datetime import datetime, timezone
            import re as _re
            created_str = datetime.now(tz=timezone.utc).strftime("%Y%m%d")
            m = _re.search(r"^platform: (.+)$", self.parser_ctx.markdown, _re.MULTILINE)
            platform = m.group(1).strip() if m else "其他"
            file_prefix = f"{created_str}-{platform}"

        # hash 去重
        content_hash = compute_hash(self.parser_ctx.markdown)
        cache = read_cache(Path(file_path).parent if file_path.is_file() else save_path)
        cache_key = self.url_or_path
        if cache_key in cache and cache[cache_key].get("content_hash") == content_hash:
            old_md = cache[cache_key].get("md_file", "")
            old_path = Path(save_path) / old_md if old_md else None
            if old_path and old_path.exists():
                if self.reporter:
                    self.reporter(f"内容未变化，跳过: {old_path.resolve()}")
                return str(old_path.resolve())

        # 确保目录存在
        save_dir_path = Path(save_path) if Path(save_path).is_dir() else Path(save_path).parent
        save_dir_path.mkdir(parents=True, exist_ok=True)

        # 写入 MD（远程 URL 版本）
        with file_path.open("w", encoding="utf-8") as f:
            f.write(self.parser_ctx.markdown)

        # 下载媒体
        downloaded: dict[str, str] = {}
        img_dir = resolve_save_dir(save_dir_path, save_imgs_dir)
        vid_dir = resolve_save_dir(save_dir_path, save_videos_dir)

        if is_save_imgs and self.parser_ctx.media_images:
            img_urls = [url for url, _ in self.parser_ctx.media_images]
            downloader = MediaDownloader(img_dir, file_prefix, self.verify_ssl)
            downloaded.update(downloader.download_all(img_urls, is_video=False))

        if is_save_videos and self.parser_ctx.media_videos:
            vid_urls = [url for url, _ in self.parser_ctx.media_videos]
            downloader = MediaDownloader(vid_dir, file_prefix, self.verify_ssl)
            downloaded.update(downloader.download_all(vid_urls, is_video=True))

        # 替换正文 URL + 重新生成媒体段
        if downloaded:
            markdown = self.parser_ctx.markdown
            # 替换正文里的远程 URL
            for remote_url, local_name in downloaded.items():
                # 判断是图片还是视频目录
                if remote_url in [u for u, _ in self.parser_ctx.media_images]:
                    local_path = _relative_path(img_dir / local_name, file_path.parent)
                else:
                    local_path = _relative_path(vid_dir / local_name, file_path.parent)
                markdown = markdown.replace(remote_url, str(local_path))

            # 重新生成媒体段
            markdown = rebuild_media_section(
                markdown, downloaded,
                self.parser_ctx.media_images, self.parser_ctx.media_videos,
                img_dir, vid_dir, file_path.parent,
            )

            # 重新写入
            with file_path.open("w", encoding="utf-8") as f:
                f.write(markdown)

        # 更新缓存
        write_cache(save_dir_path, self.url_or_path, content_hash, file_path.name)
        return str(file_path.resolve())

    def _read_html(self, url_or_path: str) -> ReaderContext:
        reader = ReaderFactory.create(url_or_path, reporter=self.reporter, verify_ssl=self.verify_ssl)
        raw_html = reader.read()
        return ReaderContext(raw_html)

    def _extract_article(self, ctx: ReaderContext) -> ExtractorContext:
        soup = BeautifulSoup(ctx.raw_html, "html5lib")
        extract = ExtractorFactory.create(soup, self.url_or_path)
        article = extract.extract()
        if not article:
            raise ValueError("Failed to extract article content.")
        return ExtractorContext(article)

    def _parse_html(self, ctx: ExtractorContext) -> ParserContext:
        parser = HtmlMarkdownParser(ctx.article)
        result = parser.parse()
        return ParserContext(
            title=result[0],
            markdown=result[1],
            media_images=parser.media_images,
            media_videos=parser.media_videos,
        )
