from __future__ import annotations

import re
from codecs import lookup
from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}

INLINE_SKIP_TAGS = {"script", "style", "noscript"}
HTML_SUFFIXES = {".html", ".htm"}
ALLOWED_WEB_SUFFIXES = {"", ".html", ".htm", ".php", ".asp", ".aspx"}
FALLBACK_ENCODINGS = ("utf-8", "utf-8-sig", "cp949", "euc-kr", "iso-8859-1", "latin-1")
BOM_ENCODINGS = (
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xff\xfe", "utf-16"),
    (b"\xfe\xff", "utf-16"),
)
META_CHARSET_RE = re.compile(br"<meta[^>]+charset=['\"]?\s*([A-Za-z0-9._-]+)", re.IGNORECASE)
META_CONTENT_RE = re.compile(br"<meta[^>]+content=['\"][^>]*charset=([A-Za-z0-9._-]+)", re.IGNORECASE)
SECTION_KEYWORDS = {
    "hero": ["hero", "banner", "masthead", "intro"],
    "pricing": ["pricing", "plan", "plans", "subscription"],
    "faq": ["faq", "accordion", "questions"],
    "testimonial": ["testimonial", "review", "trusted by"],
    "contact": ["contact", "demo", "sales", "support"],
    "gallery": ["gallery", "carousel", "slider", "showcase"],
}


@dataclass(slots=True)
class Node:
    tag: str
    attrs: dict[str, str]
    children: list["Node"] = field(default_factory=list)
    text_chunks: list[str] = field(default_factory=list)


@dataclass(slots=True)
class HeadingSummary:
    level: int
    text: str


@dataclass(slots=True)
class LinkSummary:
    text: str
    target: str
    internal: bool


@dataclass(slots=True)
class FormSummary:
    action: str
    method: str
    fields: list[str] = field(default_factory=list)
    submit_labels: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SectionSummary:
    kind: str
    label: str
    headline: str
    link_count: int
    button_count: int


@dataclass(slots=True)
class Finding:
    name: str
    evidence: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PageAnalysis:
    source: str
    source_type: str
    title: str
    meta_description: str
    encoding: str = ""
    headings: list[HeadingSummary] = field(default_factory=list)
    sections: list[SectionSummary] = field(default_factory=list)
    links: list[LinkSummary] = field(default_factory=list)
    forms: list[FormSummary] = field(default_factory=list)
    features: list[Finding] = field(default_factory=list)
    components: list[Finding] = field(default_factory=list)
    flows: list[Finding] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)
    summary: str = ""
    page_role: str = "general"


@dataclass(slots=True)
class SiteAnalysis:
    source: str
    pages: list[PageAnalysis] = field(default_factory=list)
    common_components: list[Finding] = field(default_factory=list)
    feature_summary: list[Finding] = field(default_factory=list)
    flows: list[Finding] = field(default_factory=list)
    navigation: list[str] = field(default_factory=list)
    load_issues: list["LoadIssue"] = field(default_factory=list)
    generated_at: str = ""


@dataclass(slots=True)
class LoadedDocument:
    source: str
    source_type: str
    html: str
    base_url: str | None = None
    encoding: str = ""


@dataclass(slots=True)
class LoadIssue:
    source: str
    message: str


@dataclass(slots=True)
class LoadResult:
    documents: list[LoadedDocument] = field(default_factory=list)
    issues: list[LoadIssue] = field(default_factory=list)


@dataclass(slots=True)
class DecodedContent:
    source: str
    text: str
    encoding: str
    used_replacement: bool = False


class HTMLTreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node(tag="document", attrs={})
        self.stack: list[Node] = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag=tag.lower(), attrs={key.lower(): value or "" for key, value in attrs})
        self.stack[-1].children.append(node)
        if tag.lower() not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        lower_tag = tag.lower()
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == lower_tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:
        if data and self.stack[-1].tag not in INLINE_SKIP_TAGS:
            self.stack[-1].text_chunks.append(data)


