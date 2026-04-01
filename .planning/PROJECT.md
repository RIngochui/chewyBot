# chewyBot

## What This Is

chewyBot is a production-ready Python Discord bot with five feature modules delivered as cogs: music playback via yt-dlp, text-to-speech via gTTS, a Nitro-free emoji proxy, a real-time sports arbitrage and +EV scanner powered by The Odds API, and a self-learning NBA parlay AI that improves from Discord reaction feedback. It is built for a single Discord server and designed to run continuously as a long-lived process.

## Core Value

Reliably surface sports arbitrage and +EV opportunities to the Discord channel — the odds scanner must always work, auto-scan, and post actionable alerts.

## Requirements

### Validated

**Bot Foundation** (Validated in Phase 1: Foundation)
- [x] Python 3.11+ entry point (bot.py) with cog loader — each cog loads independently so one failure never crashes others
- [x] config.py loads all secrets from .env via pydantic-settings, exposes a typed Config object
- [x] SQLite storage with abstraction layer structured for easy PostgreSQL swap (connection + driver change only)
- [x] All SQL in database/queries.py — zero inline SQL anywhere else
- [x] Logging to file (chewybot.log) + Discord LOG_CHANNEL_ID using Python logging module
- [x] Bot status: "chewyBot is online!" on ready; log channel message: "chewyBot has logged in!"
- [x] Consistent embed color scheme across all cogs (not default blurple)

**Database Schema** (Validated in Phase 1: Foundation)
- [x] Tables: odds_snapshots, normalized_odds, arb_signals, ev_signals, parlays, parlay_legs, leg_type_weights, bot_config

**Deliverables** (Validated in Phase 1: Foundation)
- [x] requirements.txt with pinned versions
- [x] .env.example with all variables
- [x] README.md: setup, Discord Developer Portal, The Odds API key, running, adding sportsbooks, SQLite→PostgreSQL swap
- [x] mock/odds_api_sample.json — realistic sample for MOCK_MODE
- [x] mock/balldontlie_sample.json — realistic sample for MOCK_MODE

**Data Layer** (Validated in Phase 1: Foundation)
- [x] Pydantic v2 models: Market, OddsSnapshot, NormalizedOdds, ArbSignal, EVSignal, ParlayLeg, Parlay
- [x] Abstract SportsbookAdapter interface + OddsApiAdapter stub
- [x] Service stubs: odds_normalizer, arb_detector, parlay_engine (Phase 3/4 implement)
- [x] Math utilities: odds_math, formatters

### Active

**Bot Foundation**
- [ ] Python 3.11+ entry point (bot.py) with cog loader — each cog loads independently so one failure never crashes others
- [ ] config.py loads all secrets from .env via pydantic-settings, exposes a typed Config object
- [ ] SQLite storage with abstraction layer structured for easy PostgreSQL swap (connection + driver change only)
- [ ] All SQL in database/queries.py — zero inline SQL anywhere else
- [ ] Logging to file (chewybot.log) + Discord LOG_CHANNEL_ID using Python logging module
- [ ] Bot status: "chewyBot is online!" on ready; log channel message: "chewyBot has logged in!"
- [ ] Consistent embed color scheme across all cogs (not default blurple)

**Cog 1 — Music (cogs/music.py)** (Validated in Phase 2: Voice & Community Cogs)
- [x] yt-dlp + discord.py voice client (no discord-music-player)
- [x] Slash commands: /play, /playlist, /skip, /stop, /pause, /resume, /queue, /nowplaying, /volume, /seek, /shuffle, /loop, /remove, /clearqueue
- [x] Auto-leave when voice channel is empty
- [x] Log embeds to LOG_CHANNEL_ID on song start, playlist add, queue end

**Cog 2 — TTS (cogs/tts.py)** (Validated in Phase 2: Voice & Community Cogs)
- [x] gTTS generates audio to temp file, plays in voice channel, deletes after
- [x] Slash commands: /tts, /tts_lang, /tts_stop
- [x] TTS_INTERRUPTS_MUSIC env toggle; TTS_MAX_CHARS limit (default 300)
- [x] Error if user not in a voice channel

**Cog 3 — Emoji Proxy (cogs/emoji.py)** (Validated in Phase 2: Voice & Community Cogs)
- [x] /emote — bot reposts as clean "[Username]: <emoji>" message
- [x] /add_emote, /remove_emote — require Manage Emojis permission; validate <256KB, PNG/JPG/GIF
- [x] /list_emotes — paginated embed with previews
- [x] Graceful name conflict errors; suggest closest match if not found

