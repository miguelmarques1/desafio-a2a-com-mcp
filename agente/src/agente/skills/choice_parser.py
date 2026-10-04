"""Strict parser for the `escolha=<valor>` reply that resumes a paused Task."""

from __future__ import annotations

import re
from dataclasses import dataclass

DECLINE_VALUE = "recusar"

_CHOICE = re.compile(r"escolha=(\S+)")


@dataclass(frozen=True)
class AcceptChoice:
    sala: str


@dataclass(frozen=True)
class DeclineChoice:
    pass


def parse_choice_value(text: str) -> str | None:
    match = _CHOICE.fullmatch(text.strip())
    return match.group(1) if match else None


def classify_choice(text: str, alternatives: tuple[str, ...]) -> AcceptChoice | DeclineChoice | None:
    value = parse_choice_value(text)
    if value is None:
        return None
    if value in alternatives:
        return AcceptChoice(value)
    if value == DECLINE_VALUE:
        return DeclineChoice()
    return None
