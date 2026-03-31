---
phase: 01-foundation
plan: B
type: execute
wave: 1
depends_on: []
files_modified:
  - models/__init__.py
  - models/odds.py
  - models/signals.py
  - models/parlay.py
  - services/__init__.py
  - services/odds_normalizer.py
  - services/arb_detector.py
  - services/parlay_engine.py
  - adapters/__init__.py
  - adapters/base.py
  - adapters/odds_api.py
  - utils/odds_math.py
  - utils/formatters.py
autonomous: true
requirements: [BOT-05, BOT-06, BOT-07, DB-04, DEL-04, DEL-05]

must_haves:
  truths:
    - "All Pydantic v2 model classes are importable and validate their fields on instantiation"
    - "adapters/base.py defines an abstract interface that odds_api.py implements"
    - "All stub files are syntactically valid Python with correct type hints and docstrings explaining future purpose"
    - "Every function in every file has full return type annotations"
    - "EMBED_COLOR is importable from config.py and referenced by utils/formatters.py"
  artifacts:
    - path: "models/odds.py"
      provides: "OddsSnapshot, NormalizedOdds, Market dataclasses/models"
      exports: ["OddsSnapshot", "NormalizedOdds", "Market"]
    - path: "models/signals.py"
      provides: "ArbSignal, EVSignal dataclasses"
      exports: ["ArbSignal", "EVSignal"]
    - path: "models/parlay.py"
      provides: "Parlay, ParlayLeg dataclasses"
      exports: ["Parlay", "ParlayLeg"]
    - path: "adapters/base.py"
      provides: "Abstract SportsbookAdapter interface"
      exports: ["SportsbookAdapter"]
    - path: "adapters/odds_api.py"
      provides: "OddsApiAdapter stub implementing SportsbookAdapter"
      exports: ["OddsApiAdapter"]
    - path: "utils/odds_math.py"
      provides: "Stubs for odds math helpers"
      exports: ["american_to_decimal", "decimal_to_american", "implied_probability", "no_vig_probability"]
    - path: "utils/formatters.py"
      provides: "Stubs for Discord embed builders"
      exports: ["build_arb_embed", "build_ev_embed", "build_parlay_embed"]
  key_links:
    - from: "adapters/odds_api.py"
      to: "adapters/base.py"
      via: "class OddsApiAdapter(SportsbookAdapter)"
      pattern: "class OddsApiAdapter\\(SportsbookAdapter\\)"
    - from: "utils/formatters.py"
      to: "config.py"
      via: "from config import EMBED_COLOR"
      pattern: "from config import EMBED_COLOR"
    - from: "services/arb_detector.py"
      to: "models/signals.py"
      via: "from models.signals import ArbSignal"
      pattern: "from models.signals import"
---

<objective>
Create all Pydantic v2 data models, abstract adapter interface, service stubs, and utility stubs that Phase 3 and Phase 4 will implement in full. All files must be syntactically valid, fully type-hinted, and importable.

Purpose: These files define the data contracts that all future cogs depend on. Creating them as stubs in Phase 1 ensures imports work immediately and Phase 2/3/4 executors have clear contracts.
Output: 13 Python files providing the complete model and stub layer.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/phases/01-foundation/01-CONTEXT.md
@.planning/phases/01-foundation/01-RESEARCH.md

<interfaces>
<!-- Contracts defined in Plan A that this plan builds on -->

From config.py (created in Plan A):
  EMBED_COLOR: int = 0x2E7D32   # import with: from config import EMBED_COLOR

From REQUIREMENTS.md ARB-06 (normalized odds schema — models must match exactly):
  NormalizedOdds fields: sport, league, event_name, home_team, away_team, start_time,
                         market_type, selection_name, line_value, decimal_odds,
                         american_odds, book_name, fetched_at, event_id, market_key

From REQUIREMENTS.md ARB-07 (key generation):
  event_id: "{home_team}_{away_team}_{date}"
  market_key: "{event_id}_{market_type}_{selection_name}"

From REQUIREMENTS.md ARB-01 (adapter interface methods):
  get_sports() -> list[dict]
  get_events(sport_key: str) -> list[dict]
  get_odds(sport_key: str, regions: list[str], markets: list[str]) -> list[dict]
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Pydantic v2 data models — odds.py, signals.py, parlay.py</name>
  <files>models/__init__.py, models/odds.py, models/signals.py, models/parlay.py</files>
  <read_first>
    - /Users/ringochui/Projects/chewyBot/.planning/REQUIREMENTS.md (ARB-06, ARB-07, ARB-08, ARB-10, PAR-03, PAR-05)
    - /Users/ringochui/Projects/chewyBot/.planning/phases/01-foundation/01-RESEARCH.md (Standard Stack: Pydantic v2)
  </read_first>
  <action>
