"""Heuristic virality scoring for generated content."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from twitter_agent.models.schemas import ContentType

ENGAGEMENT_BAIT_PATTERNS = [
    r"\brt if\b",
    r"\blike if\b",
    r"\bretweet if\b",
    r"\bshare if\b",
    r"\bfollow me\b",
    r"\bfree giveaway\b",
    r"\bairdrop\b",
    r"\bdm me\b",
    r"\bsubscribe\b",
]

SHARE_KEYWORDS = [
    "framework",
    "checklist",
    "playbook",
    "lessons",
    "mistake",
    "mistakes",
    "rules",
    "steps",
    "ways",
    "principles",
    "guide",
    "template",
    "how to",
    "counterintuitive",
    "unpopular",
    "truth",
]

REPLY_KEYWORDS = [
    "thoughts",
    "agree",
    "disagree",
    "anyone else",
    "curious",
    "hot take",
    "what do you think",
]

CLICK_KEYWORDS = [
    "link",
    "full",
    "read",
    "guide",
    "template",
    "resource",
    "download",
    "demo",
]

HOOK_KEYWORDS = [
    "here's",
    "nobody",
    "stop",
    "hot take",
    "wild",
    "truth",
    "mistake",
    "counterintuitive",
    "unpopular",
    "the real",
    "what nobody",
    "this is why",
    "changed how i",
]


@dataclass
class ViralityResult:
    """Result of virality scoring."""

    score: float
    components: dict[str, float]
    notes: list[str]


class ViralityScorer:
    """Score content for likely reach and engagement using heuristics."""

    def score(self, content: str | list[str], content_type: ContentType) -> ViralityResult:
        if isinstance(content, list):
            texts = content
        else:
            texts = [content]

        per_text_results = [self._score_text(text, content_type) for text in texts]
        if not per_text_results:
            return ViralityResult(score=0.0, components={}, notes=["No content to score"])

        components: dict[str, float] = {}
        for result in per_text_results:
            for key, value in result.components.items():
                components[key] = components.get(key, 0.0) + value

        for key in components:
            components[key] /= len(per_text_results)

        notes = []
        for result in per_text_results:
            notes.extend(result.notes)
        notes = list(dict.fromkeys(notes))[:6]

        score = self._aggregate_score(components)

        # Thread-specific hook bonus if the first tweet is strong
        if content_type == ContentType.THREAD and texts:
            hook_score = self._hook_score(texts[0])
            score = min(100.0, score + hook_score * 6)
            if hook_score > 0.6 and "Strong hook" not in notes:
                notes.insert(0, "Strong hook")

        return ViralityResult(score=round(score, 1), components=components, notes=notes)

    def _score_text(self, text: str, content_type: ContentType) -> ViralityResult:
        cleaned = text.strip()
        if not cleaned:
            return ViralityResult(score=0.0, components={}, notes=["Empty content"])

        length = len(cleaned)
        letters = re.findall(r"[A-Za-z]", cleaned)
        upper = sum(1 for c in cleaned if c.isupper())
        uppercase_ratio = (upper / len(letters)) if letters else 0.0

        question_marks = cleaned.count("?")
        exclamations = cleaned.count("!")
        hashtags = len(re.findall(r"#\w+", cleaned))
        mentions = len(re.findall(r"@\w+", cleaned))
        has_link = bool(re.search(r"https?://|www\.", cleaned))

        sentences = [s.strip() for s in re.split(r"[.!?]+", cleaned) if s.strip()]
        sentence_lengths = [len(re.findall(r"\b\w+\b", s)) for s in sentences]
        avg_sentence_len = sum(sentence_lengths) / len(sentence_lengths) if sentence_lengths else 0

        line_breaks = cleaned.count("\n")
        has_list = any(line.strip().startswith(("-", "*", "1.", "1)", "•")) for line in cleaned.splitlines())
        number_count = len(re.findall(r"\b\d+\b", cleaned))

        length_score = self._length_score(length, content_type)
        structure_score = min(1.0, (0.4 if line_breaks >= 1 else 0.0) + (0.4 if has_list else 0.0) + (0.2 if number_count >= 1 else 0.0))
        hook_score = self._hook_score(cleaned)

        reply_potential = min(1.0, (0.6 if question_marks > 0 else 0.0) + (0.4 if self._has_keywords(cleaned, REPLY_KEYWORDS) else 0.0))
        share_potential = min(1.0, (0.3 if has_list or number_count >= 1 else 0.0) + (0.4 if self._has_keywords(cleaned, SHARE_KEYWORDS) else 0.0) + (0.3 if hook_score > 0.4 else 0.0))
        click_potential = min(1.0, (0.6 if self._has_keywords(cleaned, CLICK_KEYWORDS) else 0.0) + (0.4 if has_link else 0.0))
        dwell_potential = min(1.0, (0.5 * length_score) + (0.3 * structure_score) + (0.2 * hook_score))
        clarity = self._clarity_score(avg_sentence_len, length, exclamations)

        negative_risk = self._negative_risk(
            cleaned,
            hashtags=hashtags,
            mentions=mentions,
            exclamations=exclamations,
            uppercase_ratio=uppercase_ratio,
        )

        components = {
            "reply_potential": reply_potential,
            "share_potential": share_potential,
            "click_potential": click_potential,
            "dwell_potential": dwell_potential,
            "clarity": clarity,
            "negative_risk": negative_risk,
        }

        notes = self._notes_from_components(
            reply_potential=reply_potential,
            share_potential=share_potential,
            click_potential=click_potential,
            dwell_potential=dwell_potential,
            clarity=clarity,
            negative_risk=negative_risk,
            length=length,
            content_type=content_type,
        )

        return ViralityResult(score=self._aggregate_score(components), components=components, notes=notes)

    @staticmethod
    def _aggregate_score(components: dict[str, float]) -> float:
        weights = {
            "reply_potential": 0.2,
            "share_potential": 0.25,
            "click_potential": 0.1,
            "dwell_potential": 0.25,
            "clarity": 0.2,
        }
        positive = sum(weights[key] * components.get(key, 0.0) for key in weights)
        penalty = components.get("negative_risk", 0.0) * 20.0
        return max(0.0, min(100.0, positive * 100.0 - penalty))

    @staticmethod
    def _length_score(length: int, content_type: ContentType) -> float:
        if content_type == ContentType.REPLY:
            ideal_min, ideal_max = 60, 200
        elif content_type == ContentType.QUOTE:
            ideal_min, ideal_max = 80, 200
        elif content_type == ContentType.THREAD:
            ideal_min, ideal_max = 120, 260
        else:
            ideal_min, ideal_max = 100, 220

        min_value, max_value = 30, 280
        if length <= min_value or length >= max_value:
            return 0.0
        if length < ideal_min:
            return (length - min_value) / max(ideal_min - min_value, 1)
        if length > ideal_max:
            return max(0.0, (max_value - length) / max(max_value - ideal_max, 1))
        return 1.0

    @staticmethod
    def _clarity_score(avg_sentence_len: float, length: int, exclamations: int) -> float:
        if avg_sentence_len <= 0:
            return 0.5
        base = 1.0 - min(1.0, abs(avg_sentence_len - 14) / 14)
        if length > 250:
            base *= 0.8
        if exclamations >= 4:
            base *= 0.8
        return max(0.0, min(1.0, base))

    @staticmethod
    def _has_keywords(text: str, keywords: Iterable[str]) -> bool:
        lowered = text.lower()
        return any(keyword in lowered for keyword in keywords)

    @staticmethod
    def _hook_score(text: str) -> float:
        words = re.findall(r"\b\w+\b", text.lower())
        first_words = " ".join(words[:12])
        if not first_words:
            return 0.0
        return 1.0 if any(keyword in first_words for keyword in HOOK_KEYWORDS) else 0.3

    @staticmethod
    def _negative_risk(
        text: str,
        *,
        hashtags: int,
        mentions: int,
        exclamations: int,
        uppercase_ratio: float,
    ) -> float:
        risk = 0.0
        lowered = text.lower()
        if any(re.search(pattern, lowered) for pattern in ENGAGEMENT_BAIT_PATTERNS):
            risk += 0.5
        if hashtags > 2:
            risk += 0.2
        if mentions > 2:
            risk += 0.2
        if exclamations > 3:
            risk += 0.1
        if uppercase_ratio > 0.35:
            risk += 0.2
        if re.search(r"\b(?:spam|giveaway|free money|pump)\b", lowered):
            risk += 0.2
        return min(1.0, risk)

    @staticmethod
    def _notes_from_components(
        *,
        reply_potential: float,
        share_potential: float,
        click_potential: float,
        dwell_potential: float,
        clarity: float,
        negative_risk: float,
        length: int,
        content_type: ContentType,
    ) -> list[str]:
        notes = []
        if share_potential >= 0.7:
            notes.append("Shareable insight")
        if reply_potential >= 0.7:
            notes.append("Strong reply prompt")
        if click_potential >= 0.7:
            notes.append("Clear click value")
        if dwell_potential >= 0.7:
            notes.append("Good dwell potential")
        if clarity < 0.5:
            notes.append("Clarity could be tighter")
        if negative_risk >= 0.5:
            notes.append("Risk: looks like engagement bait")

        if content_type != ContentType.THREAD:
            if length < 70:
                notes.append("May be too short")
            elif length > 250:
                notes.append("May be too long")

        return notes