def analyze_source(source: str, max_pages: int = 5, crawl_depth: int = 1, timeout: int = 10) -> SiteAnalysis:
    load_result = load_documents(source, max_pages=max_pages, crawl_depth=crawl_depth, timeout=timeout)
    pages = [analyze_document(document) for document in load_result.documents]
    normalized_source = canonicalize_url(source) if is_url(source) else str(Path(source).resolve())
    return aggregate_site(normalized_source, pages, load_result.issues)


def is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def load_documents(source: str, max_pages: int, crawl_depth: int, timeout: int) -> LoadResult:
    if is_url(source):
        return crawl_url(source, max_pages=max_pages, crawl_depth=crawl_depth, timeout=timeout)

    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"Source not found: {source}")

    if path.is_dir():
        html_files = sorted(
            item
            for item in path.rglob("*")
            if item.is_file() and item.suffix.lower() in HTML_SUFFIXES
        )[:max_pages]
        if not html_files:
            raise ValueError(f"No HTML files found under directory: {source}")
        documents: list[LoadedDocument] = []
        issues: list[LoadIssue] = []
        for item in html_files:
            document, document_issues = load_file_document(item, "directory-file")
            documents.append(document)
            issues.extend(document_issues)
        return LoadResult(documents=documents, issues=issues)

    document, issues = load_file_document(path, "file")
    return LoadResult(documents=[document], issues=issues)


def load_file_document(path: Path, source_type: str) -> tuple[LoadedDocument, list[LoadIssue]]:
    decoded = decode_html_bytes(path.read_bytes())
    issues: list[LoadIssue] = []
    if decoded.used_replacement:
        issues.append(
            LoadIssue(
                source=str(path.resolve()),
                message=f"Decoded with {decoded.encoding} using replacement characters; some text may be degraded.",
            )
        )
    return (
        LoadedDocument(
            source=str(path.resolve()),
            source_type=source_type,
            html=decoded.text,
            base_url=path.resolve().as_uri(),
            encoding=decoded.encoding,
        ),
        issues,
    )


def crawl_url(source: str, max_pages: int, crawl_depth: int, timeout: int) -> LoadResult:
    queue: deque[tuple[str, int]] = deque([(canonicalize_url(source), 0)])
    visited: set[str] = set()
    documents: list[LoadedDocument] = []
    issues: list[LoadIssue] = []
    root = urlparse(source)

    while queue and len(documents) < max_pages:
        current, depth = queue.popleft()
        if current in visited:
            continue
        visited.add(current)

        try:
            fetched = fetch_html(current, timeout=timeout)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            issues.append(LoadIssue(source=current, message=describe_load_error(exc)))
            continue

        if fetched.used_replacement:
            issues.append(
                LoadIssue(
                    source=fetched.source,
                    message=f"Decoded with {fetched.encoding} using replacement characters; some text may be degraded.",
                )
            )

        documents.append(
            LoadedDocument(
                source=fetched.source,
                source_type="url",
                html=fetched.text,
                base_url=fetched.source,
                encoding=fetched.encoding,
            )
        )
        if depth >= crawl_depth:
            continue

        root_node = parse_html(fetched.text)
        for link in extract_links(root_node, fetched.source):
            if not link.internal:
                continue
            next_url = canonicalize_url(link.target)
            parsed = urlparse(next_url)
            if parsed.netloc != root.netloc:
                continue
            if parsed.scheme not in {"http", "https"}:
                continue
            if parsed.path and Path(parsed.path).suffix.lower() not in ALLOWED_WEB_SUFFIXES:
                continue
            queue.append((next_url, depth + 1))

    return LoadResult(documents=documents, issues=issues)


def fetch_html(source: str, timeout: int) -> DecodedContent:
    request = Request(source, headers={"User-Agent": "website-benchmark/0.1"})
    with urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("Content-Type", "")
        if "html" not in content_type and content_type:
            raise HTTPError(source, response.status, f"Non-HTML content: {content_type}", response.headers, None)
        decoded = decode_html_bytes(response.read(), declared_encoding=response.headers.get_content_charset())
        return DecodedContent(
            source=canonicalize_url(response.geturl()),
            text=decoded.text,
            encoding=decoded.encoding,
            used_replacement=decoded.used_replacement,
        )


