"""Публичный HTML тарифов: разрешённые элементы, ссылки и стили."""
import html
import re
from urllib.parse import urlsplit
from bs4 import BeautifulSoup, Comment, NavigableString, Tag

TAGS = set("p div span br hr h2 h3 h4 h5 h6 strong b em i u s ul ol li blockquote pre code table caption colgroup col thead tbody tfoot tr th td a img video source iframe".split())
DROP = set("script style svg math object embed form input button textarea select option template noscript base link meta".split())
VOID = {"br", "hr", "img", "source", "col"}
FRAME_PATHS = {
    "yandex.ru": ("/map-widget/",),
    "www.youtube.com": ("/embed/",),
    "www.youtube-nocookie.com": ("/embed/",),
    "player.vimeo.com": ("/video/",),
    "rutube.ru": ("/play/embed/",),
}


def safe_url(value: str, kind: str = "link") -> str:
    """Разрешить HTTPS и локальные пути; iframe только известных сервисов."""
    value = value.strip()
    if any(ord(c) < 32 for c in value) or "\\" in value:
        return ""
    try:
        parsed = urlsplit(value)
        if parsed.username or parsed.password or parsed.port not in (None, 443):
            return ""
    except ValueError:
        return ""
    if kind == "frame":
        prefixes = FRAME_PATHS.get(parsed.hostname, ())
        return value if parsed.scheme == "https" and parsed.path.startswith(prefixes) else ""
    if parsed.scheme == "https" and parsed.hostname:
        return value
    if kind == "link" and parsed.scheme in {"mailto", "tel"}:
        return value
    if not parsed.scheme and not parsed.netloc and not value.startswith("//"):
        if value.startswith(("/", "#")):
            return value
        if value.startswith(("images/", "media/")):
            return "/" + value
    return ""


def safe_style(value: str) -> str:
    """Оставить оформление без URL, выражений и перекрытия интерфейса."""
    result = []
    for part in value.split(";"):
        key, sep, val = part.partition(":")
        key, val = key.strip().lower(), val.strip().lower()
        valid = False
        if key in {"color", "background-color"}:
            valid = bool(re.fullmatch(r"#[0-9a-f]{3,8}|[a-z]{1,20}|rgba?\([0-9.,% ]+\)", val))
        elif key in {"font-size", "width", "height", "max-width", "border-width", "padding"}:
            valid = bool(re.fullmatch(r"\d{1,4}(?:\.\d{1,2})?(?:px|pt|em|rem|%)", val))
        elif key in {"margin-left", "margin-right"}:
            valid = val == "auto"
        elif key == "text-align":
            valid = val in {"left", "right", "center", "justify"}
        elif key == "font-weight":
            valid = val in {"normal", "bold", "400", "700"}
        elif key == "font-style":
            valid = val in {"normal", "italic"}
        elif key == "text-decoration":
            valid = val in {"none", "underline", "line-through"}
        elif key == "display":
            valid = val in {"block", "inline", "inline-block"}
        elif key == "font-family":
            valid = bool(re.fullmatch(r"[a-z ,'-]{1,100}", val))
        if valid:
            result.append(f"{key}:{val}")
    return ";".join(result)


def convert_joomla_source(value: str) -> str:
    """Раскодировать HTML Joomla Source, не исполняя его содержимое."""
    def decode(match):
        fragment = BeautifulSoup(match.group(1), "html.parser")
        # В Joomla код может находиться внутри span как экранированный текст.
        if "&lt;" in match.group(1):
            return html.unescape(fragment.get_text())
        return match.group(1)
    return re.sub(r"\{source(?:\s+[^}]*)?\}(.*?)\{/source\}", decode, value, flags=re.S | re.I)


def sanitize_prices(value: str) -> str:
    """Собрать HTML заново: входные атрибуты не попадают в вывод напрямую."""
    soup = BeautifulSoup(convert_joomla_source(value or ""), "html.parser")

    def render(node):
        if isinstance(node, Comment):
            return ""
        if isinstance(node, NavigableString):
            return html.escape(str(node))
        if not isinstance(node, Tag) or node.name in DROP:
            return ""
        children = "".join(render(child) for child in node.children)
        name = node.name.lower()
        if name == "font":
            declarations = []
            if node.get("color"):
                declarations.append("color:" + str(node["color"]))
            sizes = {"1": "10px", "2": "13px", "3": "16px", "4": "18px", "5": "24px", "6": "32px", "7": "48px"}
            if str(node.get("size")) in sizes:
                declarations.append("font-size:" + sizes[str(node["size"])])
            if node.get("face"):
                declarations.append("font-family:" + str(node["face"]))
            style = safe_style(";".join(declarations))
            return '<span style="' + html.escape(style, quote=True) + '">' + children + '</span>' 
        if name not in TAGS:
            return children
        attrs = {}
        for key in ("title", "alt"):
            if node.get(key):
                attrs[key] = str(node[key])
        if node.get("style"):
            style = safe_style(str(node["style"]))
            if style:
                attrs["style"] = style
        for key in ("width", "height", "colspan", "rowspan", "span"):
            val = str(node.get(key, ""))
            if re.fullmatch(r"[1-9]\d{0,3}", val):
                attrs[key] = val
        classes = node.get("class", [])
        allowed = {"table-responsive", "table", "table-striped", "table-bordered", "table-hover", "table-condensed"}
        classes = [x for x in classes if x in allowed]
        if classes:
            attrs["class"] = " ".join(classes)
        if name == "a":
            url = safe_url(str(node.get("href", "")))
            if url:
                attrs.update(href=url, rel="noopener noreferrer")
        if name in {"img", "video", "source", "iframe"}:
            url = safe_url(str(node.get("src", "")), "frame" if name == "iframe" else "media")
            if name in {"img", "iframe", "source"} and not url:
                return ""
            if url:
                attrs["src"] = url
        if name == "img":
            attrs["loading"] = "lazy"
        if name == "video":
            attrs.update(controls="controls", preload="metadata")
            poster = safe_url(str(node.get("poster", "")), "media")
            if poster:
                attrs["poster"] = poster
        if name == "source" and node.get("type") in {"video/mp4", "video/webm", "video/ogg"}:
            attrs["type"] = node["type"]
        if name == "iframe":
            attrs.update(sandbox="allow-scripts allow-same-origin allow-presentation", loading="lazy", allowfullscreen="", referrerpolicy="strict-origin-when-cross-origin", title=attrs.get("title", "Карта или видео"))
        attributes = "".join(f' {key}="{html.escape(str(val), quote=True)}"' for key, val in sorted(attrs.items()))
        opening = f"<{name}{attributes}>"
        return opening if name in VOID else opening + children + f"</{name}>"

    return "".join(render(child) for child in soup.children)
