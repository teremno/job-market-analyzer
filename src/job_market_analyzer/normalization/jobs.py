"""Shared contracts for source-specific job normalization."""

from html.parser import HTMLParser
from typing import ClassVar


class NormalizationError(ValueError):
    """Malformed data for one source item that a batch may safely skip."""


class _DescriptionHTMLParser(HTMLParser):
    _break_tags: ClassVar[set[str]] = {
        "br",
        "div",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "p",
        "tr",
    }
    _ignored_tags: ClassVar[set[str]] = {"script", "style"}
    _trailing_punctuation = frozenset(".,;:!?)]}")

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str | None] = []
        self._ignored_depth = 0
        self._pending_inline_boundary = False

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        del attrs

        if self._ignored_depth:
            if tag in self._ignored_tags:
                self._ignored_depth += 1
            return

        if tag in self._ignored_tags:
            self._ignored_depth = 1
            return

        if tag in self._break_tags:
            self._append_break()

    def handle_endtag(self, tag: str) -> None:
        if self._ignored_depth:
            if tag in self._ignored_tags:
                self._ignored_depth -= 1
            return

        if tag in self._break_tags:
            self._append_break()
        else:
            self._pending_inline_boundary = True

    def handle_data(self, data: str) -> None:
        if self._ignored_depth or not data:
            return

        if (
            self._pending_inline_boundary
            and self._parts
            and self._parts[-1] is not None
            and not self._parts[-1][-1].isspace()
            and not data[0].isspace()
            and data[0] not in self._trailing_punctuation
        ):
            self._parts.append(" ")

        self._parts.append(data)
        self._pending_inline_boundary = False

    def _append_break(self) -> None:
        if self._parts and self._parts[-1] is not None:
            self._parts.append(None)
        self._pending_inline_boundary = False

    def text(self) -> str | None:
        lines: list[str] = []
        block_parts: list[str] = []

        for part in (*self._parts, None):
            if part is not None:
                block_parts.append(part)
                continue

            normalized_line = " ".join("".join(block_parts).split())
            if normalized_line:
                lines.append(normalized_line)
            block_parts.clear()

        return "\n".join(lines) or None


def html_to_text(value: str | None) -> str | None:
    """Convert source HTML to deterministic analytics-friendly plain text."""

    if value is None:
        return None

    parser = _DescriptionHTMLParser()
    parser.feed(value)
    parser.close()
    return parser.text()
