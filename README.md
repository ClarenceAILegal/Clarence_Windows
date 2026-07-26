# Motion Bot

Generate court **motions as Word documents (`.docx`)** from templates you download from **LexisNexis**, filled with case-specific facts.

Motion Bot does **not** log into or scrape LexisNexis. You download forms/templates with your licensed account, import them locally, mark fillable fields, then generate finished motions.

## What it does

1. **Import** LexisNexis-downloaded `.docx` templates into a local library  
2. **Catalog** templates with jurisdiction, motion type, and detected placeholders  
3. **Fill** templates from YAML/JSON case files (caption, parties, facts, prayer, etc.)  
4. **Write** court-ready motion Word documents to `output/`

## Setup

```bash
cd Motion-Bot
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -e .
```

## Private website (password-protected)

Windows 95–style solid blue login → water-ripple transition → futuristic white search UI.

```bash
motion-bot serve
# open http://127.0.0.1:8000
```

| Item | Detail |
|------|--------|
| Default password | `B0ts4Justice` (**case-sensitive**) |
| Override | `export MOTION_BOT_PASSWORD='...'` |
| Session secret | optional `MOTION_BOT_SECRET_KEY` |

| Page | Purpose |
|------|---------|
| `/login` | Solid blue Win95-style password gate |
| `/home` | Futuristic motion search by description |
| `/library` | Full template list + recent downloads |
| `/generate` | Fill fields and generate a motion `.docx` |
| `/upload` | Import a Lexis `.docx` template |

Notes:
- Default bind is **localhost only** (`127.0.0.1`).
- Shared site password (not multi-user accounts).

## CLI quick start

```bash
# See sample + imported templates
motion-bot list-templates

# Create an editable case file
motion-bot init-case

# Generate a filled motion .docx
motion-bot generate data/cases/example_case.yaml
```

Output lands in `output/`.

## LexisNexis workflow

1. In LexisNexis, download the motion form/template as **Word (`.docx`)**.  
2. Import it:

```bash
motion-bot import-template ~/Downloads/Your_Lexis_Motion.docx \
  --id motion-to-dismiss-ca \
  --name "Motion to Dismiss" \
  --jurisdiction CA \
  --motion-type dismiss
```

3. Open the file under `templates/lexis/` in Word. Replace blanks with **Jinja** placeholders, e.g.:

| Field | Placeholder |
|-------|-------------|
| Court | `{{ court_name }}` |
| Case number | `{{ case_number }}` |
| Plaintiff / Defendant | `{{ plaintiff }}` / `{{ defendant }}` |
| Motion title | `{{ motion_title }}` |
| Facts | `{{ factual_background }}` |
| Argument | `{{ legal_argument }}` |
| Prayer | `{{ prayer_for_relief }}` |
| Counsel | `{{ counsel_name }}`, `{{ counsel_bar }}`, `{{ counsel_firm }}` |

Nested fields work too: `{{ caption.case_number }}`, `{{ movant.email }}`.

4. Refresh detected fields and generate:

```bash
motion-bot show-template motion-to-dismiss-ca --refresh
motion-bot generate path/to/your_case.yaml
```

See [templates/lexis/README.md](templates/lexis/README.md) for details.

## Case file format

Starter file from `motion-bot init-case` includes:

- `template_id` — must match a registered template  
- `caption` — court, parties, case number, judge  
- `movant` / `respondent` — party and counsel  
- narrative sections — `factual_background`, `legal_argument`, `prayer_for_relief`, …  
- `custom` — any extra keys for template-specific placeholders  

JSON is also accepted (`.json`).

## CLI

| Command | Purpose |
|---------|---------|
| `motion-bot list-templates` | List sample + Lexis imports |
| `motion-bot show-template ID [--refresh]` | Inspect placeholders |
| `motion-bot import-template PATH` | Import a downloaded Lexis `.docx` |
| `motion-bot init-case` | Write starter case YAML |
| `motion-bot generate CASE_FILE` | Produce filled motion `.docx` |
| `motion-bot paths` | Print project directories |

## Project layout

```
Motion-Bot/
  motion_bot/           # CLI + generator
  templates/
    sample/             # Built-in sample motion template
    lexis/              # Your LexisNexis downloads (imported here)
    manifest.yaml       # Template registry (auto-maintained)
  data/cases/           # Case input YAML/JSON
  output/               # Generated motions
  scripts/              # Sample template builder
```

## Notes

- Templates are filled with [docxtpl](https://docxtpl.readthedocs.io/) (Jinja2 inside Word).  
- Keep Lexis-sourced files and client data consistent with your license and confidentiality rules.  
- Sample output is a **demonstration** structure, not legal advice or a substitute for jurisdiction-specific practice.

## License / compliance

You are responsible for LexisNexis license compliance, court local rules, and attorney review of every generated filing.