def analyze_document(document: LoadedDocument) -> PageAnalysis:
    root = parse_html(document.html)
    headings = extract_headings(root)
    links = extract_links(root, document.base_url)
    forms = extract_forms(root, document.base_url)
    sections = extract_sections(root)
    buttons = extract_buttons(root)
    title = extract_title(root)
    meta_description = extract_meta_description(root)
    page_role = infer_page_role(document.source, title, headings, links)
    features = detect_features(title, meta_description, headings, links, forms, buttons, sections, page_role)
    components = detect_components(root, sections, buttons, forms, links)
    flows = detect_page_flows(page_role, features, forms, links)
    stats = {
        "headings": len(headings),
        "sections": len(sections),
        "links": len(links),
        "internal_links": sum(1 for link in links if link.internal),
        "external_links": sum(1 for link in links if not link.internal),
        "forms": len(forms),
        "buttons": len(buttons),
        "images": len(find_all(root, lambda node: node.tag == "img")),
    }
    summary = summarize_page(title, page_role, features, stats)
    return PageAnalysis(
        source=document.source,
        source_type=document.source_type,
        encoding=document.encoding,
        title=title,
        meta_description=meta_description,
        headings=headings,
        sections=sections,
        links=links,
        forms=forms,
        features=features,
        components=components,
        flows=flows,
        stats=stats,
        summary=summary,
        page_role=page_role,
    )


def parse_html(html: str) -> Node:
    parser = HTMLTreeBuilder()
    parser.feed(html)
    parser.close()
    return parser.root


def iter_nodes(node: Node):
    yield node
    for child in node.children:
        yield from iter_nodes(child)


def find_first(node: Node, predicate):
    for item in iter_nodes(node):
        if predicate(item):
            return item
    return None


def find_all(node: Node, predicate):
    return [item for item in iter_nodes(node) if predicate(item)]


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def get_text(node: Node) -> str:
    pieces = list(node.text_chunks)
    for child in node.children:
        pieces.append(get_text(child))
    return normalize_whitespace(" ".join(piece for piece in pieces if piece))


def truncate(value: str, length: int = 120) -> str:
    normalized = normalize_whitespace(value)
    if len(normalized) <= length:
        return normalized
    return normalized[: length - 3].rstrip() + "..."


def attrs_blob(node: Node) -> str:
    fields = []
    for key in ("class", "id", "role", "aria-label", "name", "type", "placeholder", "href", "action"):
        value = node.attrs.get(key)
        if value:
            fields.append(value)
    return normalize_whitespace(" ".join(fields)).lower()


def humanize_identifier(value: str) -> str:
    normalized = re.sub(r"[_\-]+", " ", value or "")
    normalized = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", normalized)
    return normalize_whitespace(normalized)


def extract_title(root: Node) -> str:
    title = find_first(root, lambda node: node.tag == "title")
    return get_text(title) if title else ""


def extract_meta_description(root: Node) -> str:
    meta = find_first(
        root,
        lambda node: node.tag == "meta"
        and (
            node.attrs.get("name", "").lower() == "description"
            or node.attrs.get("property", "").lower() == "og:description"
        ),
    )
    return normalize_whitespace(meta.attrs.get("content", "")) if meta else ""


def extract_headings(root: Node) -> list[HeadingSummary]:
    headings = []
    for node in find_all(root, lambda item: item.tag in {"h1", "h2", "h3", "h4", "h5", "h6"}):
        text = truncate(get_text(node), 100)
        if text:
            headings.append(HeadingSummary(level=int(node.tag[1]), text=text))
    return headings[:20]


