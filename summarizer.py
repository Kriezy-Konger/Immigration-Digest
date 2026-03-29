"""
summarizer.py — Uses Claude to transform raw regulatory items into
plain-English summaries with HR action items. Also self-scores quality.
"""

import os
from dataclasses import dataclass

import anthropic
from dotenv import load_dotenv
from loguru import logger

from scraper import RawItem

load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DigestItem:
    source_name: str
    title: str
    url: str
    priority: str
    tags: list[str]
    # Claude-generated fields
    headline: str         # 1 punchy sentence — what happened
    plain_summary: str    # 2-3 sentences — what it means for HR
    action_items: list[str]  # concrete steps HR should take (0-3 bullets)
    urgency: str          # "Action required", "Monitor", "FYI"
    deadline: str         # e.g. "April 1, 2026" or "No deadline"


@dataclass
class DigestPackage:
    items: list[DigestItem]
    quality_score: int      # Claude's self-score 1–10
    quality_notes: str      # Claude's reasoning on quality
    send_recommended: bool  # True if score >= MIN_QUALITY_SCORE


# ─────────────────────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert immigration compliance analyst helping 
HR managers at small and mid-size US companies (50–500 employees) stay on top 
of US immigration law changes that affect their workforce.

Your readers are HR managers and operations leads — NOT lawyers. They are 
busy, non-expert, and need:
1. Clarity over precision (plain English, no legalese)
2. Actionable next steps (what do I actually DO?)
3. Urgency signals (is this fire-drill or FYI?)

You are NOT providing legal advice. You are summarizing publicly available 
regulatory news. Always note they should consult immigration counsel for 
specific situations.

Tone: Professional but direct. Like a knowledgeable colleague, not a textbook.
"""

ITEM_SUMMARY_PROMPT = """Analyze this regulatory item and extract structured 
information for HR managers.

SOURCE: {source_name}
TITLE: {title}
URL: {url}
CONTENT:
{content}

Respond in this EXACT JSON format (no markdown, raw JSON only):
{{
  "headline": "One punchy sentence summarizing what changed",
  "plain_summary": "2-3 sentences explaining what this means for HR teams at US companies that sponsor visas or employ foreign workers. Plain English only.",
  "action_items": [
    "Specific action 1 (verb-first, concrete)",
    "Specific action 2 (optional)",
    "Specific action 3 (optional)"
  ],
  "urgency": "Action required | Monitor | FYI",
  "deadline": "Specific date if mentioned, otherwise 'No deadline' or 'Ongoing'"
}}

Rules:
- action_items: 0-3 items only. If no action needed, return empty array []
- urgency: "Action required" = something must be done now; "Monitor" = watch this develop; "FYI" = background awareness
- If content is not relevant to US HR/immigration compliance, return urgency: "FYI" and empty action_items
- Be specific about form numbers, dates, dollar amounts when present
"""

QUALITY_SCORE_PROMPT = """You are evaluating the quality of today's 
immigration compliance digest before it goes out to HR managers.

Here are today's digest items:
{digest_summary}

Score the overall digest quality from 1-10 based on:
- Relevance: Are items actually relevant to HR teams managing US immigration?
- Actionability: Do items have clear next steps where needed?
- Accuracy: Do summaries reflect the source content fairly?
- Value: Would an HR manager find this worth reading today?

