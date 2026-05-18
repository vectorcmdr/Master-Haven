"""
Seed the real Voyager's Haven partner list as `civilization` rows.

Source: VH partner-tracking spreadsheet (Google Sheets, May 2026).
Scope: active partners + chartered partners + archive-agreement civs
(~28 rows) plus formally-affiliated INTERCIV / former-member civs
(~9 rows, status=archived). Skips the ~80 "not joined" entries which
are just names on a wishlist, not real archive content.

Run as:
    docker exec archive python -m app.seed_partners
    (also gated behind ARCHIVE_SEED_PARTNERS=1 to prevent accidental
    re-seeding on boot)

Idempotent: skips rows whose slug already exists.
"""

from __future__ import annotations

import logging
import os
import re
import sys

from sqlalchemy import text

from .db import session_scope

log = logging.getLogger("archive.seed_partners")


# A small palette of color pairs to assign deterministically per civ.
# Index = sum(ord(c) for c in slug) % len(palette). Stable across runs.
PALETTE: list[tuple[str, str]] = [
    ("#042C53", "#0F6E56"),   # deep teal-blue
    ("#4A1B0C", "#993C1D"),   # rust
    ("#26215C", "#534AB7"),   # twilight violet
    ("#173404", "#639922"),   # forest
    ("#5C1F4D", "#993556"),   # mulberry
    ("#1F2D3A", "#4F7A9E"),   # slate
    ("#633806", "#C18C2D"),   # bronze
    ("#3C1F4D", "#7D3F8C"),   # plum
    ("#0F4C5C", "#3E92B5"),   # ocean
    ("#5C2B0F", "#C46A2D"),   # ember
    ("#1A3D1B", "#4A8F3C"),   # moss
    ("#3E2A56", "#7E5BAA"),   # iris
]


def _slug(name: str) -> str:
    """Lowercase, strip non-alnum to dashes, trim, cap 64 chars."""
    s = name.lower().strip().rstrip("*").strip()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:64] or "unnamed"


def _colors_for(slug: str) -> tuple[str, str]:
    return PALETTE[sum(ord(c) for c in slug) % len(PALETTE)]


def _build_description(
    *,
    agreement_type: str | None,
    civ_type: str | None,
    notes: str | None,
    long_description: str | None,
    discord_link: str | None,
    leaders: str | None,
    tag: str | None,
) -> str:
    """Compose a readable description from the spreadsheet columns."""
    lines: list[str] = []
    if long_description:
        # Some rows (IEA) have a multi-paragraph rich description; lead with it
        lines.append(long_description.strip())
    if civ_type:
        lines.append(f"**Type:** {civ_type.strip()}")
    if agreement_type:
        lines.append(f"**Voyager's Haven status:** {agreement_type.strip()}")
    if leaders:
        lines.append(f"**Leaders:** {leaders.strip()}")
    if tag:
        lines.append(f"**Tag:** `{tag.strip()}`")
    if discord_link:
        lines.append(f"**Discord:** {discord_link.strip()}")
    if notes:
        lines.append(f"_Notes (from VH partner records):_ {notes.strip()}")
    return "\n\n".join(lines) if lines else None  # type: ignore[return-value]


# =====================================================================
# DATA — extracted from VH partner sheet, gid=0
# =====================================================================
# Each row is (name, agreement_type, civ_type, notes, long_description,
#              discord_link, leaders, tag, status).
# status: 'active' (current partner) / 'archived' (former, fallen, INTERCIV)