def extract_links(root: Node, base_url: str | None) -> list[LinkSummary]:
    links: list[LinkSummary] = []
    for node in find_all(root, lambda item: item.tag == "a" and item.attrs.get("href")):
        href = node.attrs.get("href", "").strip()
        if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
            continue
        target = urljoin(base_url, href) if base_url else href
        text = truncate(get_text(node) or guess_label_from_href(href), 80)
        links.append(LinkSummary(text=text, target=target, internal=is_internal_target(target, base_url)))
    return dedupe_links(links)


def extract_buttons(root: Node) -> list[str]:
    labels: list[str] = []
    for node in find_all(root, lambda item: item.tag == "button"):
        label = truncate(get_text(node), 60)
        if label:
            labels.append(label)
    for node in find_all(root, lambda item: item.tag == "input" and item.attrs.get("type", "").lower() in {"submit", "button"}):
        labels.append(normalize_whitespace(node.attrs.get("value", "")) or "Submit")
    return dedupe_strings(labels)


def extract_forms(root: Node, base_url: str | None) -> list[FormSummary]:
    forms: list[FormSummary] = []
    for form in find_all(root, lambda item: item.tag == "form"):
        action = form.attrs.get("action", "").strip()
        method = form.attrs.get("method", "GET").upper()
        fields: list[str] = []
        submit_labels: list[str] = []
        for node in find_all(form, lambda item: item.tag in {"input", "select", "textarea", "button"}):
            tag_type = node.attrs.get("type", "").lower()
            label = normalize_whitespace(
                node.attrs.get("name")
                or node.attrs.get("id")
                or node.attrs.get("placeholder")
                or node.attrs.get("aria-label")
                or node.attrs.get("value")
                or node.tag
            )
            if node.tag == "button" or tag_type in {"submit", "button"}:
                submit_labels.append(truncate(get_text(node) or label or "Submit", 60))
                continue
            descriptor = label
            if tag_type and tag_type not in {"text"}:
                descriptor = normalize_whitespace(f"{descriptor} ({tag_type})")
            if descriptor:
                fields.append(descriptor)
        forms.append(
            FormSummary(
                action=urljoin(base_url, action) if action and base_url else action,
                method=method,
                fields=dedupe_strings(fields),
                submit_labels=dedupe_strings(submit_labels),
            )
        )
    return forms


def extract_sections(root: Node) -> list[SectionSummary]:
    body = find_first(root, lambda node: node.tag == "body") or root
    main = find_first(root, lambda node: node.tag == "main")
    section_candidates = collect_top_level_sections(main or body)
    if not section_candidates:
        section_candidates = find_all(
            root,
            lambda node: node.tag in {"header", "nav", "section", "article", "aside", "footer", "form"},
        )
    summaries: list[SectionSummary] = []
    seen: set[tuple[str, str]] = set()
    for node in section_candidates:
        label = section_label(node)
        kind = section_kind(node)
        headline = first_heading(node) or truncate(get_text(node), 120)
        if not label and not headline:
            continue
        key = (kind, label or headline)
        if key in seen:
            continue
        seen.add(key)
        summaries.append(
            SectionSummary(
                kind=kind,
                label=label or kind.title(),
                headline=truncate(headline, 100),
                link_count=len(find_all(node, lambda item: item.tag == "a" and item.attrs.get("href"))),
                button_count=len(
                    find_all(
                        node,
                        lambda item: item.tag in {"button", "input"}
                        and (item.tag == "button" or item.attrs.get("type", "").lower() in {"submit", "button"}),
                    )
                ),
            )
        )
    return summaries[:12]


def collect_top_level_sections(root: Node) -> list[Node]:
    candidates: list[Node] = []
    for child in root.children:
        if child.tag in {"header", "nav", "main", "section", "article", "aside", "footer", "form"}:
            candidates.append(child)
            continue
        if looks_like_section(child):
            candidates.append(child)
    return candidates


def looks_like_section(node: Node) -> bool:
    blob = attrs_blob(node)
    if any(keyword in blob for keywords in SECTION_KEYWORDS.values() for keyword in keywords):
        return True
    return bool(first_heading(node))


