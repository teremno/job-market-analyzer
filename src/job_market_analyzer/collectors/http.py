"""Small HTTP client safeguards shared by external-source collectors."""

import logging
import re

_QUERY_TOKEN_PATTERN = re.compile(
    r"(?P<prefix>[?&]token=)[^&\s\"']*",
    flags=re.IGNORECASE,
)


class _HTTPXQueryTokenRedactionFilter(logging.Filter):
    """Redact query-string API tokens while preserving the HTTPX log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        redacted_message = _QUERY_TOKEN_PATTERN.sub(
            r"\g<prefix>[REDACTED]",
            message,
        )
        if redacted_message != message:
            record.msg = redacted_message
            record.args = ()
        return True


_HTTPX_QUERY_TOKEN_REDACTION_FILTER = _HTTPXQueryTokenRedactionFilter()


def install_httpx_query_token_redaction() -> None:
    """Ensure HTTPX INFO logs cannot expose a query parameter named ``token``."""

    logger = logging.getLogger("httpx")
    if _HTTPX_QUERY_TOKEN_REDACTION_FILTER not in logger.filters:
        logger.addFilter(_HTTPX_QUERY_TOKEN_REDACTION_FILTER)
