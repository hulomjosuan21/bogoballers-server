from rich.console import Console
from rich.panel import Panel
from src.config import Config
from src.extensions import engine
from sqlalchemy import text
from quart import send_from_directory
from pathlib import Path

console = Console()

def print_debug_banner():
    console.print(
        Panel.fit(
            f"[bold yellow]🚀 BogoBallers server running in DEBUG mode with auto‑reload\n"
            f"[green]Server: Hypercorn (ASGI)[/green]\n"
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