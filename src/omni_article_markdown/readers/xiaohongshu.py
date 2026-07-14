import re
import urllib.parse
from typing import override

from ..reader import Reader


class XhsReader(Reader):
    """
    小红书笔记 Reader

    小红书分享链接（xhslink.com 短链）需要重定向获取 xsec_token，
    token 含 = 号必须 URL encode，否则被截断导致 404。
    页面内容通过 SSR 渲染在 __INITIAL_STATE__ JSON 中，curl 直接抓即可。
    """

    @override
    def can_handle(self) -> bool:
        return "xhslink.com" in self.url_or_path or "xiaohongshu.com/discovery/item/" in self.url_or_path

    @override
    def read(self) -> str:
        url = self.url_or_path

        # 如果是 xhslink 短链，先重定向拿完整 URL
        if "xhslink.com" in url:
            url = self._resolve_short_url()
            self.report(f"短链重定向: {url}")

        # 如果已经有了 xsec_token（完整 URL），直接请求
        html = self._fetch_html(url)

        if len(html) < 1000:
            raise Exception(f"页面返回过小（{len(html)} bytes），可能被拒绝。检查 xsec_token 是否完整。")

        return html

    def _resolve_short_url(self) -> str:
        """短链重定向，拿完整 URL（含 xsec_token）"""
        import subprocess

        result = subprocess.run(
            ["curl", "-s", "-L", "-o", "/dev/null", "-w", "%{url_effective}", self.url_or_path],
            capture_output=True, text=True, timeout=15,
        )
        final_url = result.stdout.strip()
        if not final_url or "xiaohongshu.com" not in final_url:
            raise Exception(f"短链重定向失败: {final_url}")
        return final_url

    def _fetch_html(self, url: str) -> str:
        """请求页面 HTML，处理 xsec_token URL encode"""
        parsed = urllib.parse.urlparse(url)

        # 提取 xsec_token 并 URL encode
        params = urllib.parse.parse_qs(parsed.query)
        xsec_token = params.get("xsec_token", [""])[0]

        if xsec_token:
            encoded_token = urllib.parse.quote(xsec_token)
            # 重建 URL，替换 token
            new_params = []
            for key, vals in urllib.parse.parse_qsl(parsed.query):
                if key == "xsec_token":
                    new_params.append((key, encoded_token))
                else:
                    new_params.extend([(key, v) for v in ([vals] if isinstance(vals, str) else vals)])
            query = urllib.parse.urlencode(new_params)
            url = urllib.parse.urlunparse(parsed._replace(query=query))

        response = self.session.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
        )
        response.encoding = "utf-8"
        return response.text
