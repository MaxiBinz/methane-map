"""Draw the GitHub overview from retained results; no synthetic observations."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
summary = json.loads((ROOT / "outputs/run_summary.json").read_text())
candidates = json.loads((ROOT / "outputs/candidates.json").read_text())
assert len(candidates) == summary["screened_components"]
assert sum(c["category"] == "E" for c in candidates) == summary["category_E"]
assert sum(c["category"] == "C" for c in candidates) == summary["category_C"]

parts = ['''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="480" viewBox="0 0 1200 480" role="img" aria-labelledby="title description">
<title id="title">Methane Map: twenty scenes, fourteen assessed components, no established new source</title>
<desc id="description">Results of the fixed northern Delaware Basin study. Six components have published-observation neighborhood associations and eight remain ambiguous. The known-example recovery gate failed. The map shows actual enhancement centroids, not emitters.</desc>
<rect width="1200" height="480" rx="18" fill="#101c2a"/>
<g font-family="Arial,Helvetica,sans-serif">
<text x="48" y="53" fill="#78c8dc" font-size="16" letter-spacing="3">METHANE MAP · REPRODUCIBLE RESEARCH</text>
<text x="48" y="109" fill="#ffffff" font-size="34" font-weight="700">A search that tested</text>
<text x="48" y="151" fill="#ffffff" font-size="34" font-weight="700">its own detector.</text>
<text x="48" y="190" fill="#bdcad7" font-size="18">NASA EMIT · Northern Delaware Basin · 2023–2025</text>
<path d="M48 218H685" stroke="#344252"/>
''']
for x, value, label in [(48, summary["scenes_analyzed"], "FULL SCENES"),
                         (264, summary["screened_components"], "COMPONENTS"),
                         (480, summary["independently_corroborated_new_sources"], "NEW SOURCES ESTABLISHED")]:
    parts.append(f'<text x="{x}" y="283" fill="#ffffff" font-size="47" font-weight="700">{value}</text>')
    parts.append(f'<text x="{x}" y="312" fill="#bdcad7" font-size="13" letter-spacing="1">{label}</text>')
parts.append('''<text x="48" y="365" fill="#f1bc70" font-size="19" font-weight="700">Known-example recovery gate: not met</text>
<text x="48" y="398" fill="#bdcad7" font-size="17">6 documented associations · 8 ambiguous responses</text>
<text x="48" y="429" fill="#bdcad7" font-size="16">No facility attribution or emission-rate claim.</text>
<text x="796" y="48" fill="#bdcad7" font-size="14">ACTUAL ENHANCEMENT CENTROIDS</text>
''')
x0, y0, width, height = 804, 70, 330, 322
def xy(lon, lat):
    return x0 + (lon + 104.5) / 2 * width, y0 + (33 - lat) / 2 * height
for lon in [-104.5, -104, -103.5, -103, -102.5]:
    x, _ = xy(lon, 31)
    parts.append(f'<path d="M{x} {y0}V{y0+height}" stroke="#344252"/>')
    if lon in [-104.5, -103.5, -102.5]:
        parts.append(f'<text x="{x}" y="413" text-anchor="middle" fill="#bdcad7" font-size="12">{abs(lon)}°W</text>')
for lat in [31, 31.5, 32, 32.5, 33]:
    _, y = xy(-104.5, lat)
    parts.append(f'<path d="M{x0} {y}H{x0+width}" stroke="#344252"/>')
    parts.append(f'<text x="{x0-10}" y="{y+4}" text-anchor="end" fill="#bdcad7" font-size="12">{lat}°N</text>')
for candidate in candidates:
    x, y = xy(candidate["longitude"], candidate["latitude"])
    color = "#78c8dc" if candidate["category"] == "E" else "#f1bc70"
    parts.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="5" fill="#101c2a" stroke="{color}" stroke-width="2"><title>{candidate["candidate_id"]}: Category {candidate["category"]}</title></circle>')
parts.append('''<text x="804" y="445" fill="#bdcad7" font-size="13">Centroids are not emitting-source locations.</text>
</g></svg>''')
target = ROOT / "docs/assets/investigation-overview.svg"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text("\n".join(parts) + "\n")
print(target.relative_to(ROOT))
