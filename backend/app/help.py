"""Customer-facing search over the knowledge base so simple questions never become tickets."""
import re
from functools import lru_cache
from .ai import knowledge_text

SKIP_HEADINGS = {"asistanın yapmayacağı işler", "üslup", "ürün hakkında"}
STOPWORDS = {"ve", "ile", "için", "bir", "bu", "da", "de", "mi", "mı", "mu", "mü", "ne", "nasıl", "neden", "var", "yok", "olan", "ama", "veya", "ben", "biz", "siz"}
TR_LOWER = str.maketrans("IİÇĞÖŞÜ", "ıiçğöşü")


def normalize(text):
    return re.sub(r"[^a-z0-9çğıöşü ]+", " ", text.translate(TR_LOWER).lower())


def terms(text):
    return {word for word in normalize(text).split() if len(word) >= 3 and word not in STOPWORDS}


def stem(word):
    """Crude Turkish suffix trim so 'raporunu' matches 'rapor'; good enough for ranking, not for grammar."""
    for size in (4, 3, 2, 1):
        if len(word) - size >= 4:
            return word[: len(word) - size]
    return word


@lru_cache(maxsize=1)
def sections_for(text):
    """Split the markdown knowledge base into (title, body) sections under third-level headings."""
    result = []
    for match in re.finditer(r"^### (.+?)\n(.*?)(?=^###? |\Z)", text, re.S | re.M):
        title, body = match.group(1).strip(), match.group(2).strip()
        if title.translate(TR_LOWER).lower() in SKIP_HEADINGS or not body:
            continue
        lines = [re.sub(r"^\s*-\s*", "", line).strip() for line in body.splitlines() if line.strip()]
        result.append({"title": title, "lines": lines})
    return result


def search(query, limit=3):
    query_terms = {stem(word) for word in terms(query)}
    if not query_terms:
        return []
    scored = []
    for section in sections_for(knowledge_text()):
        title_terms = {stem(word) for word in terms(section["title"])}
        body_terms = {stem(word) for word in terms(" ".join(section["lines"]))}
        score = 3 * len(query_terms & title_terms) + len(query_terms & body_terms)
        if score:
            scored.append((score, section))
    scored.sort(key=lambda item: -item[0])
    return [{"title": section["title"], "lines": section["lines"][:6]} for _, section in scored[:limit]]
