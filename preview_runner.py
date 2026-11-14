from pathlib import Path

source_path = Path(__file__).with_name("hosted_preview.py")
source = source_path.read_text(encoding="utf-8")
stripped = source.rstrip()
if stripped.endswith('"""'):
    stripped = stripped[:-3].rstrip() + "\n"
namespace = {"__name__": "hosted_preview_runtime"}
exec(compile(stripped, str(source_path), "exec"), namespace)
app = namespace["app"]