Create models/__init__.py (empty) and three model files. All models use pydantic v2 BaseModel (not dataclasses). Full type hints on every field and method.

--- models/odds.py ---

```python
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Market(BaseModel):
    """A single betting market outcome from one sportsbook."""
    market_type: str
    selection_name: str
    line_value: Optional[float] = None
    decimal_odds: float
    american_odds: int
    book_name: str


class OddsSnapshot(BaseModel):
    """Raw odds data from a sportsbook API response before normalization."""
    event_id: str
    sport: str
    home_team: str
    away_team: str
    commence_time: datetime
    markets: list[Market]
    book_name: str
    fetched_at: datetime = Field(default_factory=datetime.utcnow)


class NormalizedOdds(BaseModel):
    """Canonical odds representation used throughout the scanning pipeline.

    event_id format: "{home_team}_{away_team}_{date}"  (ARB-07)
    market_key format: "{event_id}_{market_type}_{selection_name}"  (ARB-07)
    """
    event_id: str
    market_key: str
    sport: str
    league: str
    event_name: str
    home_team: str
    away_team: str
    start_time: datetime
    market_type: str
    selection_name: str
    line_value: Optional[float] = None
    decimal_odds: float
    american_odds: int
    book_name: str
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
```

--- models/signals.py ---

```python
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field


class ArbSignal(BaseModel):
    """Detected arbitrage opportunity between two sportsbooks.

    arb_pct: percentage return if both sides staked proportionally
    stake_side_a/b: recommended stake amounts given a bankroll
    """
    market_key: str
    event_name: str
    sport: str
    market_type: str
    arb_pct: float
    stake_side_a: float
    stake_side_b: float
    estimated_profit: float
    book_a: str
    book_b: str
    odds_a: float
    odds_b: float
    selection_a: str
    selection_b: str
    detected_at: datetime = Field(default_factory=datetime.utcnow)


class EVSignal(BaseModel):
    """Detected +EV (positive expected value) opportunity.

    ev_pct: expected value percentage above fair probability
    fair_probability: no-vig consensus probability of the outcome
    """
    market_key: str
    event_name: str
    sport: str
    market_type: str
    selection_name: str
    book_name: str
    decimal_odds: float
    fair_probability: float
    ev_pct: float
    detected_at: datetime = Field(default_factory=datetime.utcnow)
```

--- models/parlay.py ---

```python
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ParlayLeg(BaseModel):
    """A single leg within a parlay bet.

    leg_score: composite 0.0–1.0 score from 5-factor weighting (PAR-03)
    leg_type: category used for weight tracking (e.g. 'spread', 'moneyline', 'over_under')
    """
    team: str
    market_type: str
    line_value: Optional[float] = None
    american_odds: int
    leg_score: float
    leg_type: str
    outcome: str = "pending"  # "pending" | "hit" | "miss"


class Parlay(BaseModel):
    """A generated NBA parlay with 3–5 legs.

    confidence_score: 0–100 composite confidence from leg scores
    discord_message_id: set after posting to Discord for reaction tracking
    """
    legs: list[ParlayLeg]
    combined_odds: float
    confidence_score: float
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    outcome: str = "pending"  # "pending" | "hit" | "miss"
    discord_message_id: Optional[str] = None
```

All four files (including __init__.py) must have no syntax errors.
  </action>
  <verify>
    <automated>cd /Users/ringochui/Projects/chewyBot && python -c "import ast; [ast.parse(open(f).read()) for f in ['models/odds.py','models/signals.py','models/parlay.py']]; print('syntax ok')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "class NormalizedOdds" models/odds.py` returns 1
    - `grep -c "class OddsSnapshot" models/odds.py` returns 1
    - `grep -c "class Market" models/odds.py` returns 1
    - `grep -c "market_key" models/odds.py` returns at least 1 (market_key field on NormalizedOdds)
    - `grep -c "class ArbSignal\|class EVSignal" models/signals.py` returns 2
    - `grep -c "class ParlayLeg\|class Parlay" models/parlay.py` returns 2
    - `grep -c "BaseModel" models/odds.py models/signals.py models/parlay.py` returns at least 5 (all models extend BaseModel)
    - `python -c "import ast; ast.parse(open('models/odds.py').read()); print('ok')"` prints "ok"
    - `python -c "import ast; ast.parse(open('models/signals.py').read()); print('ok')"` prints "ok"
    - `python -c "import ast; ast.parse(open('models/parlay.py').read()); print('ok')"` prints "ok"
    - `test -f models/__init__.py` exits 0
  </acceptance_criteria>
  <done>models/__init__.py (empty), models/odds.py (OddsSnapshot, NormalizedOdds, Market), models/signals.py (ArbSignal, EVSignal), models/parlay.py (Parlay, ParlayLeg) — all pydantic v2 BaseModel, full type hints, no syntax errors.</done>
