"""单图 URL 获取（不下载）：_pre_images[0] → GitHub 社交预览（零请求）→ og:image。"""

import re

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from config import IMAGE_DOWNLOAD_TIMEOUT, REQUEST_HEADERS


def _og_image(url: str) -> str:
    """从页面 meta 标签中提取 og:image / twitter:image。"""
    try:
        r = requests.get(
            url, headers=REQUEST_HEADERS,
            timeout=(8, IMAGE_DOWNLOAD_TIMEOUT), allow_redirects=True,
        )
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            for selector in [
                ("meta", {"property": "og:image"}),
                ("meta", {"name": "og:image"}),
                ("meta", {"property": "twitter:image"}),
                ("meta", {"name": "twitter:image"}),
                ("meta", {"name": "twitter:image:src"}),
            ]:
                tag = soup.find(*selector)
                if tag:
                    src = tag.get("content", "").strip()
                    if src:
                        if not src.startswith("http"):
                            src = urljoin(url, src)
                        return src
    except Exception:
        pass
    return ""


def _github_preview(url: str) -> str:
    """GitHub 社交预览 URL（零 HTTP 请求）。"""
    m = re.match(r"https?://github\.com/([^/]+)/([^/#?]+)", url)
    if m:
        return f"https://opengraph.githubassets.com/1/{m.group(1)}/{m.group(2)}"
    return ""


def fetch_image_for_item(item: dict) -> str:
    """
    返回单个图片 URL，不下载到本地。
    优先级：_pre_images[0] → GitHub 社交预览（零请求）→ og:image。
    同时弹出并丢弃 item 中的 _pre_images 临时字段。
    """
    pre_images = item.pop("_pre_images", [])

    # 优先级 0：数据源预提供（Reddit 预览图、Dev.to 封面等）
    if pre_images:
        return pre_images[0]

    url = item.get("url", "")
    if not url:
        return ""

    # 优先级 1：GitHub 社交预览（零 HTTP 请求）
    gh = _github_preview(url)
    if gh:
        return gh

    # 优先级 2：页面 og:image（1 次 HTTP 请求）
    return _og_image(url)