def section_kind(node: Node) -> str:
    blob = attrs_blob(node)
    if node.tag in {"header", "nav", "main", "aside", "footer", "form"}:
        return node.tag
    for kind, keywords in SECTION_KEYWORDS.items():
        if any(keyword in blob for keyword in keywords):
            return kind
    return node.tag


def section_label(node: Node) -> str:
    heading = first_heading(node)
    if heading:
        return heading
    for attr in ("aria-label", "id", "class"):
        value = node.attrs.get(attr, "")
        if value:
            label = humanize_identifier(value)
            if label:
                return truncate(label, 80)
    return ""


def first_heading(node: Node) -> str:
    heading = find_first(node, lambda item: item.tag in {"h1", "h2", "h3", "h4", "h5", "h6"})
    return truncate(get_text(heading), 80) if heading else ""


def infer_page_role(source: str, title: str, headings: list[HeadingSummary], links: list[LinkSummary]) -> str:
    primary_text = normalize_whitespace(" ".join([source, title] + [heading.text for heading in headings])).lower()
    secondary_text = normalize_whitespace(" ".join([link.text for link in links])).lower()
    role_rules = [
        ("home", ["landing", "homepage", "welcome"]),
        ("pricing", ["pricing", "plans", "billing", "subscription"]),
        ("contact", ["contact", "talk to sales", "book demo", "demo request", "support"]),
        ("authentication", ["sign in", "sign up", "login", "register", "create account"]),
        ("dashboard", ["dashboard", "workspace", "profile", "settings", "account"]),
        ("catalog", ["products", "services", "solutions", "features", "catalog", "search"]),
        ("blog", ["blog", "article", "news", "resource", "documentation", "docs"]),
        ("checkout", ["checkout", "cart", "payment"]),
    ]
    for role, keywords in role_rules:
        if any(keyword in primary_text for keyword in keywords):
            return role
    for role, keywords in role_rules:
        if any(keyword in secondary_text for keyword in keywords):
            return role
    return "general"


def detect_features(
    title: str,
    meta_description: str,
    headings: list[HeadingSummary],
    links: list[LinkSummary],
    forms: list[FormSummary],
    buttons: list[str],
    sections: list[SectionSummary],
    page_role: str,
) -> list[Finding]:
    link_text = " ".join([link.text for link in links]).lower()
    targets = " ".join([link.target for link in links]).lower()
    button_text = " ".join(buttons).lower()
    form_text = " ".join(" ".join(form.fields + form.submit_labels) for form in forms).lower()
    section_text = " ".join([section.label + " " + section.headline for section in sections]).lower()
    heading_text = " ".join([heading.text for heading in headings]).lower()
    title_text = normalize_whitespace(f"{title} {meta_description}").lower()
    core_haystack = " ".join([title_text, heading_text, button_text, form_text, section_text, page_role])
    action_haystack = " ".join([button_text, link_text, targets, form_text, section_text])
    full_haystack = " ".join([core_haystack, action_haystack])

    findings: list[Finding] = []
    if any("password" in field.lower() for form in forms for field in form.fields) or any(
        keyword in action_haystack for keyword in ["sign in", "sign up", "login", "register", "create account"]
    ):
        findings.append(build_finding("Authentication / account entry", full_haystack, ["sign in", "sign up", "login", "password field", "create account"], forms))
    if any("search" in field.lower() for form in forms for field in form.fields) or any(
        keyword in full_haystack for keyword in ["search", "filter", "sort", "browse"]
    ):
        findings.append(build_finding("Search and filtering", full_haystack, ["search", "filter", "sort", "browse"], forms))
    if any(keyword in core_haystack for keyword in ["pricing", "plans", "subscription", "billing", "free trial"]):
        findings.append(build_finding("Pricing / subscription", full_haystack, ["pricing", "plans", "subscription", "free trial"], forms))
    if any(keyword in action_haystack for keyword in ["contact", "demo", "talk to sales", "get in touch", "message us", "request demo"]) or any(
        any(field.lower().startswith(("email", "message", "company")) for field in form.fields) for form in forms
    ):
        findings.append(build_finding("Contact or lead capture", full_haystack, ["contact", "demo", "email", "message", "request demo"], forms))
    if any(keyword in core_haystack for keyword in ["checkout", "cart", "payment", "buy now"]):
        findings.append(build_finding("Checkout / payment", full_haystack, ["checkout", "cart", "payment", "buy now"], forms))
    if any(keyword in core_haystack for keyword in ["blog", "article", "news", "resource", "docs", "documentation"]):
        findings.append(build_finding("Content or resource hub", full_haystack, ["blog", "article", "resource", "docs"], forms))
    if any(keyword in core_haystack for keyword in ["testimonial", "review", "customers", "faq", "questions", "trusted by"]):
        findings.append(build_finding("FAQ / social proof", full_haystack, ["testimonial", "review", "faq", "trusted by"], forms))
    if any(keyword in action_haystack for keyword in ["book", "schedule", "appointment", "calendar"]) and "book now" not in action_haystack:
        findings.append(build_finding("Booking / scheduling", full_haystack, ["book", "schedule", "appointment", "calendar"], forms))
    if any(keyword in core_haystack for keyword in ["dashboard", "workspace", "profile", "settings", "account"]) and page_role == "dashboard":
        findings.append(build_finding("Dashboard / account management", full_haystack, ["dashboard", "profile", "settings", "account"], forms))
    if any(keyword in core_haystack for keyword in ["gallery", "video", "carousel", "slider", "showcase"]):
        findings.append(build_finding("Media / gallery", full_haystack, ["gallery", "video", "carousel", "showcase"], forms))
    return dedupe_findings(findings)


