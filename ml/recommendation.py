"""
Rule-based recommendation engine for outfit selection.

This module keeps the logic simple and explainable, which is ideal for
academic review. In future, this can be replaced with a learned model
using usage_history and user feedback.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from database.db import ClothingRepository


TOP_TYPES = {"shirt", "jacket", "tshirt"}
BOTTOM_TYPES = {"pants", "skirt", "shorts"}


@dataclass
class Outfit:
    """
    Represents a simple (top, bottom) outfit.
    """

    top: Dict[str, Any]
    bottom: Dict[str, Any]


class RecommenderEngine:
    """
    Simple rule-based recommendation engine.

    Textual Flowchart:
    ------------------
    START
      -> load all clothes from repository
      -> score each item according to rules
      -> pick best top and best bottom
      -> if both exist: return outfit
         else: return None
      -> END
    """

    def __init__(self, repository: ClothingRepository) -> None:
        self._repo = repository

    # Helper scoring functions
    def _base_score_for_type(self, clothing_type: str, occasion: str) -> float:
        """
        Very simple mapping of clothing_type and occasion to base score.
        """
        score = 1.0
        if occasion == "formal":
            if clothing_type in {"shirt", "jacket", "pants"}:
                score += 1.0
        elif occasion == "party":
            if clothing_type in {"jacket", "skirt"}:
                score += 1.0
        elif occasion == "sports":
            if clothing_type in {"tshirt", "shorts"}:
                score += 1.0
        return score

    def _mood_modifier(self, mood: str) -> float:
        if mood == "happy":
            return 0.3
        if mood == "tired":
            return -0.1
        if mood == "energetic":
            return 0.5
        return 0.0

    def _weather_modifier(self, weather: str, clothing_type: str) -> float:
        if weather == "cold" and clothing_type == "jacket":
            return 1.0
        if weather == "hot" and clothing_type in {"jacket", "pants"}:
            return -0.5
        return 0.0

    def _recency_penalty(self, usage_count: int) -> float:
        """
        Simple fairness rule: items used less frequently get boosted.
        """
        if usage_count == 0:
            return 0.5
        if usage_count < 3:
            return 0.2
        if usage_count < 10:
            return 0.0
        return -0.3

    def _score_item(
        self,
        item: Dict[str, Any],
        mood: str,
        occasion: str,
        weather: str,
        time_of_day: str,  # noqa: ARG002 - reserved for future refinement
    ) -> float:
        """
        Combine simple heuristics into a final continuous score.
        """
        base = self._base_score_for_type(item["type"], occasion)
        score = base
        score += self._mood_modifier(mood)
        score += self._weather_modifier(weather, item["type"])
        score += self._recency_penalty(item.get("usage_count", 0))
        return score

    def recommend_outfit(
        self,
        mood: str,
        occasion: str,
        weather: str,
        time_of_day: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Public API used by the Flask app.

        Returns:
            dict with "top" and "bottom" items, or None if not possible.
        """
        items = self._repo.list_clothes()
        if not items:
            return None

        best_top: Tuple[float, Dict[str, Any]] | None = None
        best_bottom: Tuple[float, Dict[str, Any]] | None = None

        for item in items:
            s = self._score_item(item, mood, occasion, weather, time_of_day)
            if item["type"] in TOP_TYPES:
                if best_top is None or s > best_top[0]:
                    best_top = (s, item)
            if item["type"] in BOTTOM_TYPES:
                if best_bottom is None or s > best_bottom[0]:
                    best_bottom = (s, item)

        if not best_top or not best_bottom:
            return None

        return {"top": best_top[1], "bottom": best_bottom[1]}

