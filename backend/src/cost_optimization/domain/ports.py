"""Ports implemented by infrastructure adapters."""

from __future__ import annotations

from typing import Protocol

from cost_optimization.domain.models import EbsVolume


class EbsVolumeDiscovery(Protocol):
    """Retrieves EBS volumes that could be evaluated by detection rules."""

    def list_unattached_volumes(self) -> list[EbsVolume]:
        """Return only currently unattached EBS volumes."""