def build_finding(name: str, haystack: str, keywords: list[str], forms: list[FormSummary]) -> Finding:
    evidence: list[str] = []
    for keyword in keywords:
        if keyword == "password field":
            if any("password" in field.lower() for form in forms for field in form.fields):
                evidence.append("password field")
            continue
        if keyword in haystack:
            evidence.append(keyword)
    return Finding(name=name, evidence=dedupe_strings(evidence)[:3])


def detect_components(root: Node, sections: list[SectionSummary], buttons: list[str], forms: list[FormSummary], links: list[LinkSummary]) -> list[Finding]:
    findings: list[Finding] = []
    if find_first(root, lambda node: node.tag == "header"):
        findings.append(Finding(name="Header", evidence=["semantic <header>"]))
    if find_first(root, lambda node: node.tag == "nav"):
        findings.append(Finding(name="Primary navigation", evidence=[f"{min(len(links), 8)} detected links"]))
    if any(
        section.kind == "hero" or (section.kind in {"header", "section"} and "hero" in (section.label + section.headline).lower())
        for section in sections
    ):
        findings.append(Finding(name="Hero section", evidence=["top-of-page headline block"]))
    elif sections and sections[0].headline and sections[0].button_count:
        findings.append(Finding(name="Hero section", evidence=[sections[0].headline]))
    card_count = repeated_content_block_count(root)
    if card_count >= 3:
        findings.append(Finding(name="Card grid or repeated content blocks", evidence=[f"{card_count} similar sibling blocks"]))
    if buttons:
        findings.append(Finding(name="Call-to-action buttons", evidence=buttons[:3]))
    if forms:
        findings.append(Finding(name="Form", evidence=[f"{len(forms)} form block(s)"]))
    if find_first(root, lambda node: node.tag == "footer"):
        findings.append(Finding(name="Footer", evidence=["semantic <footer>"]))
    if find_first(root, lambda node: node.tag in {"details", "summary"} or "accordion" in attrs_blob(node)):
        findings.append(Finding(name="Accordion / expandable FAQ", evidence=["details/accordion marker"]))
    if find_first(root, lambda node: node.tag == "table"):
        findings.append(Finding(name="Table", evidence=["semantic <table>"]))
    if find_first(root, lambda node: any(keyword in attrs_blob(node) for keyword in ["carousel", "slider", "gallery"])):
        findings.append(Finding(name="Carousel or gallery", evidence=["gallery/slider marker"]))
    return dedupe_findings(findings)


