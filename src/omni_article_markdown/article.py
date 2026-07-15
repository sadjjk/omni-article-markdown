from dataclasses import dataclass, field

from bs4.element import Tag


@dataclass
class Article:
    title: str
    url: str | None
    description: str | None
    body: Tag | str
    platform: str = ""
    author: str = ""
    tags: list[str] = field(default_factory=list)
    publish_date: str = ""
