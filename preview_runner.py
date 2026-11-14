from pathlib import Path

source_path = Path(__file__).with_name("hosted_preview.py")
source = source_path.read_text(encoding="utf-8")
stripped = source.rstrip()
if stripped.endswith('"""'):
    stripped = stripped[:-3].rstrip() + "\n"

namespace = {"__name__": "hosted_preview_runtime"}
exec(compile(stripped, str(source_path), "exec"), namespace)

html = namespace["HTML"]
html = html.replace(
    '<button class="btn" onclick="sendMsg(',
    '<button class="btn" style="min-width:140px" onclick="sendMsg('
)
html = html.replace('">Send</button>', '">Send message</button>')
html = html.replace(
    'alert("Interview proposed")',
    'document.getElementById("nav-worker").textContent="Worker • interview waiting";alert("Interview proposed. Switch to Worker and accept it to confirm the meeting.")'
)
html = html.replace(
    '<button class="btn gold" onclick="submitCustomer()">Find someone to help</button>',
    '<button id="customer-submit" class="btn gold" onclick="submitCustomer()">Find someone to help</button>'
)
html = html.replace(
    'async function submitCustomer(){const b=await api(',
    'async function submitCustomer(){const btn=document.getElementById("customer-submit");btn.disabled=true;btn.textContent="Request sent";const b=await api('
)
namespace["HTML"] = html

app = namespace["app"]
