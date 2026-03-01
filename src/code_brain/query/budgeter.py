"""Context token budgeter with compact/medium/full depth profiles.

Manages token budget allocation across context sections (signatures,
docstrings, source, context) to help LLM agents fit relevant code
information within token limits.
"""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass, field

import tiktoken


class Depth(str, Enum):
    """Level of detail for code context."""

    COMPACT = "compact"
    MEDIUM = "medium"
    FULL = "full"


# Token allocation ratios per depth level.
# Each depth distributes the total budget across four sections.
DEPTH_RATIOS: dict[Depth, dict[str, float]] = {
    Depth.COMPACT: {
        "signatures": 0.60,
        "docstrings": 0.00,
        "source": 0.00,
        "context": 0.40,
    },
    Depth.MEDIUM: {
        "signatures": 0.30,
        "docstrings": 0.20,
        "source": 0.20,
        "context": 0.30,
    },
    Depth.FULL: {
        "signatures": 0.10,
        "docstrings": 0.10,
        "source": 0.60,
        "context": 0.20,
    },
}


@dataclass
class _SectionBudget:
    """Tracks token usage for a single section."""

    allocated: int
    used: int = 0

    @property
    def remaining(self) -> int:
        return max(0, self.allocated - self.used)


class ContextBudgeter:
    """Allocates and tracks a token budget across context sections.

    Parameters
    ----------
    max_tokens:
        Total token budget.
    depth:
        Detail level controlling how tokens are distributed.
    """

    def __init__(
        self, max_tokens: int = 4096, depth: Depth = Depth.MEDIUM
    ) -> None:
        self.max_tokens = max_tokens
        self.depth = depth
        self._encoder = tiktoken.get_encoding("cl100k_base")
        self._sections = self._build_sections()

    def _build_sections(self) -> dict[str, _SectionBudget]:
        ratios = DEPTH_RATIOS[self.depth]
        return {
            name: _SectionBudget(allocated=int(self.max_tokens * ratio))
            for name, ratio in ratios.items()
        }

    # ------------------------------------------------------------------
    # Token counting
    # ------------------------------------------------------------------

    def count_tokens(self, text: str) -> int:
        """Return the number of tokens in *text*."""
        if not text:
            return 0
        return len(self._encoder.encode(text))

    # ------------------------------------------------------------------
    # Allocation queries
    # ------------------------------------------------------------------

    def get_allocation(self, section: str) -> int:
        """Return the initial token allocation for *section*."""
        sec = self._sections.get(section)
        return sec.allocated if sec else 0

    def remaining(self, section: str) -> int:
        """Return remaining tokens in *section*."""
        sec = self._sections.get(section)
        return sec.remaining if sec else 0

    def total_remaining(self) -> int:
        """Return total remaining tokens across all sections."""
        return sum(s.remaining for s in self._sections.values())

    def total_used(self) -> int:
        """Return total tokens consumed across all sections."""
        return sum(s.used for s in self._sections.values())

    # ------------------------------------------------------------------
    # Budget consumption
    # ------------------------------------------------------------------

    def fits(self, text: str, section: str) -> bool:
        """Check whether *text* fits in the remaining budget of *section*."""
        sec = self._sections.get(section)
        if sec is None:
            return False
        return self.count_tokens(text) <= sec.remaining

    def consume(self, text: str, section: str) -> bool:
        """Consume tokens for *text* from *section*.

        Returns ``True`` if the text fit and was consumed, ``False`` otherwise.
        """
        sec = self._sections.get(section)
        if sec is None:
            return False
        tokens = self.count_tokens(text)
        if tokens > sec.remaining:
            return False
        sec.used += tokens
        return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def truncate_to_fit(self, text: str, section: str) -> str:
        """Return *text* truncated to fit within *section*'s remaining budget.

        Returns an empty string if *section* is unknown.
        """
        sec = self._sections.get(section)
        if sec is None:
            return ""
        tokens = self._encoder.encode(text)
        if len(tokens) <= sec.remaining:
            return text
        truncated = tokens[: sec.remaining]
        return self._encoder.decode(truncated)
