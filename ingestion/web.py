"""Web page extraction (INGEST_PLAN.md §5.3): fetch, keep the article, split it at h2/h3."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import urldefrag

import requests
from bs4 import BeautifulSoup, Tag

USER_AGENT = "LearnOrthodoxyAI/1.0 (+https://github.com/jazrs1/learn-orthodoxy-ai)"
REMOVE_SELECTORS = ("script", "style", "nav", "footer", "noscript")
CONTENT_SELECTORS = ("article", "main", "[role='main']", ".post-content", ".entry-content")
SECTION_TAGS = ("h2", "h3")


@dataclass
class WebSection:
    heading: str
    paragraphs: List[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n\n".join(self.paragraphs)


@dataclass
class WebPage:
    url: str
    title: str
    sections: List[WebSection]
    content_sha1: str

    @property
    def url_hash(self) -> str:
        return hashlib.sha1(self.url.encode("utf-8")).hexdigest()[:16]


def normalize_url(url: str) -> str:
    return urldefrag((url or "").strip())[0]


def fetch_html(url: str, timeout: float = 30.0) -> str:
    response = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    return response.text


def _title(soup: BeautifulSoup, url: str) -> str:
    h1 = soup.find("h1")
    if h1:
        title = " ".join(h1.get_text(" ", strip=True).split())
        if title:
            return title
    if soup.title and soup.title.string:
        return " ".join(soup.title.string.split())
    return url


def content_root(soup: BeautifulSoup) -> Tag:
    for selector in REMOVE_SELECTORS:
        for node in soup.select(selector):
            node.decompose()
    for selector in CONTENT_SELECTORS:
        root = soup.select_one(selector)
        if root:
            return root
    return soup.body or soup


def parse_page(url: str, html: str) -> WebPage:
    """Split the article into sections at h2/h3; text before the first heading is the page intro."""
    soup = BeautifulSoup(html, "html.parser")
    title = _title(soup, url)
    root = content_root(soup)
    sections: List[WebSection] = [WebSection(heading="")]
    seen = set()
    for node in root.find_all(["h1", "h2", "h3", "h4", "p", "li", "blockquote"]):
        text = " ".join(node.get_text(" ", strip=True).split())
        if len(text) < 2 or text in seen or node.find_parent(["li", "blockquote"]) is not None and node.name == "p":
            continue
        seen.add(text)
        if node.name in SECTION_TAGS:
            sections.append(WebSection(heading=text))
        elif node.name == "h1":
            continue
        else:
            sections[-1].paragraphs.append(text)
    sections = [section for section in sections if section.paragraphs]
    digest = hashlib.sha1("\n".join(s.heading + "\n" + s.text for s in sections).encode("utf-8")).hexdigest()
    return WebPage(url=normalize_url(url), title=title, sections=sections, content_sha1=digest)


def extract_page(url: str, html: Optional[str] = None) -> WebPage:
    url = normalize_url(url)
    return parse_page(url, html if html is not None else fetch_html(url))
