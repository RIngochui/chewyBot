# chewyBot

chewyBot is a production-ready Python Discord bot for a single server. It delivers five feature modules as independently-loaded cogs: music playback via yt-dlp, text-to-speech via gTTS, a Nitro-free emoji proxy, a real-time sports arbitrage and +EV scanner powered by The Odds API, and a self-learning NBA parlay AI that improves from Discord reaction feedback. The bot is designed to run as a long-lived process with resilient cog isolation — a syntax error in one cog never prevents the others from loading.

## Features

- **Music** — Stream audio from YouTube and other sources directly into voice channels using yt-dlp. Supports queuing, skipping, volume, seeking, shuffle, and loop.
- **Text-to-Speech** — Generate gTTS audio from text and play it in your voice channel. Configurable max length and music-interrupt behavior.
- **Emoji Proxy** — Post custom emoji without Nitro. Add, remove, and list server emoji via slash commands with permission gating.
- **Arbitrage Scanner** — Fetches live odds from FanDuel, DraftKings, BetMGM, and Bet365 via The Odds API. Detects arbitrage (sum of best odds < 1.0) and +EV opportunities. Auto-scans every 60 seconds and posts alerts to a dedicated channel.
- **NBA Parlay AI** — Generates daily 3-5 leg NBA parlays using a 5-factor scoring model. Learns from Discord reaction feedback (✅/❌) to improve picks over time.
- **Polls & Scheduling** — Create single or multi-choice polls with reaction-based voting. Schedule polls to post at a future time or set up recurring weekly polls. Supports vote-limit enforcement, results summary with percentage bars, and full CRUD management via slash commands.

## Prerequisites

- Python 3.11 or higher
- ffmpeg installed on the host system (required for audio playback)
  - macOS: `brew install ffmpeg`
  - Ubuntu/Debian: `sudo apt-get install ffmpeg`