</task>

<task type="auto">
  <name>Task 2: Adapter interface + service stubs + utility stubs</name>
  <files>
    adapters/__init__.py, adapters/base.py, adapters/odds_api.py,
    services/__init__.py, services/odds_normalizer.py, services/arb_detector.py, services/parlay_engine.py,
    utils/odds_math.py, utils/formatters.py
  </files>
  <read_first>
    - /Users/ringochui/Projects/chewyBot/.planning/REQUIREMENTS.md (ARB-01, ARB-02, ARB-06, ARB-07, ARB-08, ARB-10, ARB-11, BOT-07)
    - /Users/ringochui/Projects/chewyBot/.planning/phases/01-foundation/01-CONTEXT.md (phase boundary note — stubs only)
  </read_first>
  <action>
Create all 9 remaining files. All are stubs: correct interface, full type hints, docstrings, `raise NotImplementedError` bodies. No functional implementation yet (that's Phase 3).

--- adapters/__init__.py --- (empty)

--- adapters/base.py ---

```python
from __future__ import annotations
from abc import ABC, abstractmethod


class SportsbookAdapter(ABC):
    """Abstract interface for sportsbook API adapters.

    Concrete implementations (e.g. OddsApiAdapter) must implement all three methods.
    This interface allows swapping sportsbook providers without touching scanner logic.
    """

    @abstractmethod
    async def get_sports(self) -> list[dict]:
        """Return list of available sports dicts from the sportsbook API."""
        ...

    @abstractmethod
    async def get_events(self, sport_key: str) -> list[dict]:
        """Return list of event dicts for a given sport_key."""
        ...

    @abstractmethod
    async def get_odds(
        self,
        sport_key: str,
        regions: list[str],
        markets: list[str],
    ) -> list[dict]:
        """Return list of odds dicts for the given sport, regions, and market types."""
        ...
```

--- adapters/odds_api.py ---

```python
from __future__ import annotations
import httpx
from adapters.base import SportsbookAdapter


class OddsApiAdapter(SportsbookAdapter):
    """The Odds API adapter. Implements SportsbookAdapter using https://the-odds-api.com

    Phase 3 implements full fetch logic with MOCK_MODE support, exponential backoff,
    and quota tracking from response headers (ARB-02, ARB-04, ARB-05, BOT-07).

    Books covered: fanduel, draftkings, betmgm, bet365 (ARB-03)
    """

    BASE_URL: str = "https://api.the-odds-api.com/v4"
    SUPPORTED_BOOKS: list[str] = ["fanduel", "draftkings", "betmgm", "bet365"]

    def __init__(self, api_key: str, mock_mode: bool = False) -> None:
        self.api_key = api_key
        self.mock_mode = mock_mode
        self._quota_remaining: int | None = None

    async def get_sports(self) -> list[dict]:
        """Fetch available sports. Phase 3 implementation."""
        raise NotImplementedError("OddsApiAdapter.get_sports() — implement in Phase 3")

    async def get_events(self, sport_key: str) -> list[dict]:
        """Fetch events for a sport. Phase 3 implementation."""
        raise NotImplementedError("OddsApiAdapter.get_events() — implement in Phase 3")

    async def get_odds(
        self,
        sport_key: str,
        regions: list[str],
        markets: list[str],
    ) -> list[dict]:
        """Fetch odds for a sport. Phase 3 implementation."""
        raise NotImplementedError("OddsApiAdapter.get_odds() — implement in Phase 3")

    def get_quota_remaining(self) -> int | None:
        """Return last known API quota remaining from response headers."""
        return self._quota_remaining
```

--- services/__init__.py --- (empty)

--- services/odds_normalizer.py ---

```python
from __future__ import annotations
from models.odds import OddsSnapshot, NormalizedOdds


async def normalize(snapshot: OddsSnapshot) -> list[NormalizedOdds]:
    """Normalize a raw OddsSnapshot into canonical NormalizedOdds records.

    Implements ARB-06 canonical schema and ARB-07 key generation:
      event_id: "{home_team}_{away_team}_{date}"
      market_key: "{event_id}_{market_type}_{selection_name}"

    Phase 3 full implementation.
    """
    raise NotImplementedError("odds_normalizer.normalize() — implement in Phase 3")
```

--- services/arb_detector.py ---

```python
from __future__ import annotations
from models.odds import NormalizedOdds
from models.signals import ArbSignal, EVSignal


async def detect_arb(
    normalized: list[NormalizedOdds],
    min_arb_pct: float,
    bankroll: float,
) -> list[ArbSignal]:
    """Detect arbitrage opportunities across sportsbooks.

    ARB-08: sum(1/best_odds) < 1.0 indicates arb exists.
    ARB-09: filters by min_arb_pct threshold, deduplicates by market_key.
    Phase 3 full implementation.
    """
    raise NotImplementedError("arb_detector.detect_arb() — implement in Phase 3")


async def detect_ev(
    normalized: list[NormalizedOdds],
    min_ev_pct: float,
) -> list[EVSignal]:
    """Detect +EV opportunities using no-vig consensus probability.

    ARB-10: ev_pct = ((offered_decimal * fair_prob) - 1) * 100
    Phase 3 full implementation.
    """
    raise NotImplementedError("arb_detector.detect_ev() — implement in Phase 3")
```

--- services/parlay_engine.py ---

```python
from __future__ import annotations
from models.parlay import Parlay


async def generate_parlay(
    min_leg_score: float,
    leg_count_range: tuple[int, int] = (3, 5),
) -> Parlay:
    """Generate a 3–5 leg NBA parlay using 5-factor weighted scoring.

    PAR-03 factors: recent_form (0.25), home_away_split (0.20),
                    rest_days (0.15), line_value (0.25), historical_hit_rate (0.15)
    PAR-04: Never includes both sides of same game; min leg_score >= min_leg_score.
    Phase 4 full implementation.
    """
    raise NotImplementedError("parlay_engine.generate_parlay() — implement in Phase 4")
```

--- utils/odds_math.py ---

```python
from __future__ import annotations


def american_to_decimal(american_odds: int) -> float:
    """Convert American odds to decimal odds.

    Examples: +150 -> 2.5, -110 -> 1.909
    Phase 3 full implementation (ARB-11).
    """
    raise NotImplementedError("american_to_decimal() — implement in Phase 3")


def decimal_to_american(decimal_odds: float) -> int:
    """Convert decimal odds to American odds.

    Examples: 2.5 -> +150, 1.909 -> -110
    Phase 3 full implementation (ARB-11).
    """
    raise NotImplementedError("decimal_to_american() — implement in Phase 3")


def implied_probability(decimal_odds: float) -> float:
    """Return implied probability from decimal odds.

    Formula: 1 / decimal_odds
    Phase 3 full implementation (ARB-11).
    """
    raise NotImplementedError("implied_probability() — implement in Phase 3")


def no_vig_probability(odds_list: list[float]) -> list[float]:
    """Remove vig from a list of decimal odds and return fair probabilities.

    Used by +EV detector (ARB-10) to establish consensus fair line.
    Phase 3 full implementation (ARB-11).
    """
    raise NotImplementedError("no_vig_probability() — implement in Phase 3")
```

--- utils/formatters.py ---

```python
from __future__ import annotations
import discord
from config import EMBED_COLOR
from models.signals import ArbSignal, EVSignal
from models.parlay import Parlay


def build_arb_embed(signal: ArbSignal) -> discord.Embed:
    """Build a Discord embed for an arbitrage alert.

    ARB-20: title "⚡ Possible Arbitrage — chewyBot"
    Fields: sport, event, market, both sides, arb%, stake, profit
    Footer: disclaimer using "possible" / "estimated" language (ARB-22)
    Uses EMBED_COLOR = 0x2E7D32 (BOT-05)
    Phase 3 full implementation.
    """
    raise NotImplementedError("build_arb_embed() — implement in Phase 3")


def build_ev_embed(signal: EVSignal) -> discord.Embed:
    """Build a Discord embed for a +EV opportunity alert.

    ARB-21: title "📈 +EV Opportunity — chewyBot"
    Fields: sport, event, market, book, odds, fair probability, EV%
    Footer: disclaimer using "possible" / "estimated" language (ARB-22)
    Uses EMBED_COLOR = 0x2E7D32 (BOT-05)
    Phase 3 full implementation.
    """
    raise NotImplementedError("build_ev_embed() — implement in Phase 3")


def build_parlay_embed(parlay: Parlay, post_date: str) -> discord.Embed:
    """Build a Discord embed for a daily NBA parlay post.

    PAR-10: title "🏀 chewyBot's NBA Parlay — [date]"
    Fields: each leg (team, market type, line, American odds), combined odds, confidence score
    Uses EMBED_COLOR = 0x2E7D32 (BOT-05)
    Phase 4 full implementation.
    """
    raise NotImplementedError("build_parlay_embed() — implement in Phase 4")
```

All 9 files (including __init__.py files) must have no syntax errors.
  </action>
  <verify>
    <automated>cd /Users/ringochui/Projects/chewyBot && python -c "import ast; files=['adapters/base.py','adapters/odds_api.py','services/odds_normalizer.py','services/arb_detector.py','services/parlay_engine.py','utils/odds_math.py','utils/formatters.py']; [ast.parse(open(f).read()) for f in files]; print('all syntax ok')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "class SportsbookAdapter" adapters/base.py` returns 1
    - `grep -c "ABC\|abstractmethod" adapters/base.py` returns at least 2 (abstract base class used)
    - `grep -c "class OddsApiAdapter(SportsbookAdapter)" adapters/odds_api.py` returns 1 (correct inheritance)
    - `grep -c "SUPPORTED_BOOKS" adapters/odds_api.py` returns 1
    - `grep "SUPPORTED_BOOKS" adapters/odds_api.py` shows fanduel, draftkings, betmgm, bet365
    - `grep -c "NotImplementedError" services/odds_normalizer.py services/arb_detector.py services/parlay_engine.py utils/odds_math.py utils/formatters.py` returns at least 8 (all stubs raise NotImplementedError)
    - `grep -c "EMBED_COLOR" utils/formatters.py` returns at least 3 (imported and referenced in all three embed builders)
    - `grep -c "from config import EMBED_COLOR" utils/formatters.py` returns 1
    - `grep -c "def american_to_decimal\|def decimal_to_american\|def implied_probability\|def no_vig_probability" utils/odds_math.py` returns 4
    - `test -f adapters/__init__.py && test -f services/__init__.py` exits 0 (both package inits exist)
    - `python -c "import ast; ast.parse(open('adapters/base.py').read()); print('ok')"` prints "ok"
    - `python -c "import ast; ast.parse(open('utils/formatters.py').read()); print('ok')"` prints "ok"
  </acceptance_criteria>
  <done>adapters/__init__.py (empty), adapters/base.py (abstract SportsbookAdapter), adapters/odds_api.py (OddsApiAdapter stub with 4 books), services/__init__.py (empty), services/odds_normalizer.py (stub), services/arb_detector.py (detect_arb + detect_ev stubs), services/parlay_engine.py (generate_parlay stub), utils/odds_math.py (4 math stubs), utils/formatters.py (3 embed builder stubs importing EMBED_COLOR).</done>
</task>

</tasks>

<verification>
After both tasks complete, run from project root:

```bash
# All model and stub files parse without errors
python -c "
import ast
files = [
    'models/__init__.py', 'models/odds.py', 'models/signals.py', 'models/parlay.py',
    'adapters/__init__.py', 'adapters/base.py', 'adapters/odds_api.py',
    'services/__init__.py', 'services/odds_normalizer.py',
    'services/arb_detector.py', 'services/parlay_engine.py',
    'utils/odds_math.py', 'utils/formatters.py'
]
[ast.parse(open(f).read()) for f in files]
print('ALL 13 FILES SYNTAX OK')
"

# Confirm adapter inheritance chain
grep -c "class OddsApiAdapter(SportsbookAdapter)" adapters/odds_api.py

# Confirm EMBED_COLOR imported in formatters
grep "from config import EMBED_COLOR" utils/formatters.py

# Confirm all 4 math functions present
grep -c "def american_to_decimal\|def decimal_to_american\|def implied_probability\|def no_vig_probability" utils/odds_math.py
```
</verification>

<success_criteria>
- models/: 3 files with OddsSnapshot, NormalizedOdds, Market, ArbSignal, EVSignal, Parlay, ParlayLeg — all pydantic v2 BaseModel
- adapters/: SportsbookAdapter abstract base, OddsApiAdapter stub with correct inheritance and SUPPORTED_BOOKS list
- services/: 3 stub files with NotImplementedError and docstrings referencing phase/requirement IDs
- utils/odds_math.py: 4 math function stubs with docstrings
- utils/formatters.py: 3 embed builder stubs importing EMBED_COLOR from config
- All 13 files: full type hints, no syntax errors, package __init__.py files present
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation/01-B-SUMMARY.md` documenting:
- All 13 files created and what they export
- Pydantic v2 BaseModel confirmed (not dataclasses)
- Adapter inheritance structure
- Which stubs will be filled in Phase 3 vs Phase 4
- Any decisions made during execution
</output>
