import json
import sys
from pathlib import Path

from app.config import get_settings
from app.services.tooluniverse_adapter import ToolUniverseAdapter


def export_inventory(output_path: Path) -> dict:
    settings = get_settings()
    adapter = ToolUniverseAdapter(
        mode=settings.tool_mode,
        scan_all=settings.tooluniverse_scan_all,
    )
    inventory = {
        "tooluniverse_health": adapter.tooluniverse_health(),
        "tools": adapter.list_tools(),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    return inventory


def main() -> None:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("../../tool_inventory.json")
    inventory = export_inventory(output.resolve())
    print(f"Wrote {len(inventory['tools'])} tools to {output}")
    if not inventory["tooluniverse_health"]["available"]:
        print(f"ToolUniverse unavailable: {inventory['tooluniverse_health']['error']}")


if __name__ == "__main__":
    main()

