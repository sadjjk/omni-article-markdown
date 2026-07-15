import asyncio
import hashlib
import json
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

from .parser import MEDIA_SECTION_TITLE


def resolve_save_dir(save_path: str | Path, sub_dir: str) -> Path:
    # 相对路径相对于 save_path，绝对路径直接用
    save_path = Path(save_path)
    sub = Path(sub_dir)
    if sub.is_absolute():
        return sub
    return save_path / sub


def _get_filename(url: str, index: int, is_video: bool, file_prefix: str) -> str:
    # 从 URL 提取文件名，无扩展名用序号兜底
    path = urlparse(url).path
    name = Path(path).name
    name = name.split('!')[0]
    name = name.split('?')[0]
    valid_img_exts = ('.jpg', '.jpeg', '.png', '.gif', '.webp')
    valid_vid_exts = ('.mp4', '.mov', '.avi', '.webm')
    valid_exts = valid_vid_exts if is_video else valid_img_exts
    suffix = Path(name).suffix.lower()
    if suffix not in valid_exts:
        prefix = 'video' if is_video else 'img'
        default_ext = '.mp4' if is_video else '.jpg'
        name = f"{prefix}_{index}{default_ext}"
    if len(name) > 50:
        stem = Path(name).stem[:45]
        suffix = Path(name).suffix
        name = f"{stem}{suffix}"
    return f"{file_prefix}-{name}"


def _relative_path(target: Path, base: Path) -> Path:
    # 计算相对路径，算不出用绝对路径
    try:
        return target.relative_to(base)
    except ValueError:
        return target.resolve()


def replace_urls(markdown: str, url_mapping: dict[str, str], save_dir: Path, md_file: Path) -> str:
    # 替换正文里的远程 URL 为本地路径（不动媒体段）
    for remote_url, local_name in url_mapping.items():
        local_path = _relative_path(save_dir / local_name, md_file.parent)
        markdown = markdown.replace(remote_url, str(local_path))
    return markdown


def rebuild_media_section(
    markdown: str,
    downloaded: dict[str, str],
    media_images: list[tuple[str, str]],
    media_videos: list[tuple[str, str]],
    img_dir: Path,
    vid_dir: Path,
    md_dir: Path,
) -> str:
    # 找到旧媒体段，替换为新的
    from .parser import MEDIA_SECTION_TITLE, MEDIA_VIDEO_TITLE, MEDIA_IMAGE_TITLE

    pattern = r"\n\n---\n\n## " + re.escape(MEDIA_SECTION_TITLE) + r"\n.*$"
    old_section = re.search(pattern, markdown, re.DOTALL)
    if not old_section:
        return markdown

    sections = [f"\n\n---\n\n## {MEDIA_SECTION_TITLE}\n\n"]
    if media_videos:
        sections.append(f"### {MEDIA_VIDEO_TITLE}\n\n")
        for i, (url, desc) in enumerate(media_videos, 1):
            if url in downloaded:
                local = _relative_path(vid_dir / downloaded[url], md_dir)
                sections.append(f"{i}. [原视频]({url}) [{desc}]({local}) ✅已下载\n")
            else:
                sections.append(f"{i}. [{desc}]({url})\n")
        sections.append("\n")
    if media_images:
        sections.append(f"### {MEDIA_IMAGE_TITLE}\n\n")
        for i, (url, alt) in enumerate(media_images, 1):
            if url in downloaded:
                local = _relative_path(img_dir / downloaded[url], md_dir)
                sections.append(f"{i}. [原图]({url}) ![{alt}]({local}) ✅已下载\n")
            else:
                sections.append(f"{i}. ![{alt}]({url})\n")
        sections.append("\n")

    new_section = "".join(sections)
    return markdown[:old_section.start()] + new_section


def compute_hash(markdown: str) -> str:
    # 只算正文（去 created + 去媒体段）
    content = re.sub(r"^created:.*$", "", markdown, flags=re.MULTILINE)
    content = re.sub(r"\n\n---\n\n## " + MEDIA_SECTION_TITLE + r"\n.*$", "", content, flags=re.DOTALL)
    return hashlib.md5(content.encode()).hexdigest()


def read_cache(save_path: str | Path) -> dict:
    cache_file = Path(save_path) / ".mdcli_cache.json"
    if not cache_file.exists():
        return {}
    with open(cache_file, encoding="utf-8") as f:
        return json.load(f)


def write_cache(save_path: str | Path, url: str, content_hash: str, md_file: str):
    cache_file = Path(save_path) / ".mdcli_cache.json"
    cache = read_cache(save_path)
    cache[url] = {
        "content_hash": content_hash,
        "md_file": md_file,
        "updated": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
    }
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


class MediaDownloader:
    def __init__(self, save_dir: Path, file_prefix: str, verify_ssl: bool = True, max_workers: int = 3):
        self.save_dir = save_dir
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.file_prefix = file_prefix
        self.verify_ssl = verify_ssl
        self.max_workers = max_workers

    def download_all(self, urls: list[str], is_video: bool = False) -> dict[str, str]:
        return asyncio.run(self._download_all_async(urls, is_video))

    async def _download_all_async(self, urls: list[str], is_video: bool) -> dict[str, str]:
        sem = asyncio.Semaphore(self.max_workers)
        loop = asyncio.get_event_loop()

        async def _download_with_sem(url, idx):
            async with sem:
                await asyncio.sleep(random.uniform(0.3, 0.8))
                return await loop.run_in_executor(None, self._download_one, url, idx, is_video)

        tasks = [_download_with_sem(url, i) for i, url in enumerate(urls, 1)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        mapping = {}
        for url, result in zip(urls, results):
            if not isinstance(result, Exception) and result:
                mapping[url] = result
        return mapping

    def _download_one(self, url: str, index: int, is_video: bool = False) -> str:
        filename = _get_filename(url, index, is_video=is_video, file_prefix=self.file_prefix)
        filepath = self.save_dir / filename
        if filepath.exists():
            return filepath.name
        resp = requests.get(url, stream=True, verify=self.verify_ssl, timeout=30)
        resp.raise_for_status()
        with open(filepath, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return filepath.name
