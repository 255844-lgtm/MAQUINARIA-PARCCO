#!/usr/bin/env python3
"""Convierte el texto de 'MAQUINARIA PARCCO.xlsx' (Google Drive read_file_content)
en maquinas.json, partes.json y actualizacion.json para el dashboard.

Uso: python3 parcco_parser.py fuente.txt --out DIR --archivo "NOMBRE" --modificado ISO
El archivo tiene bloques lado a lado, uno por máquina:
  fila título: TIPO MARCA MODELO
  fila OS:     OS, <n°>, , HM, <horas>
  [filas extra opcionales, p. ej. montos en soles]
  cabecera:    FECHA, DESCRIPCION, HM, ACUM HM, [SALDO]
  arrastre:    , <mes anterior>, , <acum>, <saldo>
  días:        <fecha>, <actividad>, <hm>, <acum>, <saldo>
"""
import argparse, json, re, sys, unicodedata
from datetime import datetime, timezone, timedelta


def tokens(text):
    out, cur, q = [], [], False
    for ch in text:
        if ch == '"':
            q = not q
            cur.append(ch)
        elif ch == ',' and not q:
            out.append(''.join(cur)); cur = []
        else:
            cur.append(ch)
    out.append(''.join(cur))
    return out


def split_boundary(tok):
    q = False
    for i, ch in enumerate(tok):
        if ch == '"':
            q = not q
        elif ch == ' ' and not q:
            return tok[:i], tok[i + 1:]
    return None


NUM = re.compile(r'^-?\d+(\.\d+)?$')


def left_ok(s):
    s = s.strip()
    return s == '' or bool(NUM.match(s)) or (s.upper() == s and not any(c.islower() for c in s))


def right_ok(s):
    s = s.strip()
    return s == '' or s.startswith('"') or (s.upper() == s and not any(c.islower() for c in s))


def grid_from(text):
    text = text.strip()
    t = tokens(text)
    T = len(t)
    for N in range(5, 400):
        if (T - 1) % (N - 1):
            continue
        R = (T - 1) // (N - 1)
        if R < 3:
            continue
        ok, rows = True, []
        first = split_boundary(t[0])
        if not first:
            continue
        cur = [first[1]]
        for k in range(1, T):
            if k % (N - 1) == 0 and k < T - 1 + 0 and k != T - 1:
                b = split_boundary(t[k])
                if not b or not left_ok(b[0]) or not right_ok(b[1]):
                    ok = False; break
                cur.append(b[0]); rows.append(cur); cur = [b[1]]
            else:
                cur.append(t[k])
        if not ok:
            continue
        rows.append(cur)
        if all(len(r) == N for r in rows) and any(any(c.strip() == 'FECHA' for c in r) for r in rows):
            return [[unq(c) for c in r] for r in rows]
    raise SystemExit('No se pudo reconocer la estructura de filas del archivo.')


def unq(c):
    c = c.strip()
    if len(c) >= 2 and c[0] == '"' and c[-1] == '"':
        c = c[1:-1]
    return c.strip()


def num(c):
    c = c.replace(',', '').strip()
    return float(c) if NUM.match(c) else None


def fecha(c):
    for f in ('%A, %B %d, %Y', '%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y'):
        try:
            return datetime.strptime(c, f).date().isoformat()
        except ValueError:
            pass
    return None


TIPOS = [('RODILLO COMPACTADOR', 'Rodillo compactador', 'rodillo'), ('CARGADOR FRONTAL', 'Cargador frontal', 'cargador'),
         ('TRACTOR SOBRE ORUGAS', 'Tractor sobre orugas', 'tractor'), ('CAMION CISTERNA', 'Camión cisterna', 'volquete'),
         ('RETROEXCAVADORA', 'Retroexcavadora', 'retro'), ('EXCAVADORA', 'Excavadora', 'excavadora'),
         ('VOLQUETE', 'Volquete', 'volquete'), ('RODILLO', 'Rodillo', 'rodillo'), ('CARGADOR', 'Cargador', 'cargador'),
         ('TRACTOR', 'Tractor', 'tractor'), ('MOTONIVELADORA', 'Motoniveladora', 'motoniveladora'),
         ('CISTERNA', 'Cisterna', 'volquete'), ('CAMION', 'Camión', 'volquete'), ('MINICARGADOR', 'Minicargador', 'cargador')]


def tipo_de(titulo):
    t = titulo.upper().strip()
    for k, nombre, ico in TIPOS:
        if t.startswith(k):
            return nombre, titulo.strip()[len(k):].strip(' -'), ico
    return titulo.strip().split(' ')[0].capitalize(), ' '.join(titulo.strip().split(' ')[1:]), 'cargador'


