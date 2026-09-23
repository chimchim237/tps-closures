"""Render og-image.png (1200x630 at 2x = 2400x1260) from the page itself in headless Chromium.

Expects this layout, one level above the repo:  <parent>/repo/  (this checkout, any name works if
you adjust REPO below) and <parent>/fonts/ holding ZillaSlab-Bold.ttf, Archivo[wdth,wght].ttf and
ArchivoNarrow[wght].ttf (SIL OFL; from github.com/google/fonts, ofl/). The page runs with
?style=blank, so no basemap tiles are needed.

    pip install playwright && playwright install chromium
    python3 tools/make_og_image.py
"""
import http.server, socketserver, threading, pathlib, sys
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[2]   # serves <repo parent>/ so /repo and /fonts resolve; see docstring
PORT = 8812
OUT = pathlib.Path(__file__).resolve().parents[1] / 'og-image.png'

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
httpd = socketserver.TCPServer(("127.0.0.1", PORT), lambda *a, **k: Quiet(*a, directory=str(ROOT), **k), bind_and_activate=False)
httpd.allow_reuse_address = True; httpd.server_bind(); httpd.server_activate()
threading.Thread(target=httpd.serve_forever, daemon=True).start()

CSS = """
@font-face{font-family:"Zilla Slab";font-weight:700;src:url(/fonts/ZillaSlab-Bold.ttf)}
@font-face{font-family:"Archivo";font-weight:100 900;src:url("/fonts/Archivo[wdth,wght].ttf")}
@font-face{font-family:"Archivo Narrow";font-weight:100 900;src:url("/fonts/ArchivoNarrow[wght].ttf")}
body{overflow:hidden;margin:0}
header.mast, .side, footer, #zrst, .maplibregl-ctrl-top-right, .maplibregl-ctrl-bottom-left, .maplibregl-ctrl-bottom-right{display:none!important}
.wrap.grid{display:block;padding:0;max-width:none}
.plate{position:fixed;left:0;top:0;width:1200px;height:630px;border:0;border-radius:0;z-index:9;overflow:hidden}
#map{width:1200px;height:630px}
#og{position:absolute;left:0;top:0;bottom:0;width:430px;z-index:5;background:var(--paper);border-right:1px solid var(--rule);
  padding:44px 40px;display:flex;flex-direction:column;box-sizing:border-box;font-family:"Archivo",sans-serif;color:var(--ink)}
#og .k{font-family:"Archivo Narrow",sans-serif;text-transform:uppercase;letter-spacing:.12em;font-size:13px;color:var(--ink-3);font-weight:700}
#og h1{font-family:"Zilla Slab",serif;font-weight:700;font-size:54px;line-height:1.0;margin:14px 0 18px;letter-spacing:-.01em}
#og h1 em{font-style:normal;color:var(--signal)}
#og p{font-size:16.5px;line-height:1.4;color:var(--ink-2);margin:0}
#og .st{display:flex;gap:26px;margin-top:auto;font-family:"Archivo Narrow",sans-serif;text-transform:uppercase;letter-spacing:.08em;font-size:11.5px;color:var(--ink-3)}
#og .st b{display:block;font-family:"Archivo",sans-serif;font-size:30px;letter-spacing:0;color:var(--ink);font-variant-numeric:tabular-nums;font-weight:700;line-height:1.1}
#og .st .hot b{color:var(--signal)}
#og .u{margin-top:22px;font-size:13px;color:var(--ink-2)}
#og .u b{color:var(--ink);font-weight:600}
#leg{position:absolute;right:14px;bottom:12px;z-index:5;background:rgba(251,248,242,.92);border:1px solid var(--rule);border-radius:3px;
  padding:8px 10px;font-family:"Archivo",sans-serif;font-size:11.5px;color:var(--ink-2);display:flex;gap:14px;align-items:center}
#leg i{display:inline-block;width:11px;height:11px;border-radius:50%;vertical-align:-1px;margin-right:5px}
#ramp{position:absolute;left:446px;bottom:12px;z-index:5;background:rgba(251,248,242,.92);border:1px solid var(--rule);border-radius:3px;
  padding:7px 10px 6px;font-family:"Archivo Narrow",sans-serif;font-size:10.5px;color:var(--ink-3);text-transform:uppercase;letter-spacing:.06em}
#ramp .r{display:flex;height:8px;width:160px;margin:4px 0 3px}
#ramp .r i{flex:1}
#ramp .ax{display:flex;justify-content:space-between}
"""
HTML = """<div id="og">
<div class="k">Tulsa Public Schools &middot; Budget proposal, September 2026</div>
<h1>Proposed TPS School <em>Closures</em></h1>
<p>Seventeen campuses named for closure, mapped against median household income by census tract, with where each school's students would go.</p>
<div class="st"><div class="hot"><b>17</b>proposed closures</div><div><b>4,726</b>students affected</div><div><b>$12M</b>cuts sought</div></div>
<div class="u"><b>earthseed.technology/tps-closures</b></div>
</div>
<div id="ramp">Median household income<div class="r"><i style="background:var(--c0)"></i><i style="background:var(--c1)"></i><i style="background:var(--c2)"></i><i style="background:var(--c3)"></i><i style="background:var(--c4)"></i><i style="background:var(--c5)"></i><i style="background:var(--c6)"></i></div><div class="ax"><span>&lt;$35k</span><span>$95k+</span></div></div>
<div id="leg"><span><i style="background:var(--signal)"></i>Proposed for closure</span><span><i style="background:var(--site)"></i>Remaining site</span></div>
"""

with sync_playwright() as pw:
    b = pw.chromium.launch(args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"])
    pg = b.new_page(viewport={"width": 1200, "height": 630}, device_scale_factor=2)
    REPO = pathlib.Path(__file__).resolve().parents[1].name
    pg.goto(f"http://127.0.0.1:{PORT}/{REPO}/index.html?style=blank")
    pg.wait_for_function("window.__map && window.__map.loaded() && window.__map.getLayer('open-dot')", timeout=30000)
    pg.evaluate("""([css, html]) => {
      document.documentElement.setAttribute('data-theme', 'light');
      const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);
      document.querySelector('.plate').insertAdjacentHTML('beforeend', html);
      document.getElementById('t-zip').click();
    }""", [CSS, HTML])
    pg.wait_for_timeout(800)   # theme swap rebuilds the style
    pg.wait_for_function("window.__map.getLayer('open-dot')", timeout=30000)
    pg.evaluate("""() => {
      const m = window.__map; m.resize();
      const c = window.__data.schools.features.filter(f => f.properties.status === 'closure').map(f => f.geometry.coordinates);
      const b = c.reduce((r, p) => [[Math.min(r[0][0], p[0]), Math.min(r[0][1], p[1])], [Math.max(r[1][0], p[0]), Math.max(r[1][1], p[1])]], [[180, 90], [-180, -90]]);
      m.fitBounds(b, { padding: { top: 44, right: 44, bottom: 96, left: 474 }, duration: 0 });
    }""")
    pg.wait_for_timeout(1500)
    pg.evaluate("() => document.fonts.ready")
    ok = pg.evaluate("() => ['700 20px \"Zilla Slab\"','700 20px Archivo','700 20px \"Archivo Narrow\"'].map(f => document.fonts.check(f))")
    print("fonts loaded:", ok)
    pg.screenshot(path=str(OUT), clip={"x": 0, "y": 0, "width": 1200, "height": 630})
    b.close()
print("wrote", OUT)
