# Requirements: chewyBot

**Defined:** 2026-03-30
**Core Value:** Reliably surface sports arbitrage and +EV opportunities to the Discord channel — the odds scanner must always work, auto-scan, and post actionable alerts.

## v1 Requirements

### Bot Foundation

- [x] **BOT-01**: Bot entry point (bot.py) loads all cogs independently — one cog failing never crashes others
- [x] **BOT-02**: config.py loads all secrets from .env via pydantic-settings and exposes a typed Config object
- [x] **BOT-03**: Bot displays status "chewyBot is online!" on ready and posts "chewyBot has logged in!" to LOG_CHANNEL_ID
- [x] **BOT-04**: Logging writes to chewybot.log file AND Discord LOG_CHANNEL_ID using Python logging module
- [x] **BOT-05**: All embeds use a consistent color scheme across all cogs (not default blurple)
- [x] **BOT-06**: Full type hints on every function throughout the codebase
- [x] **BOT-07**: All external API calls use exponential backoff with max 3 retries

### Database

- [x] **DB-01**: SQLite storage layer with all SQL in database/queries.py — zero inline SQL anywhere else
- [x] **DB-02**: db.py connection manager has clear comment block showing exactly what to change to swap SQLite → PostgreSQL (connection string and driver import only)
- [x] **DB-03**: Tables created: odds_snapshots, normalized_odds, arb_signals, ev_signals, parlays, parlay_legs, leg_type_weights, bot_config
- [x] **DB-04**: Pydantic v2 models used for all API response parsing and data validation

### Music Cog

- [x] **MUS-01**: /play [query or URL] — searches YouTube or plays direct URL; bot joins user's voice channel
- [x] **MUS-02**: /playlist [url] — loads a YouTube playlist into queue
- [x] **MUS-03**: /skip — skips current song
- [x] **MUS-04**: /stop — stops playback, clears queue, bot leaves voice channel
- [x] **MUS-05**: /pause — pauses playback
- [x] **MUS-06**: /resume — resumes playback
- [x] **MUS-07**: /queue — shows current queue as paginated embed (10 songs per page)
- [x] **MUS-08**: /nowplaying — shows current song with title, thumbnail, duration, and text progress bar
- [x] **MUS-09**: /volume [0-100] — sets playback volume
- [x] **MUS-10**: /seek [seconds] — seeks to timestamp in current track
- [x] **MUS-11**: /shuffle — shuffles the queue
- [x] **MUS-12**: /loop [off/song/queue] — sets repeat mode
- [x] **MUS-13**: /remove [position] — removes song at queue position
- [x] **MUS-14**: /clearqueue — clears entire queue
- [x] **MUS-15**: Bot auto-leaves when voice channel is empty
- [x] **MUS-16**: Embeds posted to LOG_CHANNEL_ID on: song start (title, URL, thumbnail, duration, requested by), playlist added (name, count, first thumbnail), queue end
- [x] **MUS-17**: Uses yt-dlp + discord.py voice client (no discord-music-player)

### TTS Cog

- [x] **TTS-01**: /tts [text] — converts text to speech via gTTS, plays in user's current voice channel
- [x] **TTS-02**: /tts_lang [language_code] — sets preferred TTS language (default: en)
- [x] **TTS-03**: /tts_stop — stops current TTS playback
- [x] **TTS-04**: Audio generated to temp file, played, deleted after playback
- [x] **TTS-05**: TTS_INTERRUPTS_MUSIC env var controls whether TTS queues after current song or interrupts
- [x] **TTS-06**: TTS_MAX_CHARS env var enforces max character limit (default: 300)
- [x] **TTS-07**: Error returned if user is not in a voice channel

### Emoji Proxy Cog

- [x] **EMO-01**: /emote [name] — bot reposts as clean "[Username]: <emoji>" message; slash command invocation deleted
- [x] **EMO-02**: /add_emote [name] [image_url] — downloads image, validates <256KB and PNG/JPG/GIF format, uploads as custom server emoji; requires Manage Emojis permission
- [x] **EMO-03**: /remove_emote [name] — removes custom emoji from server; requires Manage Emojis permission
- [x] **EMO-04**: /list_emotes — paginated embed with emoji previews
- [x] **EMO-05**: Graceful name conflict errors; suggests closest match if emoji not found

