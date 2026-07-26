"""Command-line interface for Motion Bot."""

from __future__ import annotations

from pathlib import Path

import click

from motion_bot import __version__
from motion_bot.case_io import dump_case_template, load_case_file
from motion_bot.catalog import (
    get_template,
    import_lexis_template,
    list_templates,
    refresh_placeholders,
)
from motion_bot.generator import generate_motion
from motion_bot.paths import CASES_DIR, OUTPUT_DIR, ensure_runtime_dirs


@click.group()
@click.version_option(__version__, prog_name="motion-bot")
def main() -> None:
    """Motion Bot — generate court motions as Word (.docx) from templates.

    Import LexisNexis templates you download with your license, fill them with
    case data, and write finished motion Word documents.
    """
    ensure_runtime_dirs()


@main.command("list-templates")
def list_templates_cmd() -> None:
    """List registered motion templates (sample + LexisNexis imports)."""
    entries = list_templates()
    if not entries:
        click.echo("No templates registered yet.")
        click.echo("Import a downloaded LexisNexis .docx with: motion-bot import-template PATH")
        return
    for e in entries:
        status = "ok" if e.path.exists() else "MISSING"
        click.echo(f"{e.id}")
        click.echo(f"  name:          {e.name}")
        click.echo(f"  source:        {e.source}")
        click.echo(f"  motion_type:   {e.motion_type or '-'}")
        click.echo(f"  jurisdiction:  {e.jurisdiction or '-'}")
        click.echo(f"  path:          {e.path} [{status}]")
        if e.placeholders:
            click.echo(f"  placeholders:  {', '.join(e.placeholders)}")
        if e.description:
            click.echo(f"  description:   {e.description}")
        click.echo("")


@main.command("show-template")
@click.argument("template_id")
@click.option("--refresh", is_flag=True, help="Re-scan the .docx for placeholders.")
def show_template_cmd(template_id: str, refresh: bool) -> None:
    """Show details for one template."""
    entry = refresh_placeholders(template_id) if refresh else get_template(template_id)
    click.echo(f"id:            {entry.id}")
    click.echo(f"name:          {entry.name}")
    click.echo(f"source:        {entry.source}")
    click.echo(f"path:          {entry.path}")
    click.echo(f"jurisdiction:  {entry.jurisdiction or '-'}")
    click.echo(f"motion_type:   {entry.motion_type or '-'}")
    click.echo(f"description:   {entry.description or '-'}")
    click.echo(f"notes:         {entry.notes or '-'}")
    click.echo("placeholders:")
    if entry.placeholders:
        for p in entry.placeholders:
            click.echo(f"  - {p}")
    else:
        click.echo(
            "  (none found — add Jinja tags like {{ case_number }} to the Word template)"
        )


@main.command("import-template")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--id", "template_id", default=None, help="Template id (default: from filename).")
@click.option("--name", default=None, help="Human-readable name.")
@click.option("--jurisdiction", default="", help="e.g. CA, NY, Federal")
@click.option("--motion-type", default="", help="e.g. compel, dismiss, summary-judgment")
@click.option("--description", default="", help="Short description.")
def import_template_cmd(
    path: Path,
    template_id: str | None,
    name: str | None,
    jurisdiction: str,
    motion_type: str,
    description: str,
) -> None:
    """Import a LexisNexis-downloaded .docx into the local template library.

    Motion Bot does not connect to LexisNexis. Download forms/templates through
    your licensed account, then point this command at the file.
    """
    entry = import_lexis_template(
        path,
        template_id=template_id,
        name=name,
        description=description,
        jurisdiction=jurisdiction,
        motion_type=motion_type,
    )
    click.echo(f"Imported template '{entry.id}' -> {entry.path}")
    if entry.placeholders:
        click.echo(f"Placeholders detected: {', '.join(entry.placeholders)}")
    else:
        click.echo(
            "No Jinja placeholders found. Open the .docx and insert tags such as "
            "{{ case_number }}, {{ motion_title }}, {{ factual_background }}."
        )


@main.command("init-case")
@click.option(
    "--out",
    "out_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Where to write the starter case YAML.",
)
def init_case_cmd(out_path: Path | None) -> None:
    """Write a starter case YAML file you can edit and pass to generate."""
    ensure_runtime_dirs()
    dest = out_path or (CASES_DIR / "example_case.yaml")
    path = dump_case_template(dest)
    click.echo(f"Wrote starter case file: {path}")
    click.echo("Edit the fields, then run: motion-bot generate PATH")


@main.command("generate")
@click.argument("case_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--out",
    "out_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Output .docx path (default: output/).",
)
def generate_cmd(case_file: Path, out_path: Path | None) -> None:
    """Generate a filled motion Word document from a case YAML/JSON file."""
    request = load_case_file(case_file)
    result = generate_motion(request, output_path=out_path)
    click.echo(f"Generated motion: {result}")
    click.echo(f"Template: {request.template_id}")
    click.echo(f"Title:    {request.motion_title}")


@main.command("paths")
def paths_cmd() -> None:
    """Print important project directories."""
    from motion_bot.paths import (
        CASES_DIR,
        LEXIS_TEMPLATES_DIR,
        OUTPUT_DIR,
        SAMPLE_TEMPLATES_DIR,
        TEMPLATES_DIR,
    )

    click.echo(f"templates:       {TEMPLATES_DIR}")
    click.echo(f"  sample:        {SAMPLE_TEMPLATES_DIR}")
    click.echo(f"  lexis imports: {LEXIS_TEMPLATES_DIR}")
    click.echo(f"cases:           {CASES_DIR}")
    click.echo(f"output:          {OUTPUT_DIR}")


@main.command("serve")
@click.option("--host", default="127.0.0.1", show_default=True, help="Bind address.")
@click.option("--port", default=8000, show_default=True, type=int, help="Port.")
@click.option("--reload", is_flag=True, help="Auto-reload on code changes (dev only).")
def serve_cmd(host: str, port: int, reload: bool) -> None:
    """Run the password-protected private web UI.

    Requires MOTION_BOT_PASSWORD in the environment. Optional:
    MOTION_BOT_SECRET_KEY for stable session cookies across restarts.
    """
    import os

    import uvicorn

    if not os.environ.get("MOTION_BOT_PASSWORD", "").strip():
        raise click.ClickException(
            "Set MOTION_BOT_PASSWORD before starting the web UI.\n"
            "Example:\n"
            "  export MOTION_BOT_PASSWORD='your-strong-password'\n"
            "  motion-bot serve"
        )

    click.echo(f"Motion Bot private site: http://{host}:{port}")
    click.echo("All features require the site password.")
    uvicorn.run(
        "motion_bot.web.app:app",
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    main()
