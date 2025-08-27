from rich.console import Console
from rich.panel import Panel
from src.config import Config
from src.extensions import engine
from sqlalchemy import text
from quart import send_from_directory
from pathlib import Path

from src.utils.api_response import ApiException

console = Console()

def print_debug_banner(init_scheduler_flag: bool):
    console.print(
        Panel.fit(
            f"[bold yellow]🚀 BogoBallers server running in DEBUG mode with auto‑reload\n"
            f"[green]Server: Hypercorn (ASGI)[/green]\n"
            f"[violet]Worker: {'enabled' if init_scheduler_flag else 'disabled'}[/violet]\n"
            f"[cyan]Visit: http://{Config.HOST}:{Config.PORT}[/cyan]\n"
            "[dim]Press CTRL+C to stop[/dim]",
            border_style="bright_blue",
            title="[bold]SERVER STATUS[/bold]",
            subtitle="Programmer: Josuan",
            subtitle_align="right",
            title_align="left"
        )
    )
    
async def check_db_connection():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        print("✅ Database connection initialized")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        raise SystemExit(1)
    
def print_routes(app):
    print("\n📌 Registered Routes:")
    for rule in app.url_map.iter_rules():
        methods = ",".join(sorted(rule.methods - {"HEAD", "OPTIONS"}))
        print(f"{methods:10s} {rule.rule}")
    print()
    
def validate_required_fields(data: dict, required_fields: list[str]):
    missing_fields = [field for field in required_fields if not data.get(field)]
    if missing_fields:
        raise ApiException(f"Missing required fields: {', '.join(missing_fields)}",400)