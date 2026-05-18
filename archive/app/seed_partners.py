"""
Seed the FULL Voyager's Haven partner list as `civilization` rows.

Source: VH partner-tracking spreadsheet (Google Sheets, May 2026).
171 civilizations total across five spreadsheet sections:

  - ACTIVE_PARTNERS (28+1 self)  → status=active
  - FALLEN_CIVS         (15)     → status=archived
  - ARCHIVED_AGREEMENTS  (8)     → status=archived (1 exception → active)
  - INTERCIV           (10)     → status=archived
  - NOT_JOINED        (~109)    → status=dormant (most), few overrides

Rich-data civs (full dicts with leaders / discord / civ type / notes)
go in ACTIVE_PARTNERS. Everything else uses the compact
`(name, agreement_note)` tuple form for editability — the seed
function fills in the rest.

Run on the Pi:
    docker exec archive python -m app.seed_partners --force

Idempotent: skips slugs that already exist. To re-seed from scratch
(e.g., after a schema or data change), delete the existing rows first:
    docker exec archive python -c \\
        "import sqlite3; c=sqlite3.connect('/data/archive.db'); \\
         c.execute('DELETE FROM civilization'); c.commit()"
"""

from __future__ import annotations

import logging
import os
import re
import sys

from sqlalchemy import text

from .db import session_scope

log = logging.getLogger("archive.seed_partners")


PALETTE: list[tuple[str, str]] = [
    ("#042C53", "#0F6E56"),
    ("#4A1B0C", "#993C1D"),
    ("#26215C", "#534AB7"),
    ("#173404", "#639922"),
    ("#5C1F4D", "#993556"),
    ("#1F2D3A", "#4F7A9E"),
    ("#633806", "#C18C2D"),
    ("#3C1F4D", "#7D3F8C"),
    ("#0F4C5C", "#3E92B5"),
    ("#5C2B0F", "#C46A2D"),
    ("#1A3D1B", "#4A8F3C"),
    ("#3E2A56", "#7E5BAA"),
]


def _slug(name: str) -> str:
    s = name.lower().strip().rstrip("*").strip()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:64] or "unnamed"


def _colors_for(slug: str) -> tuple[str, str]:
    return PALETTE[sum(ord(c) for c in slug) % len(PALETTE)]


def _build_description(
    *,
    agreement_type: str | None = None,
    civ_type: str | None = None,
    notes: str | None = None,
    long_description: str | None = None,
    discord_link: str | None = None,
    leaders: str | None = None,
    tag: str | None = None,
) -> str | None:
    lines: list[str] = []
    if long_description:
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
    return "\n\n".join(lines) if lines else None