- pip (bundled with Python 3.11+)
- A Discord account and server where you have Administrator permission
- A free account at [The Odds API](https://the-odds-api.com)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/chewyBot.git
   cd chewyBot
   ```

2. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # Linux/macOS
   .venv\Scripts\activate      # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Copy the environment template:
   ```bash
   cp .env.example .env
   ```

5. Fill in your `.env` file — see [.env.example](.env.example) for all variables and their descriptions. Required fields: `DISCORD_TOKEN`, `GUILD_ID`, `LOG_CHANNEL_ID`, `ARB_CHANNEL_ID`, `PARLAY_CHANNEL_ID`, `ODDS_API_KEY`.

## Discord Developer Portal Setup

1. Go to [https://discord.com/developers/applications](https://discord.com/developers/applications) and click **New Application**.
2. Name your application and click **Create**.
3. In the left sidebar, click **Bot**, then click **Add Bot** → **Yes, do it!**
4. Under **Privileged Gateway Intents**, enable:
   - **Server Members Intent**
   - **Message Content Intent**
   - **Presence Intent**
5. Under **Token**, click **Reset Token** and copy the token. Paste it as `DISCORD_TOKEN` in your `.env` file. Never share this token.
6. In the left sidebar, click **OAuth2 → URL Generator**. Under **Scopes**, check `bot` and `applications.commands`. Under **Bot Permissions**, check `Administrator`.
7. Copy the generated URL, open it in a browser, and invite chewyBot to your server.
8. Right-click your server icon in Discord → **Copy Server ID**. Paste it as `GUILD_ID` in your `.env` file.

## The Odds API Setup

1. Create a free account at [https://the-odds-api.com](https://the-odds-api.com).
2. Navigate to your **Dashboard** and copy your API key.
3. Paste the key as `ODDS_API_KEY` in your `.env` file.
4. The free tier provides 500 requests/month. chewyBot tracks quota from response headers and exposes remaining quota in the `/status` command.
5. To test without consuming quota, set `MOCK_MODE=true` in `.env` — chewyBot will load odds from `mock/odds_api_sample.json` instead.

## Running chewyBot

```bash
python bot.py
```

On first run, you should see (in your terminal and `chewybot.log`):

```
2026-03-30 11:00:00 [INFO] __main__: Loaded cog: cogs.music
2026-03-30 11:00:00 [INFO] __main__: Loaded cog: cogs.tts
2026-03-30 11:00:00 [INFO] __main__: Loaded cog: cogs.emoji
2026-03-30 11:00:00 [INFO] __main__: Loaded cog: cogs.arb
2026-03-30 11:00:00 [INFO] __main__: Loaded cog: cogs.parlay
2026-03-30 11:00:00 [INFO] __main__: Slash commands synced to guild [your guild ID]
2026-03-30 11:00:00 [INFO] __main__: Logged in as chewyBot#1234 (ID: ...)
```

Your log channel will receive `chewyBot has logged in!` and the bot's status will show **chewyBot is online!**. Slash commands appear instantly (guild-scoped sync, no 1-hour global delay).

## Command Reference

### Arbitrage Scanner

| Command | Description |
|---------|-------------|
| `/scan_arbs` | Trigger an immediate scan and post any arb/EV alerts to ARB_CHANNEL_ID |
| `/latest_arbs` | Show the most recent arbitrage signals from the database |
| `/latest_ev` | Show the most recent +EV signals from the database |
| `/status` | Show scanner config (bankroll, thresholds, enabled sports, last scan time, API quota) |
| `/set_bankroll <amount>` | Set the bankroll used to calculate recommended stakes (e.g. `/set_bankroll 1000`) |
| `/set_min_arb <pct>` | Set the minimum arb % to alert on (e.g. `/set_min_arb 1.5` for 1.5%) |
| `/set_min_ev <pct>` | Set the minimum EV % to alert on (e.g. `/set_min_ev 3.0`) |
| `/toggle_sport <key>` | Enable or disable a sport from scanning (e.g. `/toggle_sport basketball_nba`) |
| `/ping` | Check that the bot and scanner are responsive |

The auto-scanner fires every `SCAN_INTERVAL_SECONDS` (default: 60) and posts alerts automatically. It deduplicates — the same opportunity is not re-posted unless arb% improves by more than 0.2%.

Arb alert embeds are titled **"Possible Arbitrage"** and include sport, event, market, both books, arb%, recommended stake split, estimated profit, and a "Not financial advice" disclaimer. Set `MOCK_MODE=true` in `.env` to test without consuming API quota.

### Music

| Command | Description |
|---------|-------------|
| `/play <query>` | Play audio from a YouTube URL or search query |
| `/pause` | Pause playback |
| `/resume` | Resume paused playback |
| `/skip` | Skip the current track |
| `/stop` | Stop playback and clear the queue |
| `/queue` | Show the current queue |
| `/volume <0-100>` | Set playback volume |
| `/seek <seconds>` | Seek to a position in the current track |
| `/shuffle` | Shuffle the queue |
| `/loop` | Toggle loop mode for the current track |
| `/nowplaying` | Show the currently playing track |

### Text-to-Speech

| Command | Description |
|---------|-------------|
| `/tts <text>` | Speak text in your current voice channel via gTTS |

### Emoji Proxy

| Command | Description |
|---------|-------------|
| `/emoji add <name> <url>` | Add a custom emoji to the server |
| `/emoji remove <name>` | Remove a custom emoji |
| `/emoji list` | List all custom emoji |
| `/emoji post <name>` | Post a custom emoji inline (Nitro-free) |

### NBA Parlay AI

| Command | Description |
|---------|-------------|
| `/parlay` | Manually generate and post today's NBA parlay |
| `/parlay_stats` | Show AI performance stats (hit rate, best/worst leg types) |
| `/parlay_history [n]` | Show the last n parlay results (default 5, max 10) |

React ✅ or ❌ on any posted parlay to record a hit or miss. React with a number emoji (1️⃣–5️⃣) on a parlay to mark a specific leg as a miss. The AI updates its leg-type weights after each reaction.

## Poll Commands

All poll commands are subcommands of `/poll`. Vote-limit features (`max_choices`) require **Manage Guild** permission.

| Command | Parameters | Description |
|---------|------------|-------------|
| `/poll create` | `question`, `options`, `duration`, `channel` (opt), `max_choices` (opt) | Post an immediate poll. `options` is comma-separated (2–9 choices). `duration` uses `Xm`/`Xh`/`Xd` (e.g. `2h`). `max_choices` limits how many options each user may pick — requires Manage Guild. |
| `/poll schedule` | `question`, `options`, `post_at`, `close_at`, `channel` (opt), `max_choices` (opt), `repeat` (opt) | Schedule a poll to post at a future time. Supports `YYYY-MM-DD HH:MM` or natural language like `Friday 9:00am`. Set `repeat: weekly` to make it recurring. |
| `/poll schedule_weekly` | `question`, `options`, `day`, `post_time`, `close_time`, `channel` (opt), `max_choices` (opt) | Create a recurring weekly poll. `day` is a full weekday name (e.g. `Monday`). `post_time` and `close_time` are `HH:MM` in UTC. |
| `/poll results [poll_id]` | `poll_id` | Show live vote counts with percentage bars for any poll (open or closed). Response is ephemeral. |
| `/poll close [poll_id]` | `poll_id` | Manually close a poll. Posts a results summary embed to the channel with winner(s) bolded. Requires Manage Guild. |
| `/poll list` | — | List all active, scheduled, and recurring polls with their IDs, status, and timing. Response is ephemeral. |
| `/poll cancel [poll_id]` | `poll_id` | Cancel a poll without posting results. If the poll belongs to a recurring series, the entire series is deactivated. Requires Manage Guild. |
| `/poll edit_recurring [poll_id]` | `poll_id`, `question` (opt), `options` (opt), `day` (opt), `post_time` (opt), `close_time` (opt), `max_choices` (opt) | Update a recurring poll's schedule. Changes take effect on the next weekly occurrence. Requires Manage Guild. |

**Notes:**
- Polls support up to 9 options. Reactions 1️⃣–9️⃣ are used for voting.
- `max_choices=1` acts as a radio button — selecting a new option automatically removes the old one.
- `max_choices=N` (N > 1) allows up to N votes per user; exceeding this removes the reaction and sends a warning.
- On bot restart, active polls automatically re-arm their close tasks. Missed weekly polls post immediately on the next restart.
- Recurring polls automatically schedule the next weekly instance after each poll closes.

## How to Add a New Sportsbook

chewyBot uses an adapter pattern to make adding new sportsbooks straightforward:

1. Create `adapters/new_book.py` — subclass `SportsbookAdapter` from `adapters/base.py`:
   ```python
   from adapters.base import SportsbookAdapter

   class NewBookAdapter(SportsbookAdapter):
       BOOK_KEY = "newbook"

       async def get_sports(self) -> list[str]: ...
       async def get_events(self, sport: str) -> list[dict]: ...
       async def get_odds(self, event_id: str) -> list[dict]: ...
   ```
2. Implement the three abstract methods — see `adapters/odds_api.py` for reference.
3. Register the adapter in `cogs/arb.py` (Phase 3) by adding it to the scanner's adapter list.

The odds normalizer (`services/odds_normalizer.py`) converts any adapter's output to the canonical `NormalizedOdds` schema, so the arb detection logic never changes when you add a new book.

## How to Swap SQLite for PostgreSQL

See `database/db.py` for the exact two-line change required. The PostgreSQL swap comment block at the top of that file documents precisely which import and which connection call to update. All SQL is in `database/queries.py` — you will need to update parameter placeholders from `?` (SQLite) to `$1, $2, ...` (asyncpg) in that file as well.

## Project Structure

```
chewyBot/
├── bot.py                     # Entry point: loads cogs, starts event loop
├── config.py                  # pydantic-settings Config, reads .env, fail-fast validation
├── requirements.txt           # Pinned dependencies
├── .env.example               # Template for all environment variables
├── README.md                  # This file
├── cogs/                      # Feature cogs (each loads independently)
│   ├── __init__.py
│   ├── music.py               # Music playback (Phase 2)
│   ├── tts.py                 # Text-to-speech (Phase 2)
│   ├── emoji.py               # Emoji proxy (Phase 2)
│   ├── arb.py                 # Arbitrage + EV scanner (Phase 3)
│   ├── parlay.py              # NBA parlay AI (Phase 4)
│   └── polls.py               # Polls & Scheduling (quick-260405-32a)
├── database/
│   ├── db.py                  # Async connection manager, WAL mode, table init
│   └── queries.py             # All SQL statements — zero inline SQL elsewhere
├── models/
│   ├── odds.py                # OddsSnapshot, NormalizedOdds Pydantic models
│   ├── signals.py             # ArbSignal, EVSignal Pydantic models
│   └── parlay.py              # ParlayLeg, Parlay Pydantic models
├── adapters/
│   ├── base.py                # Abstract SportsbookAdapter interface
│   └── odds_api.py            # The Odds API concrete adapter
├── services/
│   ├── odds_normalizer.py     # Normalize raw odds to canonical NormalizedOdds
│   ├── arb_detector.py        # Detect arbitrage and +EV from normalized odds
│   └── parlay_engine.py       # Generate and score NBA parlay legs
├── utils/
│   ├── logger.py              # setup_logging() — file + Discord handlers
│   ├── odds_math.py           # american_to_decimal, implied_probability, etc.
│   └── formatters.py          # Discord embed builders for alerts
└── mock/
    ├── odds_api_sample.json   # Realistic odds sample with guaranteed arb opportunity
    └── balldontlie_sample.json # NBA teams, recent games, and team stats
```

## License

MIT License — see [LICENSE](LICENSE) for details.
