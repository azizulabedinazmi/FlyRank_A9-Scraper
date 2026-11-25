"""Generate docs/banner.svg: the scraping pipeline, animated (pure SVG + CSS, loops, no JS).

    python docs/make_banner.py docs/banner.svg
"""
import sys

OUT = sys.argv[1] if len(sys.argv) > 1 else "docs/banner.svg"
W, H, LOOP = 1280, 640, 14.0
END = (93.0, 98.0)
MONO = "Consolas,Menlo,monospace"
css = []


def appear(name: str, at: float) -> str:
    css.append(f"@keyframes {name}{{0%,{at:.1f}%{{opacity:0}}{at + 2:.1f}%,{END[0]}%{{opacity:1}}{END[1]}%,100%{{opacity:0}}}}"
               f".{name}{{animation:{name} {LOOP}s linear infinite}}")
    return name


def glow(name: str, at: float, color: str) -> str:
    """The stage's dot lights up when its turn comes, then stays lit."""
    css.append(f"@keyframes {name}{{0%,{at:.1f}%{{fill:#16302B}}{at + 1.5:.1f}%,{END[0]}%{{fill:{color}}}{END[1]}%,100%{{fill:#16302B}}}}"
               f".{name}{{animation:{name} {LOOP}s linear infinite}}")
    return name


# (stage, detail shown when it runs, start %, colour)
STAGES = [
    ("FETCH", "63 pages · named user-agent · 0.75 s apart", 4, "#6FDCA4"),
    ("EXTRACT", "8 raw fields per book, product area only", 30, "#8FB8FF"),
    ("NORMALIZE", '"£51.77"  →  51.77', 40, "#F2C66D"),
    ("VALIDATE", "Pydantic: 60 ✓   0 ✗  → errors.json", 50, "#6FDCA4"),
    ("STORE", "output/books.json · 60 unique · rerun = 60", 61, "#8FB8FF"),
    ("REPORT", "run-report.json · failed_pages: 1 · cache hits", 72, "#B9D3C8"),
]
rows = []
for i, (name, detail, at, col) in enumerate(STAGES):
    y = 152 + i * 74
    rows.append(
        f'<circle cx="736" cy="{y - 6}" r="9" class="{glow(f"g{i}", at, col)}" stroke="{col}" stroke-width="2"/>'
        + (f'<line x1="736" y1="{y + 4}" x2="736" y2="{y + 58}" stroke="#2B4A44" stroke-width="2"/>' if i < len(STAGES) - 1 else "")
        + f'<text x="760" y="{y}" class="stage" fill="{col}">{name}</text>'
        + f'<text x="760" y="{y + 24}" class="detail {appear(f"d{i}", at + 1)}">{detail}</text>'
    )

# fetch progress bar: fills during the FETCH stage (4% -> 28%), with a 404 blip on the way
css.append(f"@keyframes bar{{0%,4%{{width:0}}28%,{END[0]}%{{width:300px}}{END[1]}%,100%{{width:0}}}}"
           f".bar{{animation:bar {LOOP}s cubic-bezier(.3,.1,.3,1) infinite}}")
appear("skip", 17)

css.append("@media (prefers-reduced-motion: reduce){*{animation:none!important}"
           + "".join(f".d{i}{{opacity:1}}" for i in range(len(STAGES))) + ".skip{opacity:1}.bar{width:300px}"
           + "".join(f".g{i}{{fill:{c}}}" for i, (_, _, _, c) in enumerate(STAGES)) + "}")