# =====================================================================
# SECTION 1 — ACTIVE PARTNERS (rich data, full dicts)
# =====================================================================
ACTIVE_PARTNERS: list[dict] = [
    {"name": "Voyager's Haven", "agreement_type": "Host", "civ_type": "Workshop community", "notes": "Operates the Travelers Archive (this site).", "leaders": "Founder: Ekimo", "tag": "VH"},
    {"name": "Aculon", "agreement_type": "Partner", "civ_type": "RP: Empire", "notes": "Verbal agreement.", "discord_link": "https://discord.gg/rhbt23sws9", "leaders": "Augustus"},
    {"name": "Alliance of Galactic Travelers", "agreement_type": "Archive Agreement", "notes": "Dismissive?", "discord_link": "https://discord.gg/vJpvKSRkQH", "tag": "AGT"},
    {"name": "Atlas-CSD/ETARC", "agreement_type": "Partners", "discord_link": "https://forums.atlas-65.com/", "tag": "ETARC"},
    {"name": "Aurelis Prime", "agreement_type": "Chartered Partner, Archive Agreement", "notes": "Partnership.", "leaders": "Staff: Lagz, SirDwayne, SirHobo"},
    {"name": "Black Edge Syndicate", "agreement_type": "Chartered Partner, Archive Agreement", "civ_type": "RP: Outlaw Syndicate", "discord_link": "https://discord.gg/7ZGtw5zuXq", "leaders": "Council: Unknown Regions, Lucca, Jaina Siderea, HandlesofGod", "tag": "BES"},
    {"name": "Canvas Town", "agreement_type": "Chartered Partner", "civ_type": "CM: Interciv gaming", "notes": "Interest.", "discord_link": "https://discord.gg/YkqWfdSEAq", "leaders": "Founders: Rasquel, WhrStrsG"},
    {"name": "Covenant of the Void", "agreement_type": "Partner", "discord_link": "https://discord.gg/66rxWJGWzZ", "leaders": "Void Speaker: Toruuk Makto"},
    {"name": "Drommund Compact", "agreement_type": "Archive Agreement"},
    {"name": "Everion", "agreement_type": "Archive Agreement", "notes": "Per Lucca: Official allies."},
    {"name": "The Galactic Hub Project", "agreement_type": "Archive Agreement", "tag": "GHub"},
    {"name": "Archduchy of Nicea", "agreement_type": "Partner", "notes": "Aggressive."},
    {"name": "IEA", "agreement_type": "Chartered Partner, Archive Agreement", "notes": 'Bot for "bot-dev" role.', "long_description": "🚀 **Who We Are:** The IEA is a community of like-minded individuals dedicated to the exploration of the cosmos. Whether you're an experienced spacefarer or a newcomer to the stars, everyone is welcome to join our ranks. Together, we embark on expeditions, conduct research, and unravel the mysteries of the universe.\n\n🔭 **What We Do:**\n**Exploration:** Journey to the far reaches of the universe and beyond, charting unexplored territories and discovering new celestial wonders.\n**Research:** Engage in scientific inquiry, studying the cosmos to deepen our understanding of its vastness and complexity.\n**Collaboration:** Foster collaboration and camaraderie among members, sharing knowledge and resources to further our collective exploration efforts.", "discord_link": "https://discord.gg/kyhMHAAMcM", "tag": "IEA"},
    {"name": "Indominus Legion", "agreement_type": "Archive Agreement, Envoy Expedition", "notes": "General partnership."},
    {"name": "KOS/Dawnblade Kingdom", "agreement_type": "Partner", "notes": "General partnership, exploration agreement."},
    {"name": "Neo Terra", "agreement_type": "Archive Agreement", "notes": "Potential building agreement."},
    {"name": "Outskirt Queers", "agreement_type": "Archive Agreement"},
    {"name": "Pirate Kingdom/Dominion", "agreement_type": "Archive Agreement", "notes": "Per Lucca: have presence in haven, are at war with allies."},
    {"name": "Prometheus Collective", "agreement_type": "Partner", "notes": "General partnership."},
    {"name": "Quasar Republic Reforged", "agreement_type": "Chartered Partner", "notes": "General partnership."},
    {"name": "Redwater Runners", "agreement_type": "Archive Agreement", "notes": "Aggressive."},
    {"name": "Riders of Endless Skies", "agreement_type": "Partner", "notes": "Unknown."},
    {"name": "Shattered Veil Egg Emporium", "agreement_type": "Partner", "notes": "General partnership."},
    {"name": "The Archivists", "agreement_type": "Chartered Partner, Archive Agreement"},
    {"name": "The Brotherhood", "agreement_type": "Chartered Partner, Archive Agreement", "notes": "Partnership."},
    {"name": "The Circle of Yggdrasil", "agreement_type": "Archive Agreement"},
    {"name": "The Golden Ledger", "agreement_type": "Chartered Partner, Archive Agreement"},
    {"name": "N//X", "agreement_type": "Archive Agreement"},
    {"name": "United Pirates and Adventurers of Euclid", "agreement_type": "Listed in partner section, not yet joined"},
    # Two from the not-joined section that are actually flagged active:
    {"name": "The Zabian Federation>Helghan empire", "agreement_type": "Partners"},
    {"name": "The Cloud Empire", "agreement_type": "Talks ongoing"},
    {"name": "Republic of Free Systems", "agreement_type": "Initiated (TikTok contact)"},
    {"name": "SurvivalBob", "agreement_type": "Initiated"},
    {"name": "The Galactic Hunt", "agreement_type": "Talks ongoing"},
    # One exception from archived-agreements section flagged active:
    {"name": "The Crimson Runners", "agreement_type": "Chartered Partner, Archive Agreement"},
]


