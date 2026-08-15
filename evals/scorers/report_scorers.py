"""Report evaluation scorers for completeness and clarity."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScorerResult:
    """Standard result returned by all scorers."""

    name: str
    score: float  # 0.0 to 1.0
    passed: bool
    details: dict[str, Any] = field(default_factory=dict)


class Completeness:
    """Check that a generated report contains all expected sections.

    Performs case-insensitive matching for section headings in the report
    text. Supports both markdown headings (## Section) and bold headings
    (**Section**).
    """

    def score(
        self,
        report: str,
        expected_sections: list[str],
    ) -> ScorerResult:
        """Score report completeness by checking for expected sections.

        Args:
            report: The generated report text (markdown).
            expected_sections: Section titles that should appear in the report.

        Returns:
            ScorerResult with score based on fraction of sections found.
        """
        if not expected_sections:
            return ScorerResult(
                name="report_completeness",
                score=1.0,
                passed=True,
                details={"message": "No expected sections provided"},
            )

        if not report or not report.strip():
            return ScorerResult(
                name="report_completeness",
                score=0.0,
                passed=False,
                details={"error": "Empty report", "missing": expected_sections},
            )

        report_lower = report.lower()
        found: list[str] = []
        missing: list[str] = []

        for section in expected_sections:
            section_lower = section.lower()
            # Check multiple heading formats:
            # - Markdown: ## Section Name, ### Section Name
            # - Bold: **Section Name**
            # - Plain text occurrence
            patterns = [
                rf"#{1,6}\s*{re.escape(section_lower)}",  # Markdown heading
                rf"\*\*{re.escape(section_lower)}\*\*",    # Bold heading
                section_lower,                              # Plain text
            ]
            if any(re.search(p, report_lower) for p in patterns):
                found.append(section)
            else:
                missing.append(section)

        total = len(expected_sections)
        score = len(found) / total if total > 0 else 0.0
        passed = score >= 0.8  # At least 80% of sections present

        return ScorerResult(
            name="report_completeness",
            score=round(score, 4),
            passed=passed,
            details={"found": found, "missing": missing, "total_sections": total},
        )


class Clarity:
    """Score report clarity using string-based readability heuristics.

    Checks for:
    - Presence of structured formatting (headings, bullets, numbered lists)
    - Reasonable sentence length (not overly long or short)
    - Use of specific numbers / data references
    - Absence of vague filler phrases
    - Adequate report length
    """

    # Vague phrases that reduce clarity
    VAGUE_PHRASES = [
        "it is important to note",
        "as we can see",
        "needless to say",
        "it goes without saying",
        "it should be noted",
        "various reasons",
        "many factors",
        "a number of things",
    ]

    def score(self, report: str) -> ScorerResult:
        """Score report clarity using readability heuristics.

        Args:
            report: The generated report text.

        Returns:
            ScorerResult with score between 0.0 and 1.0.
        """
        if not report or not report.strip():
            return ScorerResult(
                name="report_clarity",
                score=0.0,
                passed=False,
                details={"error": "Empty report"},
            )

        checks: dict[str, dict[str, Any]] = {}
        total_score = 0.0
        num_checks = 5

        # 1. Structured formatting (headings, bullets)
        has_headings = bool(re.search(r"^#{1,6}\s", report, re.MULTILINE))
        has_bullets = bool(re.search(r"^[\s]*[-*]\s", report, re.MULTILINE))
        has_numbered = bool(re.search(r"^[\s]*\d+[.)]\s", report, re.MULTILINE))
        formatting_score = 0.0
        if has_headings:
            formatting_score += 0.5
        if has_bullets or has_numbered:
            formatting_score += 0.5
        total_score += formatting_score
        checks["formatting"] = {
            "score": formatting_score,
            "has_headings": has_headings,
            "has_bullets": has_bullets,
            "has_numbered": has_numbered,
        }

        # 2. Sentence length distribution
        sentences = re.split(r"[.!?]+", report)
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 5]
        if sentences:
            avg_words = sum(len(s.split()) for s in sentences) / len(sentences)
            # Ideal avg sentence length: 10-25 words
            if 10 <= avg_words <= 25:
                sentence_score = 1.0
            elif 5 <= avg_words < 10 or 25 < avg_words <= 35:
                sentence_score = 0.6
            else:
                sentence_score = 0.3
        else:
            sentence_score = 0.0
        total_score += sentence_score
        checks["sentence_length"] = {
            "score": sentence_score,
            "avg_words_per_sentence": round(avg_words, 1) if sentences else 0,
            "num_sentences": len(sentences),
        }

        # 3. Specific numbers / data references
        number_matches = re.findall(r"\b\d+[,.]?\d*%?\b", report)
        # Filter out line numbers / formatting artifacts
        meaningful_numbers = [n for n in number_matches if len(n) > 0]
        numbers_score = min(1.0, len(meaningful_numbers) / 5.0)  # Expect at least 5 numbers
        total_score += numbers_score
        checks["specificity"] = {
            "score": round(numbers_score, 2),
            "numbers_found": len(meaningful_numbers),
        }

        # 4. Absence of vague filler phrases
        report_lower = report.lower()
        vague_found = [p for p in self.VAGUE_PHRASES if p in report_lower]
        vague_score = max(0.0, 1.0 - len(vague_found) * 0.25)
        total_score += vague_score
        checks["conciseness"] = {
            "score": round(vague_score, 2),
            "vague_phrases_found": vague_found,
        }

        # 5. Adequate length (at least 200 chars, ideally 500+)
        length = len(report.strip())
        if length >= 500:
            length_score = 1.0
        elif length >= 200:
            length_score = 0.7
        elif length >= 50:
            length_score = 0.3
        else:
            length_score = 0.0
        total_score += length_score
        checks["length"] = {
            "score": length_score,
            "char_count": length,
        }

        final_score = total_score / num_checks
        passed = final_score >= 0.6

        return ScorerResult(
            name="report_clarity",
            score=round(final_score, 4),
            passed=passed,
            details={"checks": checks},
        )
