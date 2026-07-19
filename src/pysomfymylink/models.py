"""Typed data models for pysomfymylink."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Shade:
    """A single Somfy cover/motor as reported by ``mylink.status.info``.

    ``cover_type`` is the hub's numeric device type (0 = blind, 1 = shutter on
    the devices seen in the wild); it may be ``None`` when the hub omits it.
    ``raw`` keeps the original payload for forward-compatibility.
    """

    target_id: str
    name: str
    cover_type: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Shade:
        """Build a :class:`Shade` from a single ``status.info`` result entry."""
        return cls(
            target_id=data["targetID"],
            name=data.get("name", ""),
            cover_type=data.get("type"),
            raw=data,
        )