### Arbitrage Scanner Cog

- [x] **ARB-01**: Adapter pattern — adapters/base.py abstract interface with get_sports(), get_events(), get_odds() methods
- [x] **ARB-02**: adapters/odds_api.py implements base using The Odds API; reads ODDS_API_KEY from env
- [x] **ARB-03**: Books covered: fanduel, draftkings, betmgm, bet365
- [x] **ARB-04**: MOCK_MODE=true loads from mock/odds_api_sample.json instead of live API
- [x] **ARB-05**: API quota remaining tracked from response headers, exposed via /status command
- [x] **ARB-06**: Odds normalized to canonical schema: sport, league, event_name, home_team, away_team, start_time, market_type, selection_name, line_value, decimal_odds, american_odds, book_name, fetched_at, event_id, market_key
- [x] **ARB-07**: event_id slugified as "{home_team}_{away_team}_{date}"; market_key as "{event_id}_{market_type}_{selection_name}"
- [x] **ARB-08**: Arb detection: sum(1/best_odds) < 1.0 → arb exists; calculates arb_pct, stake per side, estimated profit
- [x] **ARB-09**: MIN_ARB_PCT threshold filters noise (default 0.5%); deduplication skips re-alerting same market_key unless arb_pct improves by >0.2%
- [x] **ARB-10**: +EV detection: no_vig_probability() on consensus line; EV% = ((offered_decimal * fair_prob) - 1) * 100; MIN_EV_PCT threshold (default 2.0%)
- [x] **ARB-11**: Math helpers in utils/odds_math.py: american_to_decimal, decimal_to_american, implied_probability, no_vig_probability
- [x] **ARB-12**: Auto-scanner loop — replaced with on-demand /scan_arbs (accepted deviation, human-approved)
- [x] **ARB-13**: /ping — bot latency
- [x] **ARB-14**: /scan_arbs — trigger manual scan
- [x] **ARB-15**: /latest_arbs — last 5 arb alerts as embeds
- [x] **ARB-16**: /latest_ev — last 5 EV alerts as embeds
- [x] **ARB-17**: /set_bankroll [amount], /set_min_arb [pct], /set_min_ev [pct] — update runtime config
- [x] **ARB-18**: /toggle_sport [sport] — enable/disable sport from scanning
- [x] **ARB-19**: /status — current config, last scan time, Odds API quota remaining
- [x] **ARB-20**: Arb alert embed: title "⚡ Possible Arbitrage — chewyBot", fields for sport/event/market/sides/arb%/stake/profit, disclaimer footer
- [x] **ARB-21**: EV alert embed: title "📈 +EV Opportunity — chewyBot", fields for sport/event/market/book/odds/fair probability/EV%, disclaimer footer
- [x] **ARB-22**: Alert footers always say "possible"/"estimated"; never "guaranteed"

### NBA Parlay AI Cog

- [x] **PAR-01**: Data from balldontlie API (no key) for team stats + recent results; The Odds API adapter reused for NBA lines
- [ ] **PAR-02**: Auto-posts daily at PARLAY_POST_TIME (default 11:00 AM ET) to PARLAY_CHANNEL_ID
- [x] **PAR-03**: Generates 3–5 leg NBA parlay using 5-factor weighted scoring: recent_form (0.25), home_away_split (0.20), rest_days (0.15), line_value (0.25), historical_hit_rate (0.15)
- [x] **PAR-04**: Never includes both sides of the same game; only includes legs with leg_score >= MIN_LEG_SCORE (default 0.5)
- [x] **PAR-05**: Every posted parlay saved to SQLite with all legs, metadata, Discord message_id
- [ ] **PAR-06**: ✅ reaction → marks HIT, increases weights; ❌ reaction → marks MISS, decreases weights
- [ ] **PAR-07**: Weight update: new_weight = old_weight + (PARLAY_LEARNING_RATE * delta), delta ±1; PARLAY_LEARNING_RATE default 0.05
- [ ] **PAR-08**: After 20+ tracked parlays, filters out leg types with historical hit rate < 30%
- [x] **PAR-09**: All weights persist in leg_type_weights table, survive restarts
- [x] **PAR-10**: Parlay embed: title "🏀 chewyBot's NBA Parlay — [date]", each leg (team, market type, line, American odds), combined parlay odds, confidence score 0–100, reaction prompt
- [ ] **PAR-11**: /parlay — manually generate today's parlay
- [ ] **PAR-12**: /parlay_stats — hit rate, total tracked, best/worst leg types
- [ ] **PAR-13**: /parlay_history [n] — last n parlays with hit/miss/pending outcome
- [ ] **PAR-14**: Reaction handling: first valid ✅/❌ per parlay wins; ignores bot's own reactions; only tracks reactions on chewyBot messages