**Cog 4 — Arbitrage Scanner (cogs/arb.py)**
- [ ] Adapter pattern: adapters/base.py abstract interface + adapters/odds_api.py implementation
- [ ] The Odds API: books fanduel, draftkings, betmgm, bet365; exponential backoff max 3 retries; API quota tracking
- [ ] MOCK_MODE=true loads from mock/odds_api_sample.json
- [ ] Odds normalization to canonical NormalizedOdds schema with event_id and market_key slugs
- [ ] Arb detection: sum(1/best_odds) < 1.0, arb_pct, stake per side, estimated profit, MIN_ARB_PCT filter, deduplication with 0.2% improvement threshold
- [ ] +EV detection: no-vig fair probability, EV% = ((offered_decimal * fair_prob) - 1) * 100, MIN_EV_PCT filter
- [ ] Math helpers: american_to_decimal, decimal_to_american, implied_probability, no_vig_probability
- [ ] Auto-scanner loop every SCAN_INTERVAL_SECONDS (default 60s), posts to ARB_CHANNEL_ID
- [ ] Slash commands: /ping, /scan, /latest_arbs, /latest_ev, /set_bankroll, /set_min_arb, /set_min_ev, /toggle_sport, /status
- [ ] Alert embeds with "possible arbitrage" / "estimated" language and disclaimer footer

**Cog 5 — NBA Parlay AI (cogs/parlay.py)**
- [ ] balldontlie API (no key) for team stats + recent results; The Odds API reused for NBA lines
- [ ] Daily auto-post at PARLAY_POST_TIME (default 11:00 AM ET) to PARLAY_CHANNEL_ID
- [ ] 3–5 leg parlay generation with 5-factor weighted scoring (recent_form, home_away_split, rest_days, line_value, historical_hit_rate)
- [ ] Never include both sides of same game; only legs with leg_score >= MIN_LEG_SCORE
- [ ] Learning system: ✅/❌ Discord reactions update weights, persist in leg_type_weights table
- [ ] Weight formula: new_weight = old_weight + (PARLAY_LEARNING_RATE * delta), delta ±1
- [ ] After 20+ tracked parlays: filter leg types with historical hit rate < 30%
- [ ] Slash commands: /parlay, /parlay_stats, /parlay_history
- [ ] Reaction handling: first valid reaction per parlay wins, ignore bot's own reactions

**Database Schema**
- [ ] Tables: odds_snapshots, normalized_odds, arb_signals, ev_signals, parlays, parlay_legs, leg_type_weights, bot_config

**Deliverables**
- [ ] requirements.txt with pinned versions
- [ ] .env.example with all variables
- [ ] README.md: setup, Discord Developer Portal, The Odds API key, running, adding sportsbooks, SQLite→PostgreSQL swap
- [ ] mock/odds_api_sample.json — realistic sample for MOCK_MODE
- [ ] mock/balldontlie_sample.json — realistic sample for MOCK_MODE

### Out of Scope

- Auto-betting functionality — explicitly excluded; this is an alerting tool only
- Captcha bypass, account evasion, stealth features — never
- Guaranteed profit claims — alert language always uses "possible" / "estimated"
- Prefix commands — slash commands only throughout
- Multi-server deployment — single guild scoped

## Context

- **Tech stack is fully specified**: Python 3.11+, discord.py v2.x, SQLite (PostgreSQL-swappable), asyncio, yt-dlp, gTTS, httpx, Pydantic v2, Python logging
- **All env vars defined in spec**: DISCORD_BOT_TOKEN, ODDS_API_KEY, ARB_CHANNEL_ID, PARLAY_CHANNEL_ID, LOG_CHANNEL_ID, GUILD_ID, BANKROLL, MIN_ARB_PCT, MIN_EV_PCT, SCAN_INTERVAL_SECONDS, PARLAY_POST_TIME, PARLAY_LEARNING_RATE, MIN_LEG_SCORE, ENABLED_SPORTS, TTS_INTERRUPTS_MUSIC, TTS_MAX_CHARS, MOCK_MODE, LOG_LEVEL
- **Project directory already exists** at /Users/ringochui/Projects/chewyBot — greenfield, no existing code
- **External dependencies**: The Odds API (free tier, rate limited), balldontlie API (free, no key), Discord Developer Portal bot token, ffmpeg required for audio playback

## Constraints

- **Tech Stack**: discord.py v2.x with slash commands — no prefix commands, no third-party music libraries
- **Storage**: SQLite with PostgreSQL-swappable abstraction — no ORM, raw SQL in queries.py only
- **Audio**: ffmpeg must be installed on host for yt-dlp and gTTS playback
- **API**: The Odds API free tier has limited quota — quota tracked from response headers, exposed in /status
- **Safety**: No inline SQL anywhere except queries.py; no auto-bet; alert language never claims guaranteed profit
- **Resilience**: Each cog loads independently; external API calls use exponential backoff (max 3 retries)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| yt-dlp over discord-music-player | More control, actively maintained, no wrapper dependency | Validated Phase 2 — FFmpegPCMAudio + yt-dlp streaming, 14 commands |
| Raw SQL in queries.py over ORM | Explicit PostgreSQL swap path, no migration framework needed | Validated Phase 1 — queries.py enforced |
| Adapter pattern for sportsbooks | Easy to add new books without touching scanner logic | Validated Phase 1 — base.py interface + OddsApiAdapter stub |
| SQLite with swap comments over dual support | Simpler v1, clear migration path documented | Validated Phase 1 — 2-line swap documented in db.py |
| Pydantic v2 for all API response parsing | Runtime validation, clear error messages on API changes | Validated Phase 1 — all 7 models use pydantic v2 BaseModel |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-31 — Phase 2 Voice & Community Cogs complete*