Respond in this EXACT JSON format:
{{
  "score": <integer 1-10>,
  "notes": "2-3 sentences explaining the score and any issues",
  "send_recommended": <true if score >= 7, false otherwise>
}}
"""


# ─────────────────────────────────────────────────────────────────────────────
# Claude client
# ─────────────────────────────────────────────────────────────────────────────

class Summarizer:
    def __init__(self):
        self.client = anthropic.Anthropic(
            api_key=os.environ["ANTHROPIC_API_KEY"]
        )
        self.model = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
        self.min_quality = int(os.environ.get("MIN_QUALITY_SCORE", 7))

    def _call_claude(self, prompt: str, max_tokens: int = 800) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()

    def summarize_item(self, item: RawItem) -> DigestItem | None:
        """Summarize a single raw item into a structured DigestItem."""
        import json

        prompt = ITEM_SUMMARY_PROMPT.format(
            source_name=item.source_name,
            title=item.title,
            url=item.url,
            content=item.content[:3000]  # stay well within context
        )

        try:
            raw = self._call_claude(prompt, max_tokens=600)
            # Strip any accidental markdown code fences
            raw = raw.replace("```json", "").replace("```", "").strip()
            data = json.loads(raw)

            return DigestItem(
                source_name  = item.source_name,
                title        = item.title,
                url          = item.url,
                priority     = item.priority,
                tags         = item.tags,
                headline     = data.get("headline", item.title),
                plain_summary = data.get("plain_summary", ""),
                action_items = data.get("action_items", []),
                urgency      = data.get("urgency", "FYI"),
                deadline     = data.get("deadline", "No deadline"),
            )
        except Exception as e:
            logger.error(f"Summarize failed for '{item.title}': {e}")
            return None

    def score_digest(self, items: list[DigestItem]) -> tuple[int, str, bool]:
        """Ask Claude to score the digest quality before sending."""
        import json

        if not items:
            return 0, "No items to score.", False

        # Build a compact digest summary for scoring
        lines = []
        for i, item in enumerate(items, 1):
            lines.append(
                f"{i}. [{item.urgency}] {item.headline} "
                f"(actions: {len(item.action_items)})"
            )
        digest_summary = "\n".join(lines)

        prompt = QUALITY_SCORE_PROMPT.format(digest_summary=digest_summary)

        try:
            raw = self._call_claude(prompt, max_tokens=300)
            raw = raw.replace("```json", "").replace("```", "").strip()
            data = json.loads(raw)
            score = int(data.get("score", 5))
            notes = data.get("notes", "")
            send  = bool(data.get("send_recommended", score >= self.min_quality))
            return score, notes, send
        except Exception as e:
            logger.error(f"Quality scoring failed: {e}")
            # Default: send if we have at least 1 critical/high item
            has_important = any(i.urgency == "Action required" for i in items)
            return 6, f"Scoring failed ({e}), defaulting based on content.", has_important

    def build_digest(self, raw_items: list[RawItem]) -> DigestPackage:
        """
        Full pipeline: raw items → summarized DigestItems → quality scored package.
        Only processes up to 20 items per day to keep costs low.
        """
        logger.info(f"Summarizing {len(raw_items)} items with Claude...")
        
        # Cap at 20 items, prefer critical/high priority
        items_to_process = raw_items[:20]

        digest_items = []
        for item in items_to_process:
            logger.info(f"  Summarizing: {item.title[:70]}")
            result = self.summarize_item(item)
            if result:
                digest_items.append(result)

        # Filter out pure FYI with no action items to keep digest tight
        # Keep all "Action required" and "Monitor"; FYI only if it has action items
        filtered = [
            d for d in digest_items
            if d.urgency != "FYI" or len(d.action_items) > 0
        ]

        # If filtering removed too much, keep top items regardless
        if len(filtered) < 3 and len(digest_items) >= 3:
            filtered = digest_items[:5]

        logger.info(f"  {len(filtered)} items after relevance filter.")

        # Quality gate
        score, notes, send_ok = self.score_digest(filtered)
        logger.info(f"  Quality score: {score}/10 — {notes}")
        logger.info(f"  Send recommended: {send_ok}")

        return DigestPackage(
            items             = filtered,
            quality_score     = score,
            quality_notes     = notes,
            send_recommended  = send_ok,
        )


if __name__ == "__main__":
    # Quick test with a fake item
    from scraper import RawItem
    from datetime import datetime, timezone

    logger.add("./logs/summarizer.log", rotation="7 days")

    test_item = RawItem(
        source_id    = "uscis_news",
        source_name  = "USCIS News",
        title        = "USCIS Announces New I-9 Form Version Required Starting April 2026",
        url          = "https://www.uscis.gov/fake-test-url",
        content      = (
            "USCIS today announced that all employers must begin using the "
            "new Form I-9 (version 10/15/25) starting April 1, 2026. "
            "Employers using older versions after this date may face civil "
            "penalties of up to $2,500 per violation for first offenses. "
            "The new form includes updated List C documents and revised "
            "instructions for remote verification under the E-Verify "
            "Alternative Procedure."
        ),
        published    = datetime.now(timezone.utc).isoformat(),
        priority     = "critical",
        tags         = ["i9", "forms", "e_verify"],
        content_hash = "test_hash_001",
    )

    summarizer = Summarizer()
    result = summarizer.summarize_item(test_item)
    if result:
        print(f"\n✅ HEADLINE: {result.headline}")
        print(f"   SUMMARY:  {result.plain_summary}")
        print(f"   URGENCY:  {result.urgency}")
        print(f"   DEADLINE: {result.deadline}")
        print(f"   ACTIONS:  {result.action_items}")
