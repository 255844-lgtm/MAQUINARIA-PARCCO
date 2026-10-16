#!/usr/bin/env python3
"""Genera control-maquinaria-parcco.html: el dashboard en un solo archivo, con datos y d3 incluidos.
Uso: python3 build_html.py --datos DIR_JSON --pagina index.html --d3 d3.min.js --out salida.html
"""
import argparse, json, re

TOKENS = """
:root{
 --font-anthropic-sans:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;
 --font-anthropic-serif:Georgia,"Times New Roman",serif;
 --cds-font-size-caption:12.5px;--cds-font-size-body:14.5px;--cds-font-size-heading:16.5px;--cds-font-size-title:28px;
 --cds-font-weight-medium:600;
 --cds-gap-xs:4px;--cds-gap-sm:8px;--cds-gap-md:12px;--cds-gap-lg:20px;--cds-gap-xl:32px;
 --cds-pad-xs:4px;--cds-pad-sm:8px;--cds-pad-md:14px;--cds-pad-lg:18px;--cds-pad-xl:28px;
 --cds-radius:10px;--cds-dur-slow:240ms;--cds-ease-out:cubic-bezier(.2,.7,.2,1);
 --color-fg:#1f1e1c;--color-fg-muted:#6b6862;--color-bg:#f6f5f2;--color-panel:#ffffff;--color-border-line:#e3e0da;
 --color-ok:#2f7d4f;--color-warn:#b26a00;--color-bad:#c0392b;
 --cds-chart-muted:#a8a49c;--cds-chart-status-critical:#d0443a;--cds-chart-grid:#ebe8e2;--cds-chart-axis:#c9c5bd;--cds-chart-reference:#7d7a73;
 --cds-surface-popover:#ffffff;--cds-border:#dcd8d0;--cds-shadow-popover:0 6px 20px rgba(0,0,0,.12);--cds-text-secondary:#6b6862;
 --s1:#2f6fd6;--s2:#e08a1e;--s3:#2a9d7e;--s4:#9b59b6;--s5:#d0506f;--s6:#5a8f29;--s7:#8a6d3b;--s8:#4aa3c7;
}
@media (prefers-color-scheme: dark){:root{
 --color-fg:#ecebe8;--color-fg-muted:#a9a6a0;--color-bg:#1b1a19;--color-panel:#252423;--color-border-line:#3a3836;
 --color-ok:#5cc286;--color-warn:#e9a23b;--color-bad:#ef6a5e;
 --cds-chart-muted:#6f6b65;--cds-chart-status-critical:#ef6a5e;--cds-chart-grid:#33312f;--cds-chart-axis:#4a4845;--cds-chart-reference:#9a968f;
 --cds-surface-popover:#2e2d2b;--cds-border:#45433f;--cds-shadow-popover:0 6px 20px rgba(0,0,0,.45);--cds-text-secondary:#a9a6a0;
 --s1:#6b9cf0;--s2:#f0a64a;--s3:#4cc3a0;--s4:#bb86d6;--s5:#ec7c97;--s6:#8cc35a;--s7:#c4a06a;--s8:#75c3e2;
}}
html,body{margin:0;background:var(--color-bg);color:var(--color-fg);font-family:var(--font-anthropic-sans);font-size:var(--cds-font-size-body);line-height:1.45}
#dash-root{max-width:1240px;margin:0 auto;padding:20px 16px 40px}
.dash-skeleton{}
.mq-foot{margin-top:28px;font-size:var(--cds-font-size-caption);color:var(--color-fg-muted)}
"""

SHIM = r"""
window.dash = (function () {
  const DATA = window.__DATOS__;
  const calcs = {}, cache = {}, subs = [];
  const leerHash = () => { const m = /(?:^|&)m=([^&]+)/.exec(location.hash.slice(1)); return { maq: m ? decodeURIComponent(m[1]) : null }; };
  let params = leerHash();
  function data(id) {
    if (cache[id]) return cache[id];
    if (DATA[id]) return (cache[id] = { status: 'ok', data: DATA[id], refreshing: false, meta: [] });
    const c = calcs[id];
    if (!c) return { status: 'missing', data: [], meta: [] };
    try { cache[id] = { status: 'ok', data: c.fn(...c.inputs.map((i) => data(i).data)), refreshing: false, meta: [] }; }
    catch (e) { console.error(e); cache[id] = { status: 'error', data: [], message: String(e), meta: [] }; }
    return cache[id];
  }
  const run = () => subs.forEach((f) => { try { f(); } catch (e) { console.error(e); } });
  let t; window.addEventListener('resize', () => { clearTimeout(t); t = setTimeout(run, 150); });
  window.addEventListener('hashchange', () => { const p = leerHash(); if (p.maq !== params.maq) { params = p; run(); } });
  return {
    calc: (id, o) => { calcs[id] = o; },
    loader: () => {},
    data,
    onData: (f) => { subs.push(f); try { f(); } catch (e) { console.error(e); } },
    params: () => params,
    setParams: (p) => {
      params = Object.assign({}, params, p);
      const h = params.maq ? '#m=' + encodeURIComponent(params.maq) : '';
      if (location.hash !== h) history.pushState(null, '', h || location.pathname + location.search);
      run();
    },
    resetParams: () => { params = { maq: null }; run(); },
    refresh: () => {}, setLink: () => {},
    colors: ['var(--s1)', 'var(--s2)', 'var(--s3)', 'var(--s4)', 'var(--s5)', 'var(--s6)', 'var(--s7)', 'var(--s8)'],
  };
})();
window.addEventListener('popstate', () => window.dispatchEvent(new HashChangeEvent('hashchange')));
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--datos', required=True); ap.add_argument('--pagina', required=True)
    ap.add_argument('--d3', required=True); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    datos = {k: json.load(open(f'{a.datos}/{k}.json', encoding='utf-8')) for k in ('maquinas', 'partes', 'actualizacion')}
    page = open(a.pagina, encoding='utf-8').read()
    # En un archivo suelto, los colores con var() van como estilo, no como atributo SVG
    page = page.replace(" · se actualiza cada día a las 6:00 a. m.", "")
    page = re.sub(r"\.attr\('(fill|stroke)',", r".style('\1',", page)
    d3 = open(a.d3, encoding='utf-8').read()
    datos_js = json.dumps(datos, ensure_ascii=False).replace('</', '<\\/')
    html = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Control de Maquinaria – Presa Parcco</title>
<style>{TOKENS}</style>
<script>{d3}</script>
<script>window.__DATOS__ = {datos_js};</script>
<script>{SHIM}</script>
</head><body>
<div id="dash-root">
{page}
<p class="mq-foot">Página generada a partir de MAQUINARIA PARCCO.xlsx · Obra: Mejoramiento y Ampliación del Servicio de Agua de Riego – Presa Parcco.</p>
</div>
</body></html>
"""
    open(a.out, 'w', encoding='utf-8').write(html)
    print(a.out, len(html.encode()))


if __name__ == '__main__':
    main()
