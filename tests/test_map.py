#!/usr/bin/env python3
"""Interaction tests for the Proposed TPS School Closures map.

Runs the real page (vendored MapLibre GL JS) in headless Chromium against a local
static server. `?style=blank` swaps CARTO's basemap for a flat background so the
suite runs offline; everything else — data, layers, popups, controls — is live.

    pip install playwright && playwright install chromium
    python3 tests/test_map.py
"""
import http.server, json, pathlib, socketserver, sys, threading, time
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
PORT = 8765
results = []

def check(name, cond, detail=""):
    results.append((bool(cond), name, detail))
    print(("  PASS  " if cond else "  FAIL  ") + name + ((" :: " + str(detail)) if detail and not cond else ""))

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass

def serve():
    handler = lambda *a, **k: Quiet(*a, directory=str(ROOT), **k)
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), handler, bind_and_activate=False)
    httpd.allow_reuse_address = True
    httpd.server_bind(); httpd.server_activate()
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd

def main():
    httpd = serve()
    url = f"http://127.0.0.1:{PORT}/index.html?style=blank"
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"])
        pg = b.new_page(viewport={"width": 1400, "height": 1000})
        errs = []
        NOISE = ("ERR_TUNNEL", "ERR_NAME_NOT_RESOLVED", "Failed to load resource", "net::", "cartocdn", "fonts.g", "AbortError")
        def note(m):
            if not any(k in m for k in NOISE): errs.append(m)
        pg.on("pageerror", lambda e: note(str(e)))
        pg.on("console", lambda m: note("console.error: " + m.text) if m.type == "error" else None)
        pg.goto(url)
        pg.wait_for_function("window.__map && window.__map.loaded() && window.__map.getLayer('open-dot')", timeout=30000)
        pg.wait_for_timeout(600)

        def layer_vis(id_): return pg.evaluate("(id)=>{const l=window.__map.getLayer(id);return l?window.__map.getLayoutProperty(id,'visibility')||'visible':null}", id_)
        def zoom(): return pg.evaluate("()=>window.__map.getZoom()")
        def rendered(layer): return pg.evaluate("(l)=>window.__map.queryRenderedFeatures({layers:[l]}).length", layer)
        def click_layer_feature(layer, prop, val):
            return pg.evaluate("""([l,prop,val])=>{const m=window.__map;
                const f=m.querySourceFeatures('schools').find(f=>f.properties[prop]===val);
                const p=m.project([f.geometry.coordinates[0],f.geometry.coordinates[1]]);
                const r=m.getCanvas().getBoundingClientRect(); return [r.left+p.x, r.top+p.y];}""", [layer, prop, val])

        print("\n--- structure ---")
        check("no JS errors on load", not errs, errs)
        check("map reached the loaded state", pg.evaluate("()=>window.__map.loaded()"))
        for lid in ["tract-fill", "tract-line", "tract-sel", "zip-fill", "zip-line", "zip-sel", "zip-label", "open-dot", "chg-dot"]:
            check(f"layer {lid} exists", pg.evaluate("(id)=>!!window.__map.getLayer(id)", lid))
        check("17 numbered pins as DOM markers", pg.eval_on_selector_all(".pin", "e=>e.length") == 17)
        check("pins numbered 1..17 in order", pg.eval_on_selector_all(".pin", "e=>e.map(x=>+x.textContent)") == list(range(1, 18)))
        check("64 open sites in the data", pg.evaluate("()=>window.__data.schools.features.filter(f=>f.properties.status==='open').length") == 64)
        check("4 building-change sites in the data", pg.evaluate("()=>window.__data.schools.features.filter(f=>f.properties.status==='change').length") == 4)
        check("17 closures in the data", pg.evaluate("()=>window.__data.schools.features.filter(f=>f.properties.status==='closure').length") == 17)
        check("every school has a tract GEOID that exists in the tract data", pg.evaluate("()=>{const g=new Set(window.__data.tracts.features.map(f=>f.properties.geoid));return window.__data.schools.features.every(f=>g.has(f.properties.tract_geoid));}"))
        check("213 tracts in the data", pg.evaluate("()=>window.__data.tracts.features.length") == 213)
        check("38 ZIPs in the data", pg.evaluate("()=>window.__data.zips.features.length") == 38)
        check("tract layer visible by default", layer_vis("tract-fill") == "visible")
        check("ZIP layer hidden by default", layer_vis("zip-fill") == "none")
        check("17 rows in the closure list", pg.eval_on_selector_all("#roll li.it", "e=>e.length") == 17)
        check("4 rows in the building-change list", pg.eval_on_selector_all("#chgroll li.it", "e=>e.length") == 4)

        print("\n--- layer order: shading below basemap labels, sites above ---")
        order = pg.evaluate("()=>window.__map.getStyle().layers.map(l=>l.id)")
        check("open-dot draws above tract-fill", order.index("open-dot") > order.index("tract-fill"))
        check("chg-dot draws above open-dot", order.index("chg-dot") > order.index("open-dot"))
        check("selection outline draws above fill", order.index("tract-sel") > order.index("tract-fill"))

        print("\n--- hover ---")
        pt = click_layer_feature("open-dot", "name", "Carnegie Elementary")
        pg.mouse.move(pt[0], pt[1]); pg.wait_for_timeout(200)
        t = pg.eval_on_selector_all(".tip", "e=>e.map(x=>x.innerText).join('')")
        check("hovering a remaining site shows its name and address", "Carnegie" in t and "56th" in t, t[:80])
        check("cursor is 'help' over a remaining site", pg.evaluate("()=>window.__map.getCanvas().style.cursor") == "help")
        pt = click_layer_feature("chg-dot", "name", "S.O.A.R.")
        pg.mouse.move(pt[0], pt[1]); pg.wait_for_timeout(200)
        t = pg.eval_on_selector_all(".tip", "e=>e.map(x=>x.innerText).join('')")
        check("hovering a change site shows its building note", "S.O.A.R." in t and "Greenwood" in t, t[:80])
        # a bare tract
        spot = pg.evaluate("""()=>{const m=window.__map,c=m.getCanvas().getBoundingClientRect();
          for(let y=40;y<c.height-40;y+=12)for(let x=40;x<c.width-40;x+=12){
            if(m.queryRenderedFeatures([x,y],{layers:['open-dot','chg-dot']}).length) continue;
            if(document.elementFromPoint(c.left+x,c.top+y)?.closest('.pin')) continue;
            const f=m.queryRenderedFeatures([x,y],{layers:['tract-fill']});
            if(f.length&&f[0].properties.median_hh_income) return [c.left+x,c.top+y];} return null;}""")
        check("found a bare tract to hover", spot is not None)
        if spot:
            pg.mouse.move(spot[0], spot[1]); pg.wait_for_timeout(200)
            t = pg.eval_on_selector_all(".tip", "e=>e.map(x=>x.innerText).join('')").upper()
            check("tract hover shows tract, county, income, poverty", all(k in t for k in ("TRACT", "COUNTY", "$", "POVERTY")), t[:90])
        pg.mouse.move(5, 5); pg.wait_for_timeout(150)

        print("\n--- cards ---")
        badc = []
        for i in range(17):
            pg.keyboard.press("Escape"); pg.wait_for_timeout(60)
            pg.click("#zrst"); pg.wait_for_timeout(700)
            el = pg.query_selector_all(".pin")[i]
            num = el.text_content().strip()
            el.click(); pg.wait_for_timeout(250)
            n = pg.eval_on_selector_all(".pop", "e=>e.length")
            body = pg.eval_on_selector_all(".pop", "e=>e.map(x=>x.innerText).join('')").upper()
            badge = pg.eval_on_selector_all(".pop .pop-n", "e=>e.map(x=>x.textContent)")
            if n != 1 or badge != [num] or "ADDRESS" not in body or "TRACT" not in body or "FEEDER" not in body:
                badc.append((num, n, badge, body[:60]))
        check("each of the 17 pins opens its own card with address, tract and feeder rows", not badc, badc[:4])
        check("pin click marks the pin selected", pg.eval_on_selector_all(".pin.on", "e=>e.length") == 1)
        check("pin click highlights its sidebar row", pg.eval_on_selector_all("#roll li.it.on", "e=>e.length") == 1)
        check("selected tract is outlined", pg.evaluate("()=>JSON.stringify(window.__map.getFilter('tract-sel'))").find("__none__") < 0)
        pg.click(".pop .pop-x"); pg.wait_for_timeout(150)
        check("× closes the card", pg.eval_on_selector_all(".pop", "e=>e.length") == 0)
        pg.query_selector_all(".pin")[3].click(); pg.wait_for_timeout(200)
        pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
        check("Escape closes the card", pg.eval_on_selector_all(".pop", "e=>e.length") == 0)
        pg.query_selector_all(".pin")[3].click(); pg.wait_for_timeout(200)
        c = pg.evaluate("()=>{const r=window.__map.getCanvas().getBoundingClientRect();return [r.left+r.width*0.9,r.top+r.height*0.92]}")
        pg.mouse.click(c[0], c[1]); pg.wait_for_timeout(200)
        check("clicking empty map closes the card", pg.eval_on_selector_all(".pop", "e=>e.length") == 0)

        # content checks against the source figures
        DETAIL = [("Thoreau Demonstration Academy", ["MAGNET", "53%", "2021 BOND", "REPURPOSED"]),
                  ("Central Middle School", ["200 STUDENTS", "230 MIDDLE", "TULSA VIRTUAL ACADEMY", "OSAGE COUNTY"]),
                  ("Marshall Elementary", ["MEMORIAL", "$33,430", "47.2% BELOW POVERTY", "2026 BOND"]),
                  ("Anderson Elementary", ["FELICITAS MENDEZ", "ABOVE 60%"]),
                  ("Tulsa MET MS/HS", ["ALTERNATIVE", "125 STUDENTS", "PROJECT SCHOOLHOUSE"])]
        badd = []
        for nm, frags in DETAIL:
            pg.keyboard.press("Escape")
            pg.evaluate("(nm)=>{[...document.querySelectorAll('.pin')].find(p=>p.getAttribute('aria-label').startsWith(nm)).click();}", nm)
            pg.wait_for_timeout(200)
            body = pg.eval_on_selector_all(".pop", "e=>e.map(x=>x.innerText).join('')").upper()
            miss = [f for f in frags if f not in body]
            if miss: badd.append((nm, miss))
        check("sampled cards carry their sourced figures", not badd, badd)
        pg.keyboard.press("Escape")

        print("\n--- building-change sites ---")
        badch = []
        for i in range(4):
            pg.keyboard.press("Escape"); pg.wait_for_timeout(60)
            row = pg.query_selector_all("#chgroll li.it")[i]
            nm = row.eval_on_selector(".nm", "e=>e.childNodes[0].textContent")
            row.click(); pg.wait_for_timeout(900)
            body = pg.eval_on_selector_all(".pop", "e=>e.map(x=>x.innerText).join('')")
            alt = pg.eval_on_selector_all(".pop .pop-lv.alt", "e=>e.length") == 1
            if nm not in body or "BUILDING CHANGE" not in body.upper() or not alt: badch.append((nm, alt, body[:60]))
        check("each building-change row opens a change card", not badch, badch)
        pg.keyboard.press("Escape")
        pg.evaluate("()=>[...document.querySelectorAll('#chgroll li.it')].find(l=>l.querySelector('.nm').childNodes[0].textContent.startsWith('Tulsa Virtual')).click()")
        pg.wait_for_timeout(900)
        body = pg.eval_on_selector_all(".pop", "e=>e.map(x=>x.innerText).join('')")
        check("Tulsa Virtual Academy's card names the two schools under its marker",
              "New Vision Academy" in body and "North Star Academy" in body, body[:120])
        pg.keyboard.press("Escape"); pg.click("#zrst"); pg.wait_for_timeout(700)
        pt = click_layer_feature("chg-dot", "name", "S.O.A.R.")
        pg.mouse.click(pt[0], pt[1]); pg.wait_for_timeout(250)
        body = pg.eval_on_selector_all(".pop", "e=>e.map(x=>x.innerText).join('')")
        check("clicking a change marker on the map opens its card", "S.O.A.R." in body, body[:60])
        check("selected change marker is drawn in the selected state",
              pg.evaluate("()=>window.__map.getFeatureState({source:'schools',id:'soar'}).sel===true"))
        pg.keyboard.press("Escape")

        print("\n--- sidebar row → flyTo ---")
        z0 = zoom()
        pg.query_selector_all("#roll li.it")[9].click(); pg.wait_for_timeout(1000)
        check("closure row zooms in", zoom() > z0, (z0, zoom()))
        check("closure row opens its card", pg.eval_on_selector_all(".pop", "e=>e.length") == 1)
        pg.click("#zrst"); pg.wait_for_timeout(800)
        check("Fit returns to the home extent", abs(zoom() - z0) < 0.05, (z0, zoom()))
        check("Fit clears the card", pg.eval_on_selector_all(".pop", "e=>e.length") == 0)

        print("\n--- layer toggles ---")
        pg.click("#u-zip + span"); pg.wait_for_timeout(200)
        check("ZIP radio shows the ZIP layer", layer_vis("zip-fill") == "visible" and layer_vis("tract-fill") == "none")
        pt = click_layer_feature("open-dot", "name", "Carnegie Elementary")
        pg.mouse.move(pt[0] + 60, pt[1] + 60); pg.wait_for_timeout(200)
        t = pg.eval_on_selector_all(".tip", "e=>e.map(x=>x.innerText).join('')").upper()
        check("ZIP hover shows a ZIP figure", "ZIP" in t and "$" in t, t[:60])
        pg.click("#u-tract + span"); pg.wait_for_timeout(200)
        check("tract radio restores the tract layer", layer_vis("tract-fill") == "visible" and layer_vis("zip-fill") == "none")
        pg.uncheck("#t-inc"); pg.wait_for_timeout(150)
        check("income OFF makes the fill transparent", pg.evaluate("()=>window.__map.getPaintProperty('tract-fill','fill-opacity')") == 0)
        pg.check("#t-inc"); pg.wait_for_timeout(150)
        check("income ON restores it", pg.evaluate("()=>window.__map.getPaintProperty('tract-fill','fill-opacity')") > 0)
        pg.uncheck("#t-open"); pg.wait_for_timeout(150)
        check("remaining-sites OFF hides open-dot", layer_vis("open-dot") == "none")
        pg.check("#t-open"); pg.wait_for_timeout(150)
        check("remaining-sites ON shows open-dot", layer_vis("open-dot") == "visible")
        pg.query_selector_all("#chgroll li.it")[0].click(); pg.wait_for_timeout(600)
        pg.uncheck("#t-chg"); pg.wait_for_timeout(150)
        check("building-changes OFF hides chg-dot", layer_vis("chg-dot") == "none")
        check("…and closes a change card that was open", pg.eval_on_selector_all(".pop", "e=>e.length") == 0)
        pg.check("#t-chg"); pg.wait_for_timeout(150)
        pg.uncheck("#t-zip"); pg.wait_for_timeout(150)
        check("ZIP labels OFF hides zip-label", layer_vis("zip-label") == "none")
        pg.check("#t-zip"); pg.wait_for_timeout(150)
        pg.click("#zrst"); pg.wait_for_timeout(700)

        print("\n--- zoom / pan ---")
        z0 = zoom()
        c = pg.evaluate("()=>{const r=window.__map.getCanvas().getBoundingClientRect();return [r.left+r.width/2,r.top+r.height/2]}")
        pg.mouse.move(c[0], c[1]); pg.mouse.wheel(0, -300); pg.wait_for_timeout(700)
        check("wheel zooms in", zoom() > z0, (z0, zoom()))
        pg.mouse.move(c[0], c[1]); pg.mouse.down()
        for k in range(1, 8): pg.mouse.move(c[0] - 15 * k, c[1] - 10 * k); pg.wait_for_timeout(16)
        pg.mouse.up(); pg.wait_for_timeout(300)
        check("drag pans without opening a card", pg.eval_on_selector_all(".pop", "e=>e.length") == 0)
        pw_px = pg.eval_on_selector(".pin", "e=>e.getBoundingClientRect().width")
        check("pins keep a constant screen size while zoomed", 22 <= pw_px <= 30, pw_px)
        pg.click("#zrst"); pg.wait_for_timeout(700)

        print("\n--- keyboard ---")
        pg.evaluate("()=>document.querySelector('.pin').focus()")
        pg.keyboard.press("Enter"); pg.wait_for_timeout(200)
        check("Enter on a focused pin opens its card", pg.eval_on_selector_all(".pop", "e=>e.length") == 1)
        pg.keyboard.press("Escape")

        print("\n--- phone (390px) ---")
        pg2 = b.new_page(viewport={"width": 390, "height": 844})
        e2 = []
        pg2.on("pageerror", lambda e: e2.append(str(e)))
        pg2.goto(url)
        pg2.wait_for_function("window.__map && window.__map.loaded() && window.__map.getLayer('open-dot')", timeout=30000)
        pg2.wait_for_timeout(500)
        check("phone: no JS errors", not e2, e2)
        check("phone: no horizontal page scroll", pg2.evaluate("document.body.scrollWidth<=document.body.clientWidth"))
        badp = []
        for i in (0, 5, 10, 16):          # pins at different corners of the extent
            pg2.keyboard.press("Escape"); pg2.click("#zrst"); pg2.wait_for_timeout(700)
            pg2.query_selector_all(".pin")[i].click(); pg2.wait_for_timeout(700)
            ok = pg2.evaluate("()=>{const p=document.querySelector('.pop .maplibregl-popup-content');if(!p)return 'nocard';const r=p.getBoundingClientRect();const m=document.getElementById('map').getBoundingClientRect();return (r.left>=m.left-1&&r.right<=m.right+1&&r.top>=m.top-1&&r.bottom<=m.bottom+1)||[r.left,r.right,r.top,r.bottom];}")
            if ok is not True: badp.append((i, ok))
        check("phone: pin opens a card", pg2.eval_on_selector_all(".pop", "e=>e.length") == 1)
        check("phone: card stays inside the map for pins at every corner", not badp, badp)
        pg2.close()

        print("\n--- dark theme ---")
        pg3 = b.new_page(viewport={"width": 1280, "height": 900}, color_scheme="dark")
        e3 = []
        pg3.on("pageerror", lambda e: e3.append(str(e)))
        pg3.goto(url)
        pg3.wait_for_function("window.__map && window.__map.loaded() && window.__map.getLayer('open-dot')", timeout=30000)
        pg3.wait_for_timeout(400)
        def lum(css):
            v = [int(x) for x in css[css.index("(") + 1:css.index(")")].split(",")[:3]]
            return (0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]) / 255
        check("dark: body ground is dark", lum(pg3.eval_on_selector("body", "e=>getComputedStyle(e).backgroundColor")) < 0.25)
        check("dark: no JS errors", not e3, e3)
        pg3.close()

        check("no JS errors accumulated across the run", not errs, errs[:3])
        b.close()
    httpd.shutdown()

    fails = [r for r in results if not r[0]]
    print("\n" + "=" * 58)
    print("%d passed, %d failed, of %d checks" % (len(results) - len(fails), len(fails), len(results)))
    for _, name, detail in fails: print("  FAILED: %s  %s" % (name, detail))
    print("ALL GREEN" if not fails else "")
    sys.exit(1 if fails else 0)

if __name__ == "__main__":
    main()