def repeated_content_block_count(root: Node) -> int:
    best = 0
    for node in find_all(root, lambda item: len(item.children) >= 3):
        meaningful_children = [child for child in node.children if get_text(child)]
        if len(meaningful_children) < 3:
            continue
        child_tags = Counter(child.tag for child in meaningful_children)
        common_tag, count = child_tags.most_common(1)[0]
        if common_tag not in {"div", "article", "li", "section"}:
            continue
        if any(
            any(keyword in attrs_blob(child) for keyword in ["card", "item", "plan", "feature", "testimonial"])
            for child in meaningful_children
        ):
            best = max(best, count)
    return best


def detect_page_flows(page_role: str, features: list[Finding], forms: list[FormSummary], links: list[LinkSummary]) -> list[Finding]:
    feature_names = {feature.name for feature in features}
    link_text = " ".join(link.text for link in links).lower()
    flows: list[Finding] = []
    if "Pricing / subscription" in feature_names and (
        "Authentication / account entry" in feature_names
        or any(keyword in link_text for keyword in ["sign up", "start free", "get started"])
    ):
        flows.append(Finding(name="Pricing review -> sign-up", evidence=["pricing CTA", "account entry signal"]))
    if "Contact or lead capture" in feature_names and forms:
        flows.append(Finding(name="Visit page -> submit lead/contact form", evidence=[forms[0].submit_labels[0] if forms[0].submit_labels else "contact form"]))
    if "Search and filtering" in feature_names and any(keyword in link_text for keyword in ["view", "details", "learn more", "product"]):
        flows.append(Finding(name="Browse/search -> inspect detail page", evidence=["search/browse controls"]))
    if "Checkout / payment" in feature_names:
        flows.append(Finding(name="Select offer -> checkout", evidence=["checkout/payment marker"]))
    if page_role == "home" and any(keyword in link_text for keyword in ["pricing", "contact", "demo"]):
        flows.append(Finding(name="Landing page -> primary conversion page", evidence=["navigation or CTA links"]))
    return dedupe_findings(flows)


def summarize_page(title: str, page_role: str, features: list[Finding], stats: dict[str, int]) -> str:
    feature_names = ", ".join(feature.name for feature in features[:3]) or "general marketing/information"
    label = title or "Untitled page"
    return (
        f"{label} behaves like a {page_role} page, with {stats.get('sections', 0)} main sections, "
        f"{stats.get('forms', 0)} form(s), and primary signals for {feature_names}."
    )


def aggregate_site(source: str, pages: list[PageAnalysis], load_issues: list[LoadIssue]) -> SiteAnalysis:
    component_counter = Counter(component.name for page in pages for component in page.components)
    feature_counter = Counter(feature.name for page in pages for feature in page.features)
    navigation = dedupe_strings([link.text for page in pages[:1] for link in page.links if link.internal and link.text])[:8]

    if len(pages) == 1:
        common_components = [Finding(name=component.name, evidence=component.evidence) for component in pages[0].components]
    else:
        common_components = [
            Finding(name=name, evidence=[f"seen on {count}/{len(pages)} pages"])
            for name, count in component_counter.items()
            if count >= 2
        ]

    feature_summary = [
        Finding(name=name, evidence=[f"detected on {count}/{len(pages)} pages"])
        for name, count in feature_counter.most_common()
    ]

    generated_at = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %z")
    return SiteAnalysis(
        source=source,
        pages=pages,
        common_components=common_components,
        feature_summary=feature_summary,
        flows=infer_site_flows(pages),
        navigation=navigation,
        load_issues=load_issues,
        generated_at=generated_at,
    )


