"""Small source-collector contracts shared by application services."""

from dataclasses import dataclass
from typing import Literal, Protocol

from job_market_analyzer.models import RawJob

FailureStage = Literal["collect", "normalize", "persist"]


@dataclass(frozen=True)
class CollectionFailure:
    """One source item that could not complete a pipeline stage."""

    source_provider: str
    stage: FailureStage
    message: str
    item_index: int | None = None
    external_id: str | None = None


@dataclass(frozen=True)
class CollectedJobs:
    """Raw jobs and explicit item failures produced by one collection run."""

    fetched: int
    jobs: tuple[RawJob, ...]
    failures: tuple[CollectionFailure, ...] = ()
    metadata: dict[str, object] | None = None


class JobCollector(Protocol):
    """Asynchronous source collector contract used by collection services."""

    async def collect(self) -> CollectedJobs:
        """Fetch one source run without persisting its results."""
        ...