ACTIVE_PARTNERS: list[dict] = [
    {
        "name": "Voyager's Haven",
        "agreement_type": "Host",
        "civ_type": "Workshop community",
        "notes": "Operates the Travelers Archive (this site).",
        "long_description": None,
        "discord_link": None,
        "leaders": "Founder: Ekimo",
        "tag": "VH",
        "status": "active",
    },
    {
        "name": "Aculon",
        "agreement_type": "Partner",
        "civ_type": "RP: Empire",
        "notes": "Verbal agreement.",
        "long_description": None,
        "discord_link": "https://discord.gg/rhbt23sws9",
        "leaders": "Augustus",
        "tag": None,
        "status": "active",
    },
    {
        "name": "Alliance of Galactic Travelers",
        "agreement_type": "Archive Agreement",
        "civ_type": None,
        "notes": "Dismissive?",
        "long_description": None,
        "discord_link": "https://discord.gg/vJpvKSRkQH",
        "leaders": None,
        "tag": "AGT",
        "status": "active",
    },
    {
        "name": "Atlas-CSD/ETARC",
        "agreement_type": "Partners",
        "civ_type": None,
        "notes": None,
        "long_description": None,
        "discord_link": "https://forums.atlas-65.com/",
        "leaders": None,
        "tag": "ETARC",
        "status": "active",
    },
    {
        "name": "Aurelis Prime",
        "agreement_type": "Chartered Partner, Archive Agreement",
        "civ_type": None,
        "notes": "Partnership.",
        "long_description": None,
        "discord_link": None,
        "leaders": "Staff: Lagz, SirDwayne, SirHobo",
        "tag": None,
        "status": "active",
    },
    {
        "name": "Black Edge Syndicate",
        "agreement_type": "Chartered Partner, Archive Agreement",
        "civ_type": "RP: Outlaw Syndicate",
        "notes": None,
        "long_description": None,
        "discord_link": "https://discord.gg/7ZGtw5zuXq",
        "leaders": "Council: Unknown Regions, Lucca, Jaina Siderea, HandlesofGod",
        "tag": "BES",
        "status": "active",
    },
    {
        "name": "Canvas Town",
        "agreement_type": "Chartered Partner",
        "civ_type": "CM: Interciv gaming",
        "notes": "Interest.",
        "long_description": None,
        "discord_link": "https://discord.gg/YkqWfdSEAq",
        "leaders": "Founders: Rasquel, WhrStrsG",
        "tag": None,
        "status": "active",
    },
    {
        "name": "Covenant of the Void",
        "agreement_type": "Partner",
        "civ_type": None,
        "notes": None,
        "long_description": None,
        "discord_link": "https://discord.gg/66rxWJGWzZ",
        "leaders": "Void Speaker: Toruuk Makto",
        "tag": None,
        "status": "active",
    },
    {
        "name": "Drommund Compact",
        "agreement_type": "Archive Agreement",
        "civ_type": None,
        "notes": None,
        "long_description": None,
        "discord_link": None,
        "leaders": None,
        "tag": None,
        "status": "active",
    },
    {
        "name": "Everion",
        "agreement_type": "Archive Agreement",
        "civ_type": None,
        "notes": "Per Lucca: Official allies.",
        "long_description": None,
        "discord_link": None,
        "leaders": None,
        "tag": None,
        "status": "active",
    },
    {
        "name": "The Galactic Hub Project",
        "agreement_type": "Archive Agreement",
        "civ_type": None,
        "notes": None,
        "long_description": None,
        "discord_link": None,
        "leaders": None,
        "tag": "GHub",
        "status": "active",
    },
    {
        "name": "Archduchy of Nicea",
        "agreement_type": "Partner",
        "civ_type": None,
        "notes": "Aggressive.",
        "long_description": None,
        "discord_link": None,
        "leaders": None,
        "tag": None,
        "status": "active",
    },
    {
        "name": "IEA",
        "agreement_type": "Chartered Partner, Archive Agreement",
        "civ_type": None,
        "notes": 'Bot for "bot-dev" role.',
        "long_description": (
            "🚀 **Who We Are:** The IEA is a community of like-minded individuals "
            "dedicated to the exploration of the cosmos. Whether you're an experienced "
            "spacefarer or a newcomer to the stars, everyone is welcome to join our "
            "ranks. Together, we embark on expeditions, conduct research, and unravel "
            "the mysteries of the universe.\n\n"
            "🔭 **What We Do:**\n"
            "**Exploration:** Journey to the far reaches of the universe and beyond, "
            "charting unexplored territories and discovering new celestial wonders.\n"
            "**Research:** Engage in scientific inquiry, studying the cosmos to deepen "
            "our understanding of its vastness and complexity.\n"
            "**Collaboration:** Foster collaboration and camaraderie among members, "
            "sharing knowledge and resources to further our collective exploration efforts."
        ),
        "discord_link": "https://discord.gg/kyhMHAAMcM",
        "leaders": None,
        "tag": "IEA",
        "status": "active",
    },
    {
        "name": "Indominus Legion",
        "agreement_type": "Archive Agreement, Envoy Expedition",
        "civ_type": None,
        "notes": "General partnership.",
        "long_description": None,
        "discord_link": None,
        "leaders": None,
        "tag": None,
        "status": "active",
    },
    {
        "name": "KOS/Dawnblade Kingdom",
        "agreement_type": "Partner",
        "civ_type": None,
        "notes": "General partnership, exploration agreement.",
        "long_description": None,
        "discord_link": None,
        "leaders": None,
        "tag": None,
        "status": "active",
    },
    {
        "name": "Neo Terra",
        "agreement_type": "Archive Agreement",
        "civ_type": None,
        "notes": "Potential building agreement.",
        "long_description": None,
        "discord_link": None,
        "leaders": None,
        "tag": None,
        "status": "active",
    },
    {
        "name": "Outskirt Queers",
        "agreement_type": "Archive Agreement",
        "civ_type": None,
        "notes": None,
        "long_description": None,
        "discord_link": None,
        "leaders": None,
        "tag": None,
        "status": "active",
    },
    {
        "name": "Pirate Kingdom/Dominion",
        "agreement_type": "Archive Agreement",
        "civ_type": None,
        "notes": "Per Lucca: have presence in haven, are at war with allies.",
        "long_description": None,
        "discord_link": None,
        "leaders": None,
        "tag": None,
        "status": "active",
    },
    {
        "name": "Prometheus Collective",
        "agreement_type": "Partner",
        "civ_type": None,
        "notes": "General partnership.",
        "long_description": None,
        "discord_link": None,
        "leaders": None,
        "tag": None,
        "status": "active",
    },
    {
        "name": "Quasar Republic Reforged",
        "agreement_type": "Chartered Partner",
        "civ_type": None,
        "notes": "General partnership.",
        "long_description": None,
        "discord_link": None,
        "leaders": None,
        "tag": None,
        "status": "active",
    },
    {
        "name": "Redwater Runners",
        "agreement_type": "Archive Agreement",
        "civ_type": None,
        "notes": "Aggressive.",
        "long_description": None,
        "discord_link": None,
        "leaders": None,
        "tag": None,
        "status": "active",
    },
    {
        "name": "Riders of Endless Skies",
        "agreement_type": "Partner",
        "civ_type": None,
        "notes": "Unknown.",
        "long_description": None,
        "discord_link": None,
        "leaders": None,
        "tag": None,
        "status": "active",
    },
    {
        "name": "Shattered Veil Egg Emporium",
        "agreement_type": "Partner",
        "civ_type": None,
        "notes": "General partnership.",
        "long_description": None,
        "discord_link": None,
        "leaders": None,
        "tag": None,
        "status": "active",
    },
    {
        "name": "The Archivists",
        "agreement_type": "Chartered Partner, Archive Agreement",
        "civ_type": None,
        "notes": None,
        "long_description": None,
        "discord_link": None,
        "leaders": None,
        "tag": None,
        "status": "active",
    },
    {
        "name": "The Brotherhood",
        "agreement_type": "Chartered Partner, Archive Agreement",
        "civ_type": None,
        "notes": "Partnership.",
        "long_description": None,
        "discord_link": None,
        "leaders": None,
        "tag": None,
        "status": "active",
    },
    {
        "name": "The Circle of Yggdrasil",
        "agreement_type": "Archive Agreement",
        "civ_type": None,
        "notes": None,
        "long_description": None,
        "discord_link": None,
        "leaders": None,
        "tag": None,
        "status": "active",
    },
    {
        "name": "The Golden Ledger",
        "agreement_type": "Chartered Partner, Archive Agreement",
        "civ_type": None,
        "notes": None,
        "long_description": None,
        "discord_link": None,
        "leaders": None,
        "tag": None,
        "status": "active",
    },
    {
        "name": "N//X",
        "agreement_type": "Archive Agreement",
        "civ_type": None,
        "notes": None,
        "long_description": None,
        "discord_link": None,
        "leaders": None,
        "tag": None,
        "status": "active",
    },
    {
        "name": "United Pirates and Adventurers of Euclid",
        "agreement_type": "Not joined (under discussion)",
        "civ_type": None,
        "notes": None,
        "long_description": None,
        "discord_link": None,
        "leaders": None,
        "tag": None,
        "status": "active",   # in the partner section of the sheet
    },
]