# =====================================================================
# SECTION 2 — FALLEN CIVS + ARCHIVED AGREEMENTS + INTERCIV + The Nine
# All status=archived
# Tuple form: (name, agreement_note)
# =====================================================================
ARCHIVED_CIVS: list[tuple[str, str]] = [
    # "Fallen civs" section
    ("The Singularity", "Fallen — DMs only, dead"),
    ("Arcadia", "Dead"),
    ("Canvas Town Arena", "Fallen (no data)"),
    ("EDGE of EXTINCTION", "Fallen"),
    ("IHP", "Fallen"),
    ("Kaer Morhen", "Fallen"),
    ("No Man's Taverns", "Fallen"),
    ("Quantum Legion", "Fallen"),
    ("The Crimson Imperium", "Fallen"),
    ("The Imperial order of Union", "Fallen"),
    ("The Sovereign Star Union", "Fallen"),
    ("Travellers Haven>Cyper Oasis", "Fallen"),
    ("Veyrith", "Fallen"),
    ("White Noise", "Fallen"),
    ("Wild Space", "Fallen"),
    # "Archived agreements" section
    ("Ipomoea Empire", "Fallen — 2 archived agreements"),
    ("Jerra Prime", "Fallen — 1 archived agreement, prior partnership"),
    ("Nexus Republic", "Fallen — former partner"),
    ("The Republic of Meliora", "Fallen — 1 archived agreement"),
    ("Interstellar Drifters", "Fallen — former partner"),
    ("Gek Empire Reforged", "Fallen — 1 archived agreement"),
    ("The Void Citadel", "Fallen — 2 archived agreements, general partnership"),
    # INTERCIV (formal multi-civ body memberships, all dissolved)
    ("Concord of Sovereign Powers", "INTERCIV — former observer, fallen"),
    ("CoO", "INTERCIV — former member, fallen"),
    ("Covenant of Mutual Restraint", "INTERCIV — former member, fallen"),
    ("Pax Cosmica", "INTERCIV — former member, fell 22/11/25"),
    ("The Galactic Senate", "INTERCIV — former member, fallen"),
    ("The Interstellar Union of Nations", "INTERCIV — former observer, fallen"),
    ("The New Stellar Assembly", "INTERCIV — former member, fallen"),
    ("The Xi'an Project", "INTERCIV — former observer, fallen"),
    ("URGS", "INTERCIV — former member, fallen"),
    ("UEGA", "INTERCIV body (listed without further details)"),
    # The Nine — listed in the not-joined section but marked Fallen
    ("The Nine", "Fallen"),
]


