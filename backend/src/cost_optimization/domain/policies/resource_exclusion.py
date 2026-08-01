"""Opt-out policy shared by all resource detection rules."""

from collections.abc import Mapping

EXCLUSION_TAG_KEY = "cost-optimizer:exclude"
EXCLUSION_TAG_VALUE = "true"


def is_excluded_from_optimization(tags: Mapping[str, str]) -> bool:
    """Return whether a resource owner explicitly opted out of automation."""
    return tags.get(EXCLUSION_TAG_KEY, "").casefold() == EXCLUSION_TAG_VALUE