INTERCIV_FALLEN: list[dict] = [
    {
        "name": "Concord of Sovereign Powers",
        "agreement_type": "Former observer (INTERCIV)",
        "civ_type": "INTERCIV body",
        "notes": "Observer status, fallen.",
        "long_description": None,
        "discord_link": None, "leaders": None, "tag": None,
        "status": "archived",
    },
    {
        "name": "CoO",
        "agreement_type": "Former member (INTERCIV)",
        "civ_type": "INTERCIV body",
        "notes": "Former member, fallen.",
        "long_description": None,
        "discord_link": None, "leaders": None, "tag": None,
        "status": "archived",
    },
    {
        "name": "Covenant of Mutual Restraint",
        "agreement_type": "Former member (INTERCIV)",
        "civ_type": "INTERCIV body",
        "notes": "Former member, fallen.",
        "long_description": None,
        "discord_link": None, "leaders": None, "tag": None,
        "status": "archived",
    },
    {
        "name": "Pax Cosmica",
        "agreement_type": "Former member (INTERCIV)",
        "civ_type": "INTERCIV body",
        "notes": "Former member, fell 22/11/25.",
        "long_description": None,
        "discord_link": None, "leaders": None, "tag": None,
        "status": "archived",
    },
    {
        "name": "The Galactic Senate",
        "agreement_type": "Former member (INTERCIV)",
        "civ_type": "INTERCIV body",
        "notes": "Former member, fallen.",
        "long_description": None,
        "discord_link": None, "leaders": None, "tag": None,
        "status": "archived",
    },
    {
        "name": "The Interstellar Union of Nations",
        "agreement_type": "Former observer (INTERCIV)",
        "civ_type": "INTERCIV body",
        "notes": "Observer, fallen.",
        "long_description": None,
        "discord_link": None, "leaders": None, "tag": None,
        "status": "archived",
    },
    {
        "name": "The New Stellar Assembly",
        "agreement_type": "Former member (INTERCIV)",
        "civ_type": "INTERCIV body",
        "notes": "Former member, fallen.",
        "long_description": None,
        "discord_link": None, "leaders": None, "tag": None,
        "status": "archived",
    },
    {
        "name": "The Xi'an Project",
        "agreement_type": "Former observer (INTERCIV)",
        "civ_type": "INTERCIV body",
        "notes": "Former observer, fallen.",
        "long_description": None,
        "discord_link": None, "leaders": None, "tag": None,
        "status": "archived",
    },
    {
        "name": "URGS",
        "agreement_type": "Former member (INTERCIV)",
        "civ_type": "INTERCIV body",
        "notes": "Former member, fallen.",
        "long_description": None,
        "discord_link": None, "leaders": None, "tag": None,
        "status": "archived",
    },
    {
        "name": "UEGA",
        "agreement_type": "INTERCIV body",
        "civ_type": "INTERCIV body",
        "notes": "Listed in INTERCIV section.",
        "long_description": None,
        "discord_link": None, "leaders": None, "tag": None,
        "status": "archived",
    },
]