# =====================================================================
# SECTION 3 — NOT JOINED / NOT INITIATED / NEUTRAL / NO RESPONSE
# All status=dormant
# Tuple form: (name, agreement_note)
# =====================================================================
DORMANT_CIVS: list[tuple[str, str]] = [
    ("¥GTTG¥", "Not initiated"),
    ("Albion Dominion", "Not joined"),
    ("Aldaran Galactic Federation", "Not joined"),
    ("Archion Armada", "Not initiated"),
    ("Ark Haven", "Not joined"),
    ("Atheria", "Not joined"),
    ("BGP Galactic Hub", "Not joined"),
    ("Black Skies Mercenaries", "Not initiated"),
    ("Celesta Prime", "Listed without details"),
    ("Commune of the Stars", "Not joined"),
    ("Custodes Nemesiea", "Not initiated"),
    ("Dread Force", "Not initiated"),
    ("Eisvana", "No response — unknown"),
    ("Elysium Grand Temple", "Not initiated"),
    ("Empire of Anomalies", "Declined (no)"),
    ("Federal oligarchist Republic", "Not initiated"),
    ("Gek-Zuma Empire", "Not joined"),
    ("Halavana Conclave", "Not joined"),
    ("Hitchhikers of No Man's Sky", "Not joined"),
    ("HOUSE ATREIDES", "Not initiated"),
    ("Hyperion Syndicate", "Not joined"),
    ("Intergalactic Federation of No Man's Sky", "Not joined"),
    ("Intergalactic Mexican Empire", "Not joined"),
    ("Khelaris Prime-Hyperion Syndicate", "Not initiated"),
    ("Kosforr Travelers Guild", "Not initiated"),
    ("Militaires Sans Frontieres (MSF)", "Not initiated"),
    ("MOAPS (Manifesto of Pure Soul)", "Not joined"),
    ("Morley Celestial Bureau", "Not joined"),
    ("New Avalon", "Not initiated"),
    ("New IKE order", "Not joined"),
    ("No Man's High", "Not joined"),
    ("No Man's Militia", "Not joined"),
    ("No Man's Sky creative and sharing Hub", "Not initiated"),
    ("No Man's Sky Hub", "Not joined"),
    ("Nuvanti Prime", "Not joined"),
    ("N-Y-X Orbital Corporation", "Not initiated"),
    ("Old Fortuna", "Not initiated"),
    ("PanGalactic StarCabs", "Not initiated"),
    ("Pirates of No Man's Sky", "Not joined"),
    ("Republic of Harlev", "Not joined"),
    ("Republic of intergalactic Travellers", "Not initiated"),
    ("Requiem Explorer's League", "Not initiated"),
    ("Scientia Aureus", "Not joined"),
    ("Sentaurus Empire", "Not joined"),
    ("Skies of Utopia", "Not initiated"),
    ("Stellar Reaper imperium", "Not initiated"),
    ("Stellar Towel Society", "Not joined"),
    ("The Alpha Sector", "Not joined"),
    ("Solara", "Status unclear — ask Lucca"),
    ("The Arcadian Index", "Not joined"),
    ("The Collective", "Not initiated"),
    ("The Crimson Empire", "Not initiated"),
    ("The Euclid Archive", "Not joined"),
    ("The First Order", "Not joined"),
    ("The Galactic Federation", "Not joined"),
    ("The Galaktik empire", "Not initiated"),
    ("The Galactic Tea rooms", "Not joined"),
    ("The Galactic Trade Federation", "Not initiated"),
    ("The Genesis of Galactica", "Not joined"),
    ("The Grand Lake Voyagers", "Not joined"),
    ("The Grand Imperium", "Not initiated"),
    ("The Holy Empire", "Not initiated"),
    ("The Initiative", "Not initiated"),
    ("The Ironclad Ledger", "Not interested"),
    ("The Muha Society", "Not initiated"),
    ("The Phoenix Republic", "Not joined"),
    ("The Pilgrim Society", "Not joined"),
    ("The Pirate Republic of Larcenix", "Not joined"),
    ("The Real Atlas Cult", "Not initiated"),
    ("The Vortex Protection Federation (VPF)", "Not joined"),
    ("The World of Glass", "Not joined"),
    ("Vanguard of the Cosmos", "Not joined"),
    ("Ventarian Republic", "Not joined"),
    ("Chimera Core", "Listed without details"),
    ("Civ Hub NexGen", "Listed without details"),
    ("Dear Mister Dubs Community", "Listed without details"),
    ("GerMans Sky", "Listed without details"),
    ("NMS: Construction Contractors", "Listed without details"),
    ("No Man's Sky Retro", "Listed without details"),
    ("No One's Sky", "Listed without details"),
    ("PanGalactic Builders Federation", "Listed without details"),
    ("Procedural Lounge", "Listed without details"),
    ("SilverIndustries", "Listed without details"),
    ("Skies of Radiance", "Non-partner — unknown"),
    ("Sovereign Systems Compact", "Listed without details"),
    ("Star Wars Galactic Project", "Neutral"),
    ("TetraCobalt Trading Company", "Listed without details"),
    ("The Mayhedo Community", "No response"),
    ("The Onyx Imperium", "Not initiated"),
    ("The Rose Garden Republic", "Not initiated"),
    ("The Star Squadron", "Not initiated"),
    ("The Union of free systems", "Listed without details"),
    ("The Xparsian Legion", "Listed without details"),
    ("The XZSERON Construct", "Listed without details"),
    ("United Corporate Alliance", "Listed without details"),
    ("United Republic of the Shnail", "Not initiated"),
    ("Valdis Oversector", "Listed without details"),
    ("Vel'Kora Empire", "Listed without details"),
    ("Valtheria", "Listed without details"),
    ("Vanguard Order", "Listed without details"),
    ("Veltrax Regime", "Not initiated"),
    ("Veritas", "Non-partner — disinterest"),
    ("Viltrum empire", "Discord channel link only"),
    ("Voidborne sovereignty", "Listed without details"),
]


