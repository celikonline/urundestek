from html.parser import HTMLParser
from fastapi import HTTPException
import nh3


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)

    def handle_starttag(self, tag, attrs):
        if tag == "br":
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"p", "li", "blockquote", "pre", "h2", "h3"}:
            self.parts.append("\n")


def clean_message(data, has_files=False):
    html = None
    body = data.body.strip()
    if data.body_html is not None:
        html = nh3.clean(data.body_html, tags={"p", "br", "strong", "em", "u", "s", "ul", "ol", "li", "blockquote", "pre", "code", "h2", "h3", "a"},
                         attributes={"a": {"href", "title"}}, url_schemes={"http", "https", "mailto"}, link_rel="noopener noreferrer nofollow")
        text = PlainText()
        text.feed(html)
        body = "".join(text.parts).strip()
    if len(body) > 10000:
        raise HTTPException(422, "Mesaj en fazla 10.000 karakter olabilir.")
    if len(body) < 2 and not has_files:
        raise HTTPException(422, "En az iki karakterlik mesaj yazın veya dosya ekleyin.")
    return body, html
