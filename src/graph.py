"""Parse assignment HTML pages into a directed simple graph."""

from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, Tuple


class LinkParser(HTMLParser):
    """Collect anchor href attributes, including uppercase HTML attributes."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for name, value in attrs:
                if name == 'href' and value is not None:
                    self.links.append(value)
                    break

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)


@dataclass
class Graph:
    names: list
    name_to_id: dict
    outgoing: list
    incoming: list
    raw_links: int = 0
    duplicate_links: int = 0
    invalid_links: int = 0
    self_links: int = 0

    @property
    def edge_count(self):
        return sum(len(neighbors) for neighbors in self.outgoing)


def build_graph(page_names: Iterable[str], pages: Iterable[Tuple[str, str]]) -> Graph:
    """Build from known names and streamed (name, HTML) pairs.

    Hrefs must exactly match a dataset filename. Duplicate valid targets within
    one page are collapsed. Self-links remain; missing/external targets do not.
    Every registered page must be supplied exactly once.
    """
    names = sorted(page_names)
    if not names:
        raise ValueError('No HTML pages found')
    if len(set(names)) != len(names):
        raise ValueError('Duplicate page names')
    mapping = {name: idx for idx, name in enumerate(names)}
    graph = Graph(names, mapping, [[] for _ in names], [[] for _ in names])
    seen_pages = set()
    for name, html in pages:
        if name not in mapping or name in seen_pages:
            raise ValueError(f'Unexpected or repeated page: {name}')
        seen_pages.add(name)
        source = mapping[name]
        parser = LinkParser()
        parser.feed(html)
        parser.close()
        targets = set()
        for href in parser.links:
            graph.raw_links += 1
            if href not in mapping:
                graph.invalid_links += 1
                continue
            target = mapping[href]
            if target in targets:
                graph.duplicate_links += 1
                continue
            targets.add(target)
            if source == target:
                graph.self_links += 1
        graph.outgoing[source] = sorted(targets)
        for target in graph.outgoing[source]:
            graph.incoming[target].append(source)
    if len(seen_pages) != len(names):
        raise ValueError('Missing content for registered pages')
    for neighbors in graph.incoming:
        neighbors.sort()
    return graph


def load_local_graph(input_dir: Path) -> Graph:
    """Read immediate *.html files as UTF-8, retaining empty/isolated pages."""
    directory = Path(input_dir)
    if not directory.is_dir():
        raise ValueError(f'Input directory does not exist: {directory}')
    paths = sorted(path for path in directory.glob('*.html') if path.is_file())
    return build_graph(
        (path.name for path in paths),
        ((path.name, path.read_text(encoding='utf-8')) for path in paths),
    )
