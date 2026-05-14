from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any


@dataclass
class TransformSpan:
    kind: str
    orig_start: int | None = None
    orig_end: int | None = None
    clone_start: int | None = None
    clone_end: int | None = None
    detail: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"kind": self.kind}
        if self.orig_start is not None:
            d["orig_start"] = self.orig_start
        if self.orig_end is not None:
            d["orig_end"] = self.orig_end
        if self.clone_start is not None:
            d["clone_start"] = self.clone_start
        if self.clone_end is not None:
            d["clone_end"] = self.clone_end
        if self.detail:
            d["detail"] = self.detail
        return d
