# Runbook

## Setup

```bash
pip install -r requirements.txt
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

## Start

```bash
cd webapp
python3 app.py
```

Open:

```text
http://127.0.0.1:5050/editor/
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

## Troubleshooting

- Empty or non-JSON request to `/api/research/start` should return 400 with `缺少 company_name 或 company_url`.
- If a research job fails at L3, no partial all-missing record should be written.
- If generated images do not display, confirm `/images/<filename>` returns 200 and `IMAGES_DIR` points to the saved image directory.
- If imports fail in a new environment, reinstall with `pip install -r requirements.txt`.
- `urllib3` may warn about LibreSSL on the system Python. The warning is noisy but was not a blocker in local verification.
