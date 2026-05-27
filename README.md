# hermes-cro-agent

Fire a URL at Hermes, get back a screenshotted walk-through of the site's
purchase funnel. Currently crawl-only — analysis/roadmap stages are
stripped while we validate the crawler prompt.

## How it works

```
Your shell  -->  POST /api/crawl   { run_id, url }
                       |
                       v  (async, ~3-5 min)
                 Hermes loads the funnel-crawler skill
                 Walks landing → ... → checkout
                 Screenshots each distinct step
                       |
                       v
            ./crawls/{run_id}/
              crawl.json
              01-landing.png
              02-quiz-...png
              0N-checkout.png
```

## Quickstart

```bash
cp .env.example .env
# edit .env — set ANTHROPIC_API_KEY and WEBHOOK_SECRET
make build
make up
```

## Fire a crawl

```bash
# Defaults to https://perfectbody.me/v2
make crawl

# Or any other URL
URL=https://example.com make crawl
```

Output prints the `run_id`. Watch progress with `make logs`. Results land
in `./crawls/{run_id}/`.

## Make commands

| Command | What it does |
|---|---|
| `make build` | Build the Docker image |
| `make up` | Start the container |
| `make down` | Stop the container |
| `make logs` | Tail logs |
| `make shell` | Shell into the container |
| `make crawl URL=...` | Fire a crawl request |
| `make clean` | Remove image + crawl output |

## Tweaking the prompt

The crawler prompt lives in `skills/funnel-crawler/SKILL.md`. The skills
directory is bind-mounted into the container (`./skills` →
`/root/.hermes/skills`), so edits take effect on the next crawl — no
rebuild needed. The webhook prompt itself lives in
`scripts/entrypoint.sh` (registered at container start) — changing that
requires a `make down && make up`.

## Crawl output

`./crawls/{run_id}/crawl.json`:

```json
{
  "run_id": "...",
  "url": "...",
  "crawled_at": "...",
  "reached_checkout": true,
  "stopped_reason": "reached checkout",
  "steps": [
    {
      "step": 1,
      "name": "landing",
      "url": "...",
      "screenshot": "01-landing.png",
      "action_taken": "clicked 'Start' CTA"
    }
  ]
}
```

Screenshots in the same directory, sequentially numbered.

## Remote deploy

```bash
./scripts/deploy.sh user@your-server.com
```
