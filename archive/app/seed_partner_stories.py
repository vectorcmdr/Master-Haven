"""
Generate briefs + features from per-civ spreadsheet metadata.

Per the v0.8 decision (Parker, May 2026): NOT a template per civ. Each
story is written from the *specific* data that civ actually has in the
spreadsheet — civ_type, named leaders, war/alliance flags, fall dates,
agreement-type characterizations. Civs with only name + status get no
story (no fabrication).

Output (~16 stories):
  - 1 feature   (IEA — has multi-paragraph description)
  - ~15 briefs  (every civ with at least one substantive non-template
                 field beyond name + agreement type)

All seeded stories are authored by a synthetic 'vh-records' archive
user with a random un-guessable password so no-one can claim it via
the login flow. The byline reads as a system author.

Run on Pi:
    docker exec archive python -m app.seed_partner_stories --force

Idempotent — skips story slugs that already exist.
"""

from __future__ import annotations

import logging
import os
import re
import secrets
import sys
from datetime import datetime, timedelta

from sqlalchemy import text

from .db import session_scope
from .passwords import hash_password

log = logging.getLogger("archive.seed_partner_stories")

SEED_AUTHOR_USERNAME = "vh-records"
SEED_AUTHOR_DISPLAY = "VH Records"
SEED_AUTHOR_DISCORD_ID = "seed:vh-records"

# All stories get published timestamps spread across a 16-day window
# ending today, so the newsroom shows them in a varied chronological
# order rather than all bunched up at the same second.
SEED_BASE_DATE = datetime(2026, 5, 17)  # most-recent story dated here


def _slug(s: str, maxlen: int = 64) -> str:
    s = s.lower().strip().rstrip("*").strip()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:maxlen] or "untitled"


def _ensure_seed_author(s) -> int:
    """Get-or-create the vh-records synthetic author. Returns user id."""
    row = s.execute(
        text("SELECT id FROM archive_user WHERE discord_id = :did"),
        {"did": SEED_AUTHOR_DISCORD_ID},
    ).first()
    if row:
        return row.id
    # Random un-guessable password so this account can't be claimed via login
    random_pwd = secrets.token_urlsafe(32)
    result = s.execute(
        text(
            "INSERT INTO archive_user ("
            "discord_id, discord_username, display_name, avatar_letter,"
            " avatar_color, base_role, is_editor, is_admin, password_hash, bio"
            ") VALUES ("
            ":did, :u, :n, :l, :c, 'historian', 1, 0, :pwd, :bio"
            ")"
        ),
        {
            "did": SEED_AUTHOR_DISCORD_ID,
            "u": SEED_AUTHOR_USERNAME,
            "n": SEED_AUTHOR_DISPLAY,
            "l": "V",
            "c": "amber",
            "pwd": hash_password(random_pwd),
            "bio": (
                "Voyager's Haven partner records keeper. Authors archive "
                "entries derived from the VH partner spreadsheet — formal "
                "agreements, fall events, INTERCIV records."
            ),
        },
    )
    new_id = result.lastrowid
    log.info("created seed author vh-records (id=%d)", new_id)
    return new_id


# =====================================================================
# STORIES — written PER CIV from the actual spreadsheet content
# =====================================================================
# Each entry has: civ_slug, doctype, beat, headline, deck, body.
# Body uses real fields from that civ's row. No invented facts.

