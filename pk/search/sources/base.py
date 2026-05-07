"""Adapter base class. Each source implements keyword search + fetch."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class SourceBase(ABC):
    name: str = "base"

    @abstractmethod
    def search(self, query: str, max_results: int = 20) -> list[dict[str, Any]]:
        """Return list of hits: {doc_id, title, abstract, ipc, applicant, pub_date, url}."""

    def fetch(self, doc_id: str) -> dict[str, Any]:
        """Optional: full-text fetch."""
        raise NotImplementedError