chips, x = "", 72
for text in ["Requests", "Beautiful Soup", "Pydantic", "≥ 0.5 s delay"]:
    w = 20 + 10.2 * len(text)
    chips += (f'<rect x="{x + 1}" y="404" width="{w - 2}" height="34" rx="8" fill="none" stroke="#6FDCA4" stroke-width="2"/>'
              f'<text x="{x + w / 2}" y="427" text-anchor="middle" class="chip">{text}</text>')
    x += w + 10

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d">
<title id="t">The polite scraper: Books to Scrape to clean, validated JSON</title>
<desc id="d">Animated pipeline: fetch 63 pages politely (a made-up URL returns 404 and is skipped), extract eight raw
fields, normalize "£51.77" to 51.77, validate 60 records with Pydantic, store 60 unique records in books.json, and write
a run report. By Azizul Abedin Azmi, FlyRank verified.</desc>
<defs>
 <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M40 0H0V40" fill="none" stroke="#FFFFFF" stroke-opacity=".035"/></pattern>
 <radialGradient id="g1" cx="85%" cy="15%" r="45%"><stop offset="0" stop-color="#2ECC80" stop-opacity=".18"/><stop offset="1" stop-color="#2ECC80" stop-opacity="0"/></radialGradient>
 <radialGradient id="g2" cx="10%" cy="95%" r="50%"><stop offset="0" stop-color="#1A7A4A" stop-opacity=".35"/><stop offset="1" stop-color="#1A7A4A" stop-opacity="0"/></radialGradient>
 <style>
  text{{font-family:"Segoe UI",-apple-system,Roboto,Helvetica,Arial,sans-serif}}
  .eyebrow{{font-size:17px;letter-spacing:3px;font-weight:600;fill:#6FDCA4}}
  .h1{{font-size:84px;font-weight:800;fill:#fff;letter-spacing:-2px}}
  .sub{{font-size:25px;fill:#B9D3C8}}
  .chip{{font-family:{MONO};font-size:16px;font-weight:700;fill:#6FDCA4}}
  .name{{font-size:22px;font-weight:600;fill:#fff}}
  .stage{{font-family:{MONO};font-size:17px;font-weight:700;letter-spacing:1px}}
  .detail{{font-family:{MONO};font-size:15px;fill:#E8F3EE}}
  .mono{{font-family:{MONO}}}
  {"".join(css)}
 </style>
</defs>
<rect width="{W}" height="{H}" fill="#051F21"/><rect width="{W}" height="{H}" fill="url(#g2)"/>
<rect width="{W}" height="{H}" fill="url(#g1)"/><rect width="{W}" height="{H}" fill="url(#grid)"/>

<text x="72" y="98" class="eyebrow">FLYRANK AI INTERNSHIP · A9 · WEEK 5</text>
<text x="66" y="190" class="h1">The polite</text>
<text x="66" y="276" class="h1">scraper</text>
<text x="72" y="334" class="sub">3 catalogue pages → 60 books → clean,</text>
<text x="72" y="368" class="sub">validated JSON. Without being rude.</text>
{chips}
<text x="72" y="566" class="name">Azizul Abedin Azmi</text>
<circle cx="292" cy="559" r="3" fill="#4C7A6B"/>
<rect x="308" y="539" width="352" height="38" rx="19" fill="#fff"/>
<text x="332" y="564" font-size="17" font-weight="700" fill="#1A7A4A">✓</text>
<text x="352" y="564" font-size="16" font-weight="700" fill="#051F21">FlyRank verified</text>
<line x1="490" y1="549" x2="490" y2="567" stroke="#E4EAED"/>
<text x="500" y="563" fill="#6E7F84" style="font-family:Consolas,Menlo,monospace;font-size:13px">FR-D1-A84A9-AB526</text>

<rect x="700" y="64" width="516" height="550" rx="18" fill="#020E0F" fill-opacity=".78" stroke="#6FDCA4" stroke-opacity=".22"/>
<circle cx="726" cy="90" r="6" fill="#2B4A44"/><circle cx="746" cy="90" r="6" fill="#2B4A44"/><circle cx="766" cy="90" r="6" fill="#2B4A44"/>
<text x="1192" y="95" text-anchor="end" class="mono" font-size="13" fill="#6E8F85">python src/main.py</text>
{"".join(rows)}
<rect x="1080" y="128" width="0" height="0"/>
<rect x="890" y="130" width="300" height="8" rx="4" fill="#16302B"/>
<rect class="bar" x="890" y="130" width="0" height="8" rx="4" fill="#6FDCA4"/>
<g class="skip"><rect x="1092" y="104" width="98" height="20" rx="10" fill="#3A2A2C"/>
 <text x="1141" y="118" text-anchor="middle" class="mono" font-size="12" font-weight="700" fill="#FF8A8E">404 · skipped</text></g>
</svg>
'''
open(OUT, "w", encoding="utf-8", newline="\n").write(svg)
print("wrote", OUT, len(svg), "bytes")