STORIES: list[dict] = [
    # ----- THE FEATURE -----
    {
        "civ_slug": "iea",
        "doctype": "feature",
        "beat": "projects",
        "headline": "IEA: a community for the cosmos's explorers",
        "deck": (
            "Independent Exploration Alliance — chartered partner of "
            "Voyager's Haven, archive-agreement holder, and one of the "
            "few partner civs whose self-description appears in VH "
            "records verbatim."
        ),
        "body": (
            "Of the 172 civilizations tracked in Voyager's Haven's partner "
            "records, only one arrived with a self-written charter long "
            "enough to publish in full. That community is the Independent "
            "Exploration Alliance — the IEA.\n\n"
            "The IEA's own words, as supplied to VH partner records:\n\n"
            "> 🚀 **Who We Are:** The IEA is a community of like-minded "
            "individuals dedicated to the exploration of the cosmos. "
            "Whether you're an experienced spacefarer or a newcomer to "
            "the stars, everyone is welcome to join our ranks. Together, "
            "we embark on expeditions, conduct research, and unravel the "
            "mysteries of the universe.\n\n"
            "> 🔭 **What We Do:**\n"
            "> **Exploration:** Journey to the far reaches of the universe "
            "and beyond, charting unexplored territories and discovering "
            "new celestial wonders.\n"
            "> **Research:** Engage in scientific inquiry, studying the "
            "cosmos to deepen our understanding of its vastness and "
            "complexity.\n"
            "> **Collaboration:** Foster collaboration and camaraderie "
            "among members, sharing knowledge and resources to further "
            "our collective exploration efforts.\n\n"
            "The IEA holds both a Chartered Partner relationship and an "
            "Archive Agreement with Voyager's Haven. VH partner records "
            "note one operational specific: the IEA provides a bot for "
            "the \"bot-dev\" role. The IEA's Discord is open to public "
            "join: https://discord.gg/kyhMHAAMcM.\n\n"
            "This entry is preserved in the Travelers Archive as the "
            "IEA's foundational record."
        ),
    },

    # ----- BRIEFS -----
    {
        "civ_slug": "black-edge-syndicate",
        "doctype": "brief",
        "beat": "diplomacy",
        "headline": "Black Edge Syndicate: outlaw council of four chartered with Haven",
        "deck": (
            "BES holds both Chartered Partner status and an Archive "
            "Agreement, governed by a four-member council in the RP "
            "outlaw-syndicate tradition."
        ),
        "body": (
            "Black Edge Syndicate (BES) is recorded in Voyager's Haven "
            "partner records as a Chartered Partner with an Archive "
            "Agreement — one of the small number of communities holding "
            "both relationships simultaneously.\n\n"
            "BES is classified as an RP: Outlaw Syndicate. Its governance "
            "sits with a Council of four named members: Unknown Regions, "
            "Lucca, Jaina Siderea, and HandlesofGod. The Discord is open "
            "to public join: https://discord.gg/7ZGtw5zuXq.\n\n"
            "Tag in VH records: BES."
        ),
    },
    {
        "civ_slug": "aculon",
        "doctype": "brief",
        "beat": "diplomacy",
        "headline": "Aculon: a verbal alliance under Augustus",
        "deck": (
            "Aculon, an RP-Empire community led by Augustus, holds a "
            "Partner agreement with Voyager's Haven on a verbal basis."
        ),
        "body": (
            "Aculon is recorded as a Partner of Voyager's Haven. The civ "
            "is classified as an RP: Empire and is led by Augustus. The "
            "partnership itself is a verbal agreement — no written "
            "charter is on file in VH partner records.\n\n"
            "Aculon's Discord is open to public join: "
            "https://discord.gg/rhbt23sws9."
        ),
    },
    {
        "civ_slug": "canvas-town",
        "doctype": "brief",
        "beat": "projects",
        "headline": "Canvas Town: interciv gaming under Rasquel and WhrStrsG",
        "deck": (
            "Founded by Rasquel and WhrStrsG, Canvas Town runs as a "
            "cross-member interciv gaming community. Voyager's Haven "
            "holds a Chartered Partnership; the relationship status "
            "note: \"Interest.\""
        ),
        "body": (
            "Canvas Town is a Chartered Partner of Voyager's Haven, "
            "classified in VH partner records as a CM (cross-member) "
            "interciv gaming community. Its founders are Rasquel and "
            "WhrStrsG.\n\n"
            "The current status note in VH partner records reads simply "
            "\"Interest\" — characterizing the relationship as one of "
            "active mutual interest rather than a settled program. "
            "Discord: https://discord.gg/YkqWfdSEAq."
        ),
    },
    {
        "civ_slug": "aurelis-prime",
        "doctype": "brief",
        "beat": "diplomacy",
        "headline": "Aurelis Prime: chartered partnership held by a staff trio",
        "deck": (
            "Aurelis Prime holds both Chartered Partner status and an "
            "Archive Agreement. Governance sits with three named "
            "staff members."
        ),
        "body": (
            "Aurelis Prime is recorded as a Chartered Partner of "
            "Voyager's Haven with an additional Archive Agreement in "
            "place. The relationship is noted in VH records simply as "
            "\"partnership.\"\n\n"
            "The governing staff trio: Lagz, SirDwayne, and SirHobo."
        ),
    },
    {
        "civ_slug": "covenant-of-the-void",
        "doctype": "brief",
        "beat": "diplomacy",
        "headline": "Covenant of the Void: led by the Void Speaker",
        "deck": (
            "Covenant of the Void holds a Partner agreement with "
            "Voyager's Haven. Leadership carries the title \"Void "
            "Speaker.\""
        ),
        "body": (
            "Covenant of the Void is a Partner of Voyager's Haven. The "
            "community is led by Toruuk Makto, whose title in VH "
            "partner records is \"Void Speaker\" — the only civ in the "
            "current partner roster whose leadership uses that "
            "particular formulation.\n\n"
            "Discord: https://discord.gg/66rxWJGWzZ."
        ),
    },
    {
        "civ_slug": "everion",
        "doctype": "brief",
        "beat": "diplomacy",
        "headline": "Everion confirmed as official allies",
        "deck": (
            "VH partner records, per Lucca's note, designate Everion as "
            "\"OFFICIAL ALLIES.\" The civ also holds an Archive "
            "Agreement."
        ),
        "body": (
            "Everion is recorded in Voyager's Haven partner records as "
            "an Archive-Agreement civ with the explicit additional "
            "designation of \"OFFICIAL ALLIES,\" per Lucca's annotation.\n\n"
            "The capitalization is preserved verbatim from the VH "
            "spreadsheet — the formality of the designation appears "
            "intentional. Everion is one of the small number of partner "
            "civs whose relationship with VH has been escalated beyond "
            "an archive-only arrangement."
        ),
    },
    {
        "civ_slug": "pirate-kingdom-dominion",
        "doctype": "brief",
        "beat": "conflicts",
        "headline": "Pirate Kingdom/Dominion: a presence in Haven space, at war with allies",
        "deck": (
            "Per Lucca's note in VH records: Pirate Kingdom/Dominion "
            "holds an Archive Agreement with Voyager's Haven while "
            "maintaining a contested presence inside Haven space and "
            "an open war with VH allies."
        ),
        "body": (
            "Pirate Kingdom/Dominion's relationship with Voyager's "
            "Haven is two-sided. VH partner records register an Archive "
            "Agreement — the standard documentation arrangement. "
            "Simultaneously, per Lucca's annotation, the civ \"has "
            "presence in haven, [and is] at war with allies.\"\n\n"
            "The combination of an active archive relationship and a "
            "war footing against VH allies makes Pirate Kingdom/Dominion "
            "one of the partner roster's more complex entries. The "
            "archive holds the record; the diplomatic posture is "
            "contested."
        ),
    },
    {
        "civ_slug": "archduchy-of-nicea",
        "doctype": "brief",
        "beat": "diplomacy",
        "headline": "Archduchy of Nicea: an aggressive partner",
        "deck": (
            "Nicea holds Partner status. The relationship is characterized "
            "in VH records as \"aggressive.\""
        ),
        "body": (
            "The Archduchy of Nicea is recorded as a Partner of "
            "Voyager's Haven. VH partner records carry one notation: "
            "\"aggressive.\"\n\n"
            "Whether this characterizes Nicea's broader posture toward "
            "the multiverse, its conduct within the partnership itself, "
            "or both, is not specified in the record."
        ),
    },
    {
        "civ_slug": "redwater-runners",
        "doctype": "brief",
        "beat": "diplomacy",
        "headline": "Redwater Runners: archive agreement, aggressive posture",
        "deck": (
            "Redwater Runners holds an Archive Agreement; VH records "
            "note the civ as \"aggressive.\""
        ),
        "body": (
            "Redwater Runners is recorded in Voyager's Haven partner "
            "records as holding an Archive Agreement. The notes column "
            "characterizes the civ as \"aggressive\" — the same "
            "designation applied to the Archduchy of Nicea.\n\n"
            "As with Nicea, the record does not specify whether the "
            "aggression is general posture or has manifested in the "
            "partnership."
        ),
    },
    {
        "civ_slug": "alliance-of-galactic-travelers",
        "doctype": "brief",
        "beat": "diplomacy",
        "headline": "Alliance of Galactic Travelers: archive partnership under uncertain warmth",
        "deck": (
            "AGT holds an Archive Agreement with Voyager's Haven. VH "
            "records flag the relationship's warmth as a question: "
            "\"Dismissive?\""
        ),
        "body": (
            "The Alliance of Galactic Travelers (AGT) holds an Archive "
            "Agreement with Voyager's Haven. VH partner records carry "
            "one annotation, posed as a question rather than a "
            "statement: \"Dismissive?\"\n\n"
            "The relationship is therefore documented as active but "
            "uncertain. AGT's Discord: https://discord.gg/vJpvKSRkQH."
        ),
    },
    {
        "civ_slug": "pax-cosmica",
        "doctype": "brief",
        "beat": "civupdates",
        "headline": "Pax Cosmica falls — INTERCIV member dissolved 22/11/25",
        "deck": (
            "Pax Cosmica, a former member of an INTERCIV multi-civ body, "
            "is recorded as fallen on 22 November 2025."
        ),
        "body": (
            "Pax Cosmica, recorded in Voyager's Haven INTERCIV registers "
            "as a former member, is logged as fallen on 22/11/25 (22 "
            "November 2025).\n\n"
            "The civ is one of nine INTERCIV-affiliated communities "
            "presently archived. Of the nine, Pax Cosmica is the only "
            "one for which VH records preserve a concrete fall date — "
            "the rest are documented as fallen without a specific date.\n\n"
            "This entry preserves the date as a historical record."
        ),
    },
    {
        "civ_slug": "neo-terra",
        "doctype": "brief",
        "beat": "diplomacy",
        "headline": "Neo Terra archive partnership — potential building agreement on file",
        "deck": (
            "Neo Terra holds an Archive Agreement. VH records additionally "
            "flag a potential building agreement under consideration."
        ),
        "body": (
            "Neo Terra is recorded as an Archive-Agreement partner of "
            "Voyager's Haven. The relationship has a specific extension "
            "noted in VH partner records: a \"potential building "
            "agreement\" — the kind of construction-focused "
            "collaboration the Haven occasionally negotiates beyond a "
            "standard archive relationship.\n\n"
            "No formal building agreement has yet been logged as "
            "executed."
        ),
    },
    {
        "civ_slug": "indominus-legion",
        "doctype": "brief",
        "beat": "diplomacy",
        "headline": "Indominus Legion: archive partnership + envoy expedition",
        "deck": (
            "Indominus Legion holds an Archive Agreement and an envoy "
            "expedition arrangement — characterized in VH records as a "
            "general partnership."
        ),
        "body": (
            "Indominus Legion is recorded in Voyager's Haven partner "
            "records as holding two arrangements simultaneously: an "
            "Archive Agreement and an Envoy Expedition. The combined "
            "relationship is described as a \"General partnership.\"\n\n"
            "The envoy-expedition designation is the more distinctive "
            "of the two — relatively few civs on the partner roster "
            "carry it."
        ),
    },
    {
        "civ_slug": "kos-dawnblade-kingdom",
        "doctype": "brief",
        "beat": "diplomacy",
        "headline": "KOS/Dawnblade Kingdom: exploration agreement under partnership",
        "deck": (
            "KOS / Dawnblade Kingdom holds a Partner agreement plus an "
            "exploration agreement and a general partnership."
        ),
        "body": (
            "KOS/Dawnblade Kingdom is recorded as a Partner of Voyager's "
            "Haven. The relationship covers a General Partnership and an "
            "Exploration Agreement — the exploration component is the "
            "more specific of the two, signalling intent toward joint "
            "exploration activity rather than purely passive partnership."
        ),
    },
    {
        "civ_slug": "the-crimson-runners",
        "doctype": "brief",
        "beat": "civupdates",
        "headline": "The Crimson Runners: chartered partner, listed among archived agreements",
        "deck": (
            "The Crimson Runners hold Chartered Partner + Archive "
            "Agreement status, yet appear in the \"Archived agreements\" "
            "section of VH partner records — an unusual placement."
        ),
        "body": (
            "The Crimson Runners occupy an unusual position in Voyager's "
            "Haven partner records. The civ is documented as a "
            "Chartered Partner with an Archive Agreement — both active "
            "designations — but the row appears under the \"Archived "
            "agreements\" section of the VH partner spreadsheet, "
            "alongside fallen civs.\n\n"
            "The placement may reflect a transition state, a "
            "categorization quirk, or pending action by VH leadership. "
            "The record is preserved as-is."
        ),
    },
]


