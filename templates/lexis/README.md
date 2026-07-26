# LexisNexis templates

Place Word templates (`.docx`) you download from **LexisNexis** in this folder, or import them with:

```bash
motion-bot import-template /path/to/downloaded-form.docx \
  --id motion-to-dismiss \
  --name "Motion to Dismiss" \
  --jurisdiction CA \
  --motion-type dismiss
```

## Important

- Motion Bot does **not** log into, scrape, or download from LexisNexis.
- Use your licensed LexisNexis account to download forms/templates, then import them here.
- Respect LexisNexis terms of use and your firm’s licensing rules.

## Making templates fillable

Open the `.docx` in Word and replace blanks / bracketed fields with Jinja placeholders, for example:

| Placeholder | Example |
|---|---|
| `{{ court_name }}` | SUPERIOR COURT OF CALIFORNIA |
| `{{ case_number }}` | CV-2026-000123 |
| `{{ plaintiff }}` / `{{ defendant }}` | Party names |
| `{{ motion_title }}` | Motion to Compel Discovery |
| `{{ factual_background }}` | Narrative facts |
| `{{ legal_argument }}` | Legal discussion |
| `{{ prayer_for_relief }}` | Requested relief |
| `{{ counsel_name }}` | Signing attorney |

Nested fields also work: `{{ caption.case_number }}`, `{{ movant.firm }}`.

After editing placeholders:

```bash
motion-bot show-template YOUR_TEMPLATE_ID --refresh
```
