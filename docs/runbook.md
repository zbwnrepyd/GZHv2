# Runbook

## Setup

```bash
pip install -r requirements.txt
npm install
sqlite3 db/research_db.sqlite < db/init_research_db.sql
sqlite3 db/final_db.sqlite < db/init_final_db.sql
```

Put secrets in environment variables or `~/.env`. Do not commit secrets.

Required for full research:

```bash
DEEPSEEK_API_KEY=sk-...
TAVILY_API_KEY=tvly-...
```

Optional:

```bash
YOUTUBE_API_KEY=...
IMAGE_API_KEY=sk-...
IMAGE_API_URL=https://api.openai.com/v1/images/generations
FLASK_PORT=5050
DB_PATH_RESEARCH=/absolute/path/to/research_db.sqlite
DB_PATH_FINAL=/absolute/path/to/final_db.sqlite
IMAGES_DIR=/absolute/path/to/images
```

`IMAGE_API_KEY` and `IMAGE_API_URL` are defaults for image generation. The card workbench can also send a one-off `image_api_url` and `image_api_key` to `/api/generate-image`; the one-off API key is not persisted or returned.

## Start

```bash
cd webapp
python3 app.py
```

Open:

```text
http://127.0.0.1:5050/
```

If port 5050 is occupied:

```bash
cd webapp
FLASK_PORT=5051 python3 app.py
```

## Smoke Tests

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile webapp/*.py
node canvas/screenshot.js --help
```

Prompt loading:

```bash
python3 - <<'PY'
import sys
sys.path.insert(0, "webapp")
from deepseek_client import load_prompt
for name in ["layer0-cleaner", "layer1-hv-analysis", "layer2-business", "layer3-field-extraction", "split-text"]:
    print(name, len(load_prompt(name)))
PY
```

Check duplicate final fields:

```bash
sqlite3 db/final_db.sqlite \
"SELECT company_name, card_index, field_name, COUNT(*) FROM final_content GROUP BY company_name, card_index, field_name HAVING COUNT(*) > 1;"
```

Expected output is empty.

## Start Research By API

```bash
curl -X POST http://127.0.0.1:5050/api/research/start \
  -H "Content-Type: application/json" \
  -d '{"company_name":"Anthropic","company_url":"https://www.anthropic.com"}'
```

Response:

```json
{"job_id":"abc123","status":"running"}
```

Poll:

```bash
curl http://127.0.0.1:5050/api/research/status/<job_id>
```

Read result:

```bash
curl http://127.0.0.1:5050/api/research/Anthropic
```

Open finalization desk:

```text
http://127.0.0.1:5050/editor?company=Anthropic
```

In the finalization desk, each card is edited row by row across four columns: standard version, business version, spread version, and final input. Confirm cards 1-8. Card 7 is the competition landscape; card 8 is the summary and contains the market opportunity. The spread hook paragraphs are available from the left-side `传播钩子文案` entry; they are copy options for the article opening and are not written into cards.

The research desk company table shows finalization progress as `confirmed/8`. The card workbench `返回定稿台` button should return to `/editor?company=<company>` for the currently loaded company.

Export for canvas:

```bash
# Structured JSON for the card renderer
curl "http://127.0.0.1:5050/api/final/export/Anthropic?format=json" | python3 -m json.tool

# Open canvas directly with company data
open "http://127.0.0.1:5050/canvas/?company=Anthropic"

# Open one card directly
open "http://127.0.0.1:5050/canvas/card/Anthropic/1"
```

## Card Workbench And PNG Export

The card workbench is an HTML/CSS renderer, not the legacy fabric.js canvas. The left pane shows the current project name as read-only state from `?company=<company>`; use the finalization desk link or URL parameter to switch projects. “卡片每一页” and “图片夹” are mutually exclusive accordions, and each open panel scrolls internally when content is long. The image folder should show Markdown images from finalized cards plus images generated from the prompt bar, and it also contains the background-watermark upload/clear controls. The middle pane previews a scaled `900 x 1200` card. The right pane shows the current card's full `<style>...</style>` plus `<article class="knowledge-card">...</article>` source with syntax highlighting. Editing the source live-renders into the middle iframe. Use “保存当前页源码” to persist that card's source in browser `localStorage`.

The bottom image bar has:

- prompt input
- optional image API URL
- API Key password input
- reset prompt and generate buttons

The API Key input is intentionally not saved. If the browser reloads, paste it again or use `IMAGE_API_KEY` in the environment.

Batch export:

```bash
node canvas/screenshot.js \
  --company Anthropic \
  --base-url http://127.0.0.1:5050 \
  --out output/cards/Anthropic
```

Check job persistence across restarts:

```bash
sqlite3 db/research_db.sqlite "SELECT job_id, status, stage FROM research_jobs ORDER BY created_at DESC LIMIT 5;"
```

## Troubleshooting

- Empty or non-JSON request to `/api/research/start` should return 400 with `缺少 company_name 或 company_url`.
- If a research job fails at L3, no partial all-missing record should be written.
- If hook copy is missing in the finalization desk, open the left-side `传播钩子文案` entry and confirm `hook_paragraph_1/2/3` exist in `GET /api/research/<company>/<version>`.
- If generated images do not display, confirm `/images/<filename>` returns 200 and `IMAGES_DIR` points to the saved image directory.
- If the image folder is empty, first confirm the finalized Markdown contains `![alt](url)` image syntax or generate an image from the bottom prompt bar; both local and remote Markdown image URLs should be preserved by the canvas parser.
- If the background watermark is missing, open “图片夹”, upload a local image again, and confirm browser `localStorage` is available for `aistartups_bg_image`.
- If image generation fails from the card workbench, check the bottom-bar API URL/API Key first, then the environment `IMAGE_API_URL` and `IMAGE_API_KEY`.
- If the card workbench opens without a project name, go back through `/editor?company=<company>` or add `?company=<company>` to the canvas URL; the left project label is intentionally not editable.
- If the card preview differs from the source editor, reload `/canvas/?company=<company>` and confirm the current card source was saved in the same browser profile.
- If PNG export says Puppeteer is missing, run `npm install` from the project root.
- If imports fail in a new environment, reinstall with `pip install -r requirements.txt`.
- `urllib3` may warn about LibreSSL on the system Python. The warning is noisy but was not a blocker in local verification.