def seed_partner_stories(force: bool = False) -> None:
    if not force and os.environ.get("ARCHIVE_SEED_STORIES", "") != "1":
        log.info("seed_partner_stories: ARCHIVE_SEED_STORIES!=1 — skipping. Pass --force to run.")
        return
    log.info("seed_partner_stories: %d stories to consider", len(STORIES))
    inserted = 0
    skipped = 0
    skipped_civ_missing = 0
    with session_scope() as s:
        author_id = _ensure_seed_author(s)
        for i, st in enumerate(STORIES):
            # Verify the civ this story is tagged to exists
            civ_row = s.execute(
                text("SELECT 1 FROM civilization WHERE slug = :s AND deleted_at IS NULL"),
                {"s": st["civ_slug"]},
            ).first()
            if not civ_row:
                log.warning("civ %r not found, skipping story %r", st["civ_slug"], st["headline"])
                skipped_civ_missing += 1
                continue

            slug = _slug(st["headline"])
            existing = s.execute(
                text("SELECT 1 FROM story WHERE slug = :s"), {"s": slug},
            ).first()
            if existing:
                skipped += 1
                continue

            # Spread publish dates: most recent first
            published_at = (SEED_BASE_DATE - timedelta(days=i)).isoformat(sep=" ")
            read_minutes = 4 if st["doctype"] == "feature" else None

            result = s.execute(
                text(
                    "INSERT INTO story ("
                    "slug, doctype, headline, deck, body, beat,"
                    " author_id, published_at, read_minutes"
                    ") VALUES ("
                    ":slug, :doctype, :headline, :deck, :body, :beat,"
                    " :author_id, :published_at, :read_minutes"
                    ")"
                ),
                {
                    "slug": slug,
                    "doctype": st["doctype"],
                    "headline": st["headline"],
                    "deck": st.get("deck"),
                    "body": st["body"],
                    "beat": st.get("beat"),
                    "author_id": author_id,
                    "published_at": published_at,
                    "read_minutes": read_minutes,
                },
            )
            story_id = result.lastrowid
            # Tag to its civ so it shows on the civ's coverage list
            s.execute(
                text(
                    "INSERT OR IGNORE INTO story_civilization (story_id, civ_slug) "
                    "VALUES (:sid, :cs)"
                ),
                {"sid": story_id, "cs": st["civ_slug"]},
            )
            inserted += 1

    log.info(
        "seed_partner_stories: inserted %d, skipped %d (already existed), %d (civ missing)",
        inserted, skipped, skipped_civ_missing,
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    seed_partner_stories(force="--force" in sys.argv)
