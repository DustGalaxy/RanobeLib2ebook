import re
import base64
from urllib.parse import urlparse

import jwt
from FB2 import Author


def is_url(url) -> bool:
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


def set_authors(authors) -> list:
    result_list = []
    for author in authors:
        result_list.append(
            Author(
                firstName=author.get("name"),
            )
        )

    return result_list


def is_jwt(token) -> bool:
    parts = token.split(".")
    if len(parts) != 3:
        return False

    try:
        header = base64.urlsafe_b64decode(parts[0] + "==").decode("utf-8")
        payload = base64.urlsafe_b64decode(parts[1] + "==").decode("utf-8")
    except (ValueError, base64.binascii.Error):
        return False

    try:
        jwt.decode(token, options={"verify_signature": False})
    except jwt.DecodeError:
        return False

    return True


def is_html(text) -> bool:
    html_tag_pattern = re.compile(r"<(\/?[^>]+)>")

    tags = html_tag_pattern.findall(text)

    if not tags:
        return False

    known_html_tags = {
        "html",
        "head",
        "body",
        "title",
        "meta",
        "link",
        "script",
        "style",
        "div",
        "span",
        "p",
        "a",
        "img",
        "ul",
        "ol",
        "li",
        "table",
        "tr",
        "td",
        "th",
        "form",
        "input",
        "button",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "br",
        "hr",
    }

    # Проверка, есть ли в найденных тегах известные HTML-теги
    for tag in tags:
        tag_name = tag.split()[0].strip("/")
        if tag_name.lower() in known_html_tags:
            return True

    return False
