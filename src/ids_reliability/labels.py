from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
import pandas as pd


class LabelError(ValueError):
    pass


@dataclass(frozen=True)
class LabelMapping:
    label_to_id: dict[str, int]
    id_to_label: dict[int, str]
    unknown_label: str
    benign_label: str

    def encode(self, labels: Iterable[object]) -> list[int]:
        encoded: list[int] = []
        for value in labels:
            key = normalize_label(value)
            if key not in self.label_to_id:
                raise LabelError(f"Encountered label not included in fitted mapping: {value!r}")
            encoded.append(self.label_to_id[key])
        return encoded


def normalize_label(value: object) -> str:
    if pd.isna(value):
        raise LabelError("Missing class label encountered")
    return str(value).strip()


def build_label_mapping(
    labels: Iterable[object], unknown_label: str, benign_aliases: Iterable[str] = ("Benign", "Normal", "BENIGN", "0")
) -> LabelMapping:
    names = {normalize_label(v) for v in labels}
    if not names:
        raise LabelError("No labels found")
    unknown_matches = [x for x in names if x.casefold() == unknown_label.strip().casefold()]
    if len(unknown_matches) != 1:
        raise LabelError(
            f"Unknown family {unknown_label!r} must occur in the data exactly once; found {len(unknown_matches)} case-insensitive matches"
        )
    benign_set = {str(x).strip().casefold() for x in benign_aliases}
    benign_matches = [x for x in names if x.casefold() in benign_set]
    if len(benign_matches) != 1:
        raise LabelError(f"Expected exactly one benign label, found {benign_matches}")
    unknown = unknown_matches[0]
    benign = benign_matches[0]
    known_attacks = sorted((x for x in names if x not in {unknown, benign}), key=str.casefold)
    mapping = {benign: 0}
    mapping.update({label: i + 1 for i, label in enumerate(known_attacks)})
    mapping[unknown] = -1
    inverse = {value: key for key, value in mapping.items() if value >= 0}
    inverse[-1] = "Unknown_held_out"
    return LabelMapping(mapping, inverse, unknown, benign)
