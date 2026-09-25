"""Write the CHANGELOG.md section for one version to a file (GitHub Release notes)."""

import re
import sys
from pathlib import Path

version, output = sys.argv[1], Path(sys.argv[2])
text = Path(__file__).resolve().parents[2].joinpath("CHANGELOG.md").read_text(encoding="utf-8")
pattern = rf"^## \[{re.escape(version)}\].*?$(.*?)(?=^## |^\[[^\]]+\]: |\Z)"
match = re.search(pattern, text, re.M | re.S)
if not match:
    sys.exit(f"CHANGELOG.md has no section for {version}")
output.write_text(match.group(1).strip() + "\n", encoding="utf-8")
