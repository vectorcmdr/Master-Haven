"""
Pydantic v2 schemas for API responses.

One consolidated file covering every resource. Split into per-resource
files if/when this gets unwieldy (probably Phase 4 when writes are
added and request schemas appear).

Conventions:
- Every list endpoint returns Envelope[list[T]] with meta carrying
  pagination + count
- Every detail endpoint returns Envelope[T] with empty meta
- Summary models are card-shaped (no body); Detail models include body
- Field names match what the v0.9 mockup's frontend expects so the
  Phase 5 rebuild has no impedance mismatch
"""

from __future__ import annotations

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------
# Envelope
# ---------------------------------------------------------------------
T = TypeVar("T")


class Meta(BaseModel):
    # Pagination fields are present on list responses, absent on detail.
    page: Optional[int] = None
    page_size: Optional[int] = None
    total: Optional[int] = None
    # Free-form extras (filter echo, search query, etc.)
    extra: Optional[dict[str, Any]] = None


class Envelope(BaseModel, Generic[T]):
    data: T
    meta: Meta = Field(default_factory=Meta)


# ---------------------------------------------------------------------
# Author / byline (compact user fragment shown on stories, inquisitions)
# ---------------------------------------------------------------------
class Author(BaseModel):
    id: int
    slug: str                              # the user's discord_username, used in URL
    name: str                              # display_name
    avatar_letter: Optional[str] = None
    avatar_color: Optional[str] = None
    role: Optional[str] = None             # base_role: reader/diplomat/historian


# ---------------------------------------------------------------------
# Civilizations
# ---------------------------------------------------------------------
class CivStats(BaseModel):
    entries: int = 0                       # stories + inquisitions
    inquisitions: int = 0
    people: int = 0
    years: int = 0


class CivilizationSummary(BaseModel):
    slug: str
    name: str
    status: str                            # active / dormant / archived
    galaxy: Optional[str] = None
    founded: Optional[str] = None
    ended: Optional[str] = None
    tagline: Optional[str] = None
    color_primary: str
    color_secondary: str
    stats: CivStats


class CivilizationDetail(CivilizationSummary):
    description: Optional[str] = None
    founded_year: Optional[int] = None
    ended_year: Optional[int] = None


# Coverage = combined stories + inquisitions list for one civ
class CoverageItem(BaseModel):
    # 'story' or 'inquisition' so the frontend can route to the right page
    kind: str
    id: int
    slug: Optional[str] = None
    doctype: Optional[str] = None          # brief / feature / inquisition
    headline: str                          # title for inquisitions, headline for stories
    deck: Optional[str] = None
    beat: Optional[str] = None
    published_at: Optional[str] = None     # for stories
    started_at: Optional[str] = None       # for inquisitions
    numeral: Optional[str] = None          # for inquisitions
    state: Optional[str] = None            # for inquisitions
    author: Optional[Author] = None        # primary author


# ---------------------------------------------------------------------
# People
# ---------------------------------------------------------------------
class PersonDetail(BaseModel):
    slug: str
    name: str
    discord_username: Optional[str] = None
    civ_slug: Optional[str] = None
    role_in_civ: Optional[str] = None
    bio: Optional[str] = None


# ---------------------------------------------------------------------
# Events (historical events, not the archive_user kind)
# ---------------------------------------------------------------------
class EventDetail(BaseModel):
    slug: str
    title: str
    event_date: Optional[str] = None
    event_year: Optional[int] = None
    description: Optional[str] = None


# ---------------------------------------------------------------------
# Places
# ---------------------------------------------------------------------
class PlaceDetail(BaseModel):
    slug: str
    name: str
    galaxy: Optional[str] = None
    region: Optional[str] = None
    coordinates: Optional[str] = None
    description: Optional[str] = None


# ---------------------------------------------------------------------
# Stories
# ---------------------------------------------------------------------
class StorySummary(BaseModel):
    id: int
    slug: str
    doctype: str                           # brief / feature
    headline: str
    deck: Optional[str] = None
    beat: Optional[str] = None
    civs: list[str] = Field(default_factory=list)   # civ slugs
    author: Author
    published_at: str
    read_minutes: Optional[int] = None


class StoryDetail(StorySummary):
    body: str


# ---------------------------------------------------------------------
# Inquisitions
# ---------------------------------------------------------------------
class InquisitionSummary(BaseModel):
    id: int
    slug: str
    numeral: str
    title: str
    subtitle: Optional[str] = None
    deck: Optional[str] = None
    state: str                             # in_progress / closed / archived
    progress: int
    sources_count: int
    started_at: str
    closed_at: Optional[str] = None
    authors: list[Author] = Field(default_factory=list)
    civs: list[str] = Field(default_factory=list)


class InquisitionDetail(InquisitionSummary):
    body: str


# ---------------------------------------------------------------------
# Timeline (mixed stream)
# ---------------------------------------------------------------------
class TimelineEntry(BaseModel):
    # 'event' (historical event), 'story' (publication date), 'inquisition' (start)
    kind: str
    date: str                              # ISO date or year-only display string
    year: Optional[int] = None
    title: str
    slug: Optional[str] = None
    id: Optional[int] = None
    doctype: Optional[str] = None
    civs: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------
class SearchHit(BaseModel):
    # 'story' / 'inquisition' / 'civilization' / 'person'
    kind: str
    id: int
    slug: str
    title: str                             # headline / title / name
    snippet: Optional[str] = None          # ~120 chars of context