# =====================================================================
# RUNNER
# =====================================================================
def _insert_civ(s, name: str, status: str, agreement_note: str, extras: dict | None = None) -> bool:
    """Insert one civ if not already present. Returns True if inserted."""
    slug = _slug(name)
    existing = s.execute(
        text("SELECT 1 FROM civilization WHERE slug = :s"),
        {"s": slug},
    ).first()
    if existing:
        return False
    c1, c2 = _colors_for(slug)
    extras = extras or {}
    description = _build_description(
        agreement_type=extras.get("agreement_type") or agreement_note,
        civ_type=extras.get("civ_type"),
        notes=extras.get("notes"),
        long_description=extras.get("long_description"),
        discord_link=extras.get("discord_link"),
        leaders=extras.get("leaders"),
        tag=extras.get("tag"),
    )
    tagline = extras.get("civ_type") or (extras.get("agreement_type") or agreement_note)
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
            "slug": slug, "name": name, "status": status,
            "tagline": tagline, "description": description,
            "c1": c1, "c2": c2,
        },
    )
    return True


def seed_partners(force: bool = False) -> None:
    if not force and os.environ.get("ARCHIVE_SEED_PARTNERS", "") != "1":
        log.info("seed_partners: ARCHIVE_SEED_PARTNERS!=1 — skipping. Pass --force to run.")
        return
    total = len(ACTIVE_PARTNERS) + len(ARCHIVED_CIVS) + len(DORMANT_CIVS)
    log.info("seed_partners: %d total rows to consider (%d active, %d archived, %d dormant)",
             total, len(ACTIVE_PARTNERS), len(ARCHIVED_CIVS), len(DORMANT_CIVS))
    inserted = 0
    skipped = 0
    with session_scope() as s:
        for r in ACTIVE_PARTNERS:
            extras = {k: v for k, v in r.items() if k != "name"}
            agreement = extras.pop("agreement_type", "Listed in active section")
            if _insert_civ(s, r["name"], "active", agreement, {"agreement_type": agreement, **extras}):
                inserted += 1
            else:
                skipped += 1
        for name, note in ARCHIVED_CIVS:
            if _insert_civ(s, name, "archived", note):
                inserted += 1
            else:
                skipped += 1
        for name, note in DORMANT_CIVS:
            if _insert_civ(s, name, "dormant", note):
                inserted += 1
            else:
                skipped += 1
    log.info("seed_partners: inserted %d, skipped %d (already existed)", inserted, skipped)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    seed_partners(force="--force" in sys.argv)