def slug(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')[:48] or 'maquina'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('fuente'); ap.add_argument('--out', default='.')
    ap.add_argument('--archivo', default=''); ap.add_argument('--modificado', default='')
    a = ap.parse_args()
    g = grid_from(open(a.fuente, encoding='utf-8').read())
    h = next(i for i, r in enumerate(g) if any(c == 'FECHA' for c in r))
    starts = [j for j, c in enumerate(g[h]) if c == 'FECHA']
    # Fila OS: la más cercana encima de la cabecera que tenga 'OS'; puede haber filas extra (montos) entre ambas.
    ro = next((r for r in range(h - 1, -1, -1) if any(c.upper() == 'OS' for c in g[r])), h - 1)
    # Fila título: la más cercana encima de la fila OS con algún texto.
    rt = next((r for r in range(ro - 1, -1, -1) if any(c and num(c) is None for c in g[r])), ro - 1)
    maquinas, partes, avisos, usados = [], [], [], set()
    for bi, s in enumerate(starts):
        e = starts[bi + 1] if bi + 1 < len(starts) else len(g[h])
        head = {g[h][j].upper(): j for j in range(s, e) if g[h][j]}
        cD = next((j for k, j in head.items() if k.startswith('DESCRIP')), s + 1)
        cH, cA = head.get('HM', s + 2), head.get('ACUM HM', s + 3)
        cS = head.get('SALDO')
        titulo = g[rt][s] if rt >= 0 and g[rt][s] and num(g[rt][s]) is None else ''
        if not titulo:
            titulo = next((g[r][s] for r in range(h - 1, -1, -1) if g[r][s] and g[r][s].upper() != 'OS' and num(g[r][s]) is None), '')
        if not titulo:
            titulo = f'MÁQUINA {bi + 1}'
        os_, hos = '', None
        if ro >= 0:
            fila = g[ro]
            for j in range(s, e):
                if fila[j].upper() == 'OS' and j + 1 < e:
                    os_ = fila[j + 1]
                if fila[j].upper() == 'HM' and j + 1 < e:
                    hos = num(fila[j + 1])
        tipo, det, ico = tipo_de(titulo)
        cod = slug(titulo)
        while cod in usados:
            cod += '-2'
        usados.add(cod)
        arr_p, arr_h, prev, saldo_arch = '', 0.0, None, None
        for r in g[h + 1:]:
            f = fecha(r[s]); d = r[cD] if cD < e else ''
            hm = num(r[cH]); ac = num(r[cA]); sa = num(r[cS]) if cS is not None else None
            if not f:
                if r[s] == '' and d and ac is not None:
                    arr_p, arr_h, prev = d, ac, ac
                    saldo_arch = sa if sa is not None else saldo_arch
                continue
            if ac is None and hm is None:
                continue  # día aún sin registrar
            if ac is None:
                ac = round((prev or 0) + (hm or 0), 2)
            if prev is not None and abs(prev + (hm or 0) - ac) > 0.05:
                avisos.append(f'{titulo} {f}: acumulado {ac} no coincide con {prev} + {hm or 0}')
            partes.append({'codigo': cod, 'fecha': f, 'descripcion': d or ('—' if not hm else ''), 'horas': hm or 0.0,
                           'acumulado': ac, 'saldo_archivo': sa, 'trabajo': bool(hm)})
            prev = ac
            if sa is not None:
                saldo_arch = sa
        maquinas.append({'codigo': cod, 'nombre': titulo.strip(), 'tipo': tipo, 'detalle': det, 'icono': ico,
                         'os': os_, 'horas_os': hos, 'arrastre_periodo': arr_p, 'arrastre_horas': arr_h,
                         'saldo_archivo': saldo_arch, 'orden': bi + 1})
    # Una OS sin HM en su bloque toma las horas de otro bloque con la misma OS
    por_os = {}
    for m in maquinas:
        if m['os'] and m['horas_os'] is not None:
            por_os[m['os']] = m['horas_os']
    for m in maquinas:
        if m['os'] and m['horas_os'] is None and m['os'] in por_os:
            m['horas_os'] = por_os[m['os']]
    lima = datetime.now(timezone(timedelta(hours=-5)))
    act = [{'actualizado_en': lima.strftime('%Y-%m-%dT%H:%M'), 'archivo': a.archivo,
            'archivo_modificado': a.modificado, 'ultimo_parte': max((p['fecha'] for p in partes), default=''),
            'maquinas': len(maquinas), 'partes': len(partes), 'avisos': len(avisos), 'detalle_avisos': ' | '.join(avisos)[:2000]}]
    for name, data in (('maquinas', maquinas), ('partes', partes), ('actualizacion', act)):
        json.dump(data, open(f'{a.out}/{name}.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps({'maquinas': [(m['codigo'], m['os'], m['horas_os'], m['arrastre_horas']) for m in maquinas],
                      'partes': len(partes), 'ultimo_parte': act[0]['ultimo_parte'], 'avisos': avisos}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
