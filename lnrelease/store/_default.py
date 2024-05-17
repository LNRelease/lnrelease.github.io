from __future__ import annotations

from session import Session


def equal(a: str, b: str) -> bool:
    return a == b


def hash_link(link: str) -> int:
    return hash(link)


def normalise(session: Session, link: str) -> str | None:
    return link