### Deliverables

- [x] **DEL-01**: requirements.txt with pinned versions
- [x] **DEL-02**: .env.example with all 20 variables documented
- [x] **DEL-03**: README.md: what chewyBot is, prerequisites (Python 3.11+, ffmpeg, API keys), step-by-step install, Discord Developer Portal setup, Odds API key setup, how to run, how to add a new sportsbook, how to swap SQLite → PostgreSQL
- [x] **DEL-04**: mock/odds_api_sample.json — realistic multi-sport sample for MOCK_MODE
- [x] **DEL-05**: mock/balldontlie_sample.json — realistic NBA teams/stats sample for MOCK_MODE

## v2 Requirements

### Future Enhancements

- **V2-01**: Multi-guild support with per-guild config isolation
- **V2-02**: Web dashboard for arb/EV alert history and parlay stats
- **V2-03**: PostgreSQL migration for production deployment
- **V2-04**: Additional sportsbook adapters (Caesars, PointsBet, etc.)
- **V2-05**: Push notifications / webhook alerts for arb signals
- **V2-06**: Additional sports leagues beyond the initial ENABLED_SPORTS
- **V2-07**: Spotify integration for music cog

## Out of Scope

| Feature | Reason |
|---------|--------|
| Auto-betting functionality | Explicitly prohibited — alerting tool only, no execution |
| Guaranteed profit claims | Alert language always uses "possible"/"estimated" |
| Captcha bypass / account evasion | Never — no stealth or adversarial features |
| Prefix commands | Slash commands only throughout per spec |
| discord-music-player library | Use yt-dlp + discord.py voice client directly |
| ORM (SQLAlchemy, etc.) | Raw SQL in queries.py only, explicit PostgreSQL swap path |
| Multi-server deployment | Single guild scoped for v1 |
| Mobile / web frontend | Bot-only interface for v1 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| BOT-01 | Phase 1 — Foundation | Complete |
| BOT-02 | Phase 1 — Foundation | Complete |
| BOT-03 | Phase 1 — Foundation | Complete |
| BOT-04 | Phase 1 — Foundation | Complete |
| BOT-05 | Phase 1 — Foundation | Complete |
| BOT-06 | Phase 1 — Foundation | Complete |
| BOT-07 | Phase 1 — Foundation | Complete |
| DB-01 | Phase 1 — Foundation | Complete |
| DB-02 | Phase 1 — Foundation | Complete |
| DB-03 | Phase 1 — Foundation | Complete |
| DB-04 | Phase 1 — Foundation | Complete |
| DEL-01 | Phase 1 — Foundation | Complete |
| DEL-02 | Phase 1 — Foundation | Complete |
| DEL-03 | Phase 1 — Foundation | Complete |
| DEL-04 | Phase 1 — Foundation | Complete |
| DEL-05 | Phase 1 — Foundation | Complete |
| MUS-01 | Phase 2 — Voice & Community Cogs | Complete |
| MUS-02 | Phase 2 — Voice & Community Cogs | Complete |
| MUS-03 | Phase 2 — Voice & Community Cogs | Complete |
| MUS-04 | Phase 2 — Voice & Community Cogs | Complete |
| MUS-05 | Phase 2 — Voice & Community Cogs | Complete |
| MUS-06 | Phase 2 — Voice & Community Cogs | Complete |
| MUS-07 | Phase 2 — Voice & Community Cogs | Complete |
| MUS-08 | Phase 2 — Voice & Community Cogs | Complete |
| MUS-09 | Phase 2 — Voice & Community Cogs | Complete |
| MUS-10 | Phase 2 — Voice & Community Cogs | Complete |
| MUS-11 | Phase 2 — Voice & Community Cogs | Complete |
| MUS-12 | Phase 2 — Voice & Community Cogs | Complete |
| MUS-13 | Phase 2 — Voice & Community Cogs | Complete |
| MUS-14 | Phase 2 — Voice & Community Cogs | Complete |
| MUS-15 | Phase 2 — Voice & Community Cogs | Complete |
| MUS-16 | Phase 2 — Voice & Community Cogs | Complete |
| MUS-17 | Phase 2 — Voice & Community Cogs | Complete |
| TTS-01 | Phase 2 — Voice & Community Cogs | Complete |
| TTS-02 | Phase 2 — Voice & Community Cogs | Complete |
| TTS-03 | Phase 2 — Voice & Community Cogs | Complete |
| TTS-04 | Phase 2 — Voice & Community Cogs | Complete |
| TTS-05 | Phase 2 — Voice & Community Cogs | Complete |
| TTS-06 | Phase 2 — Voice & Community Cogs | Complete |
| TTS-07 | Phase 2 — Voice & Community Cogs | Complete |
| EMO-01 | Phase 2 — Voice & Community Cogs | Complete |
| EMO-02 | Phase 2 — Voice & Community Cogs | Complete |
| EMO-03 | Phase 2 — Voice & Community Cogs | Complete |
| EMO-04 | Phase 2 — Voice & Community Cogs | Complete |
| EMO-05 | Phase 2 — Voice & Community Cogs | Complete |
| ARB-01 | Phase 3 — Arbitrage Scanner | Complete |
| ARB-02 | Phase 3 — Arbitrage Scanner | Complete |
| ARB-03 | Phase 3 — Arbitrage Scanner | Complete |
| ARB-04 | Phase 3 — Arbitrage Scanner | Complete |
| ARB-05 | Phase 3 — Arbitrage Scanner | Complete |
| ARB-06 | Phase 3 — Arbitrage Scanner | Complete |
| ARB-07 | Phase 3 — Arbitrage Scanner | Complete |
| ARB-08 | Phase 3 — Arbitrage Scanner | Complete |
| ARB-09 | Phase 3 — Arbitrage Scanner | Complete |
| ARB-10 | Phase 3 — Arbitrage Scanner | Complete |
| ARB-11 | Phase 3 — Arbitrage Scanner | Complete |
| ARB-12 | Phase 3 — Arbitrage Scanner | Complete |
| ARB-13 | Phase 3 — Arbitrage Scanner | Complete |
| ARB-14 | Phase 3 — Arbitrage Scanner | Complete |
| ARB-15 | Phase 3 — Arbitrage Scanner | Complete |
| ARB-16 | Phase 3 — Arbitrage Scanner | Complete |
| ARB-17 | Phase 3 — Arbitrage Scanner | Complete |
| ARB-18 | Phase 3 — Arbitrage Scanner | Complete |
| ARB-19 | Phase 3 — Arbitrage Scanner | Complete |
| ARB-20 | Phase 3 — Arbitrage Scanner | Complete |
| ARB-21 | Phase 3 — Arbitrage Scanner | Complete |
| ARB-22 | Phase 3 — Arbitrage Scanner | Complete |
| PAR-01 | Phase 4 — NBA Parlay AI | Complete |
| PAR-02 | Phase 4 — NBA Parlay AI | Pending |
| PAR-03 | Phase 4 — NBA Parlay AI | Pending |
| PAR-04 | Phase 4 — NBA Parlay AI | Pending |
| PAR-05 | Phase 4 — NBA Parlay AI | Complete |
| PAR-06 | Phase 4 — NBA Parlay AI | Pending |
| PAR-07 | Phase 4 — NBA Parlay AI | Pending |
| PAR-08 | Phase 4 — NBA Parlay AI | Pending |
| PAR-09 | Phase 4 — NBA Parlay AI | Complete |
| PAR-10 | Phase 4 — NBA Parlay AI | Pending |
| PAR-11 | Phase 4 — NBA Parlay AI | Pending |
| PAR-12 | Phase 4 — NBA Parlay AI | Pending |
| PAR-13 | Phase 4 — NBA Parlay AI | Pending |
| PAR-14 | Phase 4 — NBA Parlay AI | Pending |

**Coverage:**
- v1 requirements: 75 total
- Mapped to phases: 75
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-30*
*Last updated: 2026-03-30 after roadmap creation*
