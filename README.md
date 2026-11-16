# Web3 Content Pipeline

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Docker Image (GHCR)](https://img.shields.io/badge/ghcr.io-multi--arch-blue?logo=docker)](https://github.com/nothingser0/web3-content-pipeline/pkgs/container/web3-content-pipeline)

An automated, multi-stage content generation pipeline for Web3 and crypto researchers. It features authentic conversational voice styling, multi-tier model fallback, automatic quality control (QC), semantic angle deduplication, and an internal scheduler daemon built for 24/7 Docker deployment.

---

## Features

- **AI Strategist**: Generates and ranks 10 distinct content angles based on contemporary Web3 topics and onchain security themes.
- **AI Writer**: Produces complete drafts across 4 content formats:
  - **Thread**: In-depth educational multi-tweet thread
  - **Image / Carousel**: Concept text accompanied by a visual design brief
  - **Single Tweet**: High-impact standalone tweet under 280 characters
  - **Poll**: Engaging community question with context
- **Visual & Engagement Designers**: Generates image design briefs, posting schedules, CTAs, and hashtags in parallel.
- **4-Layer Quality Control**: Evaluates hook strength, voice consistency, formatting rules, and automatically patches detected issues.
- **Resilient Model Routing**: 3-tier fallback system (`Primary` $\to$ `FB1` $\to$ `FB2`) with connection pooling and transient HTTP 429 rate-limit retries.
- **Automated Docker Daemon**: Built-in scheduler executing daily content generation (Monday–Friday at 07:00 WIB) with Docker healthcheck and log rotation.
- **Publishing Integrations**: Optional delivery of raw angles and final packages to Discord channels and Buffer social media scheduler.

---

## Quick Start

### Prerequisites

- Python 3.10 or newer (or Docker & Docker Compose)
- Access to an OpenAI-compatible API endpoint (e.g., local proxy, OpenCode, or provider API)

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/nothingser0/web3-content-pipeline.git
cd web3-content-pipeline

# Install Python dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
```

Open `.env` and configure your API credentials and preferred models:

```env
OPENCODE_BASE_URL=http://your-api-host:port/v1
OPENCODE_API_KEY=your-api-key-here
```

---

## Usage

### Local CLI Execution

Choose one of the entrypoint scripts depending on your workflow:

```bash
# Option 1: Daily Auto Generation (Generates 1 evergreen topic)
python run_daily_auto.py

# Option 2: Batch Generation (Generates 5 diverse topics concurrently)
python run_batch_5x_auto.py

# Option 3: Manual Input (Interactive custom topic prompt)
python run_manual.py

# Option 4: Twitter Analysis (Processes curated research from twitter-data/)
python run_twitter.py
```

Generated content packages are saved under `./output/{title}_{format}_{timestamp}/`.

---

## Docker Deployment

Pre-built multi-architecture images (`linux/amd64` and `linux/arm64`) are published to GitHub Container Registry (GHCR).

### Running with Docker Compose

1. **Prepare configuration:**
   ```bash
   cp .env.example .env
   # Set your OPENCODE_BASE_URL, OPENCODE_API_KEY, and optional Discord/Buffer credentials
   ```

2. **Start the container:**
   ```bash
   # Pull pre-built image and start in background
   docker compose pull
   docker compose up -d
   ```

3. **Monitor logs and status:**
   ```bash
   # View live daemon logs
   docker compose logs -f

   # Check container status and healthcheck
   docker compose ps
   ```

### Docker Scheduler Behavior

- Runs continuously with low memory consumption (~15–25 MB RAM).
- Automatically triggers `run_daily_auto.py` every **Monday through Friday at 07:00 WIB** (Asia/Jakarta).
- Includes container healthcheck verification via heartbeat and log file rotation (max 10MB x 3 files).
- Saved outputs and logs persist on the host filesystem via `./output` and `./logs` volume mounts.

---

## Configuration Reference

Key environment variables available in `.env`:

### API & Model Configuration

| Variable | Description | Default / Example |
|---|---|---|
| `OPENCODE_BASE_URL` | Base URL for OpenAI-compatible completions API | `http://your-api-host:port/v1` |
| `OPENCODE_API_KEY` | Authentication bearer token / API key | `sk-your-api-key` |
| `API_TIMEOUT` | Request timeout in seconds | `600` |
| `MODEL_STRATEGIST_PRIMARY` | Primary model for ideation and angle strategy | `cbcn/deepseek-v4.1-flash` |
| `MODEL_WRITER_PRIMARY` | Primary model for creative drafting | `cx/gpt-6-luna` |
| `MODEL_VISUAL_PRIMARY` | Primary model for visual design briefs | `cbcn/deepseek-v4.1-flash` |
| `MODEL_ENGAGEMENT_PRIMARY`| Primary model for engagement strategy | `cbcn/deepseek-v4.1-flash` |
| `MODEL_QC_PRIMARY` | Primary model for review and autofix | `cx/gpt-6-luna` |

> Each role supports `_PRIMARY`, `_FB1`, and `_FB2` fallback tiers.

### Scheduler Settings

| Variable | Description | Default |
|---|---|---|
| `SCHEDULE_TIME` | Daily trigger time in 24-hour format (`HH:MM`) | `07:00` |
| `SCHEDULE_DAYS` | Active days of the week (`1`=Monday to `7`=Sunday) | `1,2,3,4,5` |
| `RUN_ON_START` | Trigger one execution immediately upon container start | `false` |
| `TZ` | Container timezone | `Asia/Jakarta` |

### Publishing Integrations (Optional)

| Variable | Description |
|---|---|
| `DISCORD_TOKEN` | Discord bot token for channel uploads |
| `DISCORD_CHANNEL_A_ID` | Discord channel ID for early `angle.json` preview |
| `DISCORD_CHANNEL_B_ID` | Discord channel ID for final `FINAL.md` package |
| `BUFFER_ENABLED` | Set `true` to enable automated Buffer scheduling |
| `BUFFER_ACCESS_TOKEN` | Buffer API access token |
| `BUFFER_PROFILE_ID` | Buffer profile/channel ID |

---

## Project Structure

```text
web3-content-pipeline/
├── .github/workflows/        # CI/CD workflow for GHCR multi-arch builds
├── data/                     # Topic templates and dedup history records
├── output/                   # Session-based content packages
├── prompts/                  # Prompt templates library (Strategist, Writer, QC, etc.)
├── src/
│   ├── ai/                   # AI role modules (strategist, writer, visual, engagement)
│   ├── core/                 # Routing, API client, prompt loader, deduplication
│   ├── qc/                   # Format checks and autofix engine
│   ├── utils/                # Configuration, logging, Discord, and Buffer helpers
│   └── package.py            # Final Markdown package assembler
├── tools/                    # Topic seed generators and ranking tools
├── docker-compose.yml        # Docker Compose service definition
├── Dockerfile                # Multi-stage production container image
├── pyproject.toml            # Project packaging specification
├── requirements.txt          # Python runtime dependencies
├── run_daily_auto.py         # Daily automated generator
├── run_batch_5x_auto.py      # Parallel batch generator
├── run_manual.py             # Interactive manual topic runner
├── run_twitter.py            # Twitter research data runner
└── scheduler.py              # Background scheduler daemon for Docker
```

---

## Output Package

Each generation cycle produces a dedicated timestamped folder inside `output/`:

```text
output/{title}_{format}_{timestamp}/
├── angle.json         # Selected content angle and ranking rationale
├── content.txt        # Final written copy
├── visual_brief.txt   # Image / carousel layout specification
├── engagement.txt     # CTAs, hashtag options, and posting recommendations
├── qc_report.txt      # 4-layer quality control audit scores
└── FINAL.md           # Unified ready-to-publish Markdown package
```

---

## License

This project is licensed under the [MIT License](LICENSE).