# =====================================================================
# RUNNER
# =====================================================================
def seed_partners(force: bool = False) -> None:
    if not force and os.environ.get("ARCHIVE_SEED_PARTNERS", "") != "1":
        log.info("seed_partners: ARCHIVE_SEED_PARTNERS!=1 — skipping. "
                 "Pass --force or set the env var to run.")
        return
    all_rows = ACTIVE_PARTNERS + INTERCIV_FALLEN
    log.info("seed_partners: %d rows to consider", len(all_rows))
    inserted = 0
    skipped = 0
    with session_scope() as s:
        for r in all_rows:
            slug = _slug(r["name"])
            existing = s.execute(
                text("SELECT 1 FROM civilization WHERE slug = :s"),
                {"s": slug},
            ).first()
            if existing:
                skipped += 1
                continue
            c1, c2 = _colors_for(slug)
            description = _build_description(
                agreement_type=r.get("agreement_type"),
                civ_type=r.get("civ_type"),
                notes=r.get("notes"),
                long_description=r.get("long_description"),
                discord_link=r.get("discord_link"),
                leaders=r.get("leaders"),
                tag=r.get("tag"),
            )
            tagline = r.get("civ_type") or r.get("agreement_type")
            s.execute(
                text(
                    "INSERT INTO civilization ("
                    "slug, name, status, galaxy, founded, founded_year,"
                    " ended, ended_year, tagline, description,"
                    " color_primary, color_secondary"
                    ") VALUES ("
                    ":slug, :name, :status, NULL, NULL, NULL,"
                    " NULL, NULL, :tagline, :description,"
                    " :c1, :c2"
                    ")"
                ),
                {
                    "slug": slug, "name": r["name"], "status": r["status"],
                    "tagline": tagline, "description": description,
                    "c1": c1, "c2": c2,
                },
            )
            inserted += 1
    log.info("seed_partners: inserted %d, skipped %d", inserted, skipped)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    seed_partners(force="--force" in sys.argv)