def infer_site_flows(pages: list[PageAnalysis]) -> list[Finding]:
    flows: list[Finding] = []
    roles = {page.page_role: page for page in pages}
    if "home" in roles and "pricing" in roles and any(role in roles for role in {"authentication", "contact"}):
        destination = "sign-up" if "authentication" in roles else "demo/contact"
        flows.append(Finding(name=f"Landing -> pricing -> {destination}", evidence=["cross-page role coverage"]))
    if "home" in roles and "contact" in roles:
        flows.append(Finding(name="Landing -> contact form", evidence=["home + contact pages"]))
    if "catalog" in roles and "checkout" in roles:
        flows.append(Finding(name="Browse catalog -> checkout", evidence=["catalog + checkout pages"]))

    seen = {flow.name for flow in flows}
    for page in pages:
        for flow in page.flows:
            if flow.name in seen:
                continue
            seen.add(flow.name)
            flows.append(flow)
    return flows[:6]


def dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = normalize_whitespace(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def dedupe_links(links: list[LinkSummary]) -> list[LinkSummary]:
    seen: set[tuple[str, str]] = set()
    result: list[LinkSummary] = []
    for link in links:
        key = (link.text, link.target)
        if key in seen:
            continue
        seen.add(key)
        result.append(link)
    return result


def dedupe_findings(values: list[Finding]) -> list[Finding]:
    seen: set[str] = set()
    result: list[Finding] = []
    for value in values:
        if value.name in seen:
            continue
        seen.add(value.name)
        value.evidence = dedupe_strings(value.evidence)
        result.append(value)
    return result


def canonicalize_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed._replace(fragment="", path=parsed.path or "/").geturl()


def is_internal_target(target: str, base_url: str | None) -> bool:
    if not base_url:
        return not bool(urlparse(target).netloc)
    target_parsed = urlparse(target)
    base_parsed = urlparse(base_url)
    if not target_parsed.netloc:
        return True
    return target_parsed.netloc == base_parsed.netloc


def guess_label_from_href(href: str) -> str:
    parsed = urlparse(href)
    candidate = Path(parsed.path).stem or parsed.netloc
    return humanize_identifier(candidate) or href


def decode_html_bytes(data: bytes, declared_encoding: str | None = None) -> DecodedContent:
    candidate_encodings = build_encoding_candidates(data, declared_encoding)
    last_error: UnicodeDecodeError | None = None
    for encoding in candidate_encodings:
        try:
            return DecodedContent(source="", text=data.decode(encoding), encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
    fallback_text = data.decode(candidate_encodings[0] if candidate_encodings else "utf-8", errors="replace")
    fallback_encoding = candidate_encodings[0] if candidate_encodings else "utf-8"
    if last_error is None and not fallback_text:
        fallback_encoding = "utf-8"
    return DecodedContent(source="", text=fallback_text, encoding=fallback_encoding, used_replacement=True)


def build_encoding_candidates(data: bytes, declared_encoding: str | None = None) -> list[str]:
    candidates: list[str] = []
    for encoding in (
        normalize_encoding_name(declared_encoding),
        detect_bom_encoding(data),
        sniff_meta_charset(data),
        *FALLBACK_ENCODINGS,
    ):
        if not encoding or encoding in candidates:
            continue
        candidates.append(encoding)
    return candidates or ["utf-8"]


def normalize_encoding_name(encoding: str | None) -> str | None:
    if not encoding:
        return None
    cleaned = encoding.strip().strip("\"'").lower()
    try:
        return lookup(cleaned).name
    except LookupError:
        return None


def detect_bom_encoding(data: bytes) -> str | None:
    for marker, encoding in BOM_ENCODINGS:
        if data.startswith(marker):
            return encoding
    return None


def sniff_meta_charset(data: bytes) -> str | None:
    head = data[:4096]
    for pattern in (META_CHARSET_RE, META_CONTENT_RE):
        match = pattern.search(head)
        if not match:
            continue
        return normalize_encoding_name(match.group(1).decode("ascii", errors="ignore"))
    return None


def describe_load_error(exc: Exception) -> str:
    if isinstance(exc, HTTPError):
        return f"HTTP {exc.code}: {exc.reason}"
    if isinstance(exc, URLError):
        reason = getattr(exc, "reason", exc)
        return f"URL error: {reason}"
    if isinstance(exc, TimeoutError):
        return "Timed out while loading page"
    return str(exc)
