<!-- GSD:project-start source:PROJECT.md -->
## Project

**chewyBot**

chewyBot is a production-ready Python Discord bot with five feature modules delivered as cogs: music playback via yt-dlp, text-to-speech via gTTS, a Nitro-free emoji proxy, a real-time sports arbitrage and +EV scanner powered by The Odds API, and a self-learning NBA parlay AI that improves from Discord reaction feedback. It is built for a single Discord server and designed to run continuously as a long-lived process.

**Core Value:** Reliably surface sports arbitrage and +EV opportunities to the Discord channel — the odds scanner must always work, auto-scan, and post actionable alerts.

### Constraints

- **Tech Stack**: discord.py v2.x with slash commands — no prefix commands, no third-party music libraries
- **Storage**: SQLite with PostgreSQL-swappable abstraction — no ORM, raw SQL in queries.py only
- **Audio**: ffmpeg must be installed on host for yt-dlp and gTTS playback
- **API**: The Odds API free tier has limited quota — quota tracked from response headers, exposed in /status
- **Safety**: No inline SQL anywhere except queries.py; no auto-bet; alert language never claims guaranteed profit
- **Resilience**: Each cog loads independently; external API calls use exponential backoff (max 3 retries)
<!-- GSD:project-end -->

<!-- GSD:stack-start source:STACK.md -->
## Technology Stack

Technology stack not yet documented. Will populate after codebase mapping or first phase.
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
