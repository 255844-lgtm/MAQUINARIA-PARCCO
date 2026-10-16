# Actualización diaria del dashboard

1. Leer `MAQUINARIA PARCCO.xlsx` de Google Drive (id 12jWqTfzRTrp6cBNjq8CSdAtg5oJknPym) con `read_file_content` y guardar el texto tal cual en `fuente.txt`.
2. `python3 scripts/parcco_parser.py fuente.txt --out datos --archivo "MAQUINARIA PARCCO.xlsx" --modificado <modifiedTime en hora de Lima, AAAA-MM-DDTHH:MM>`
3. `python3 scripts/build_html.py --datos datos --pagina scripts/plantilla.html --d3 scripts/d3.min.js --out index.html`
4. Commit y push de `index.html` (y `datos/`).

El Excel debe mantener un bloque por máquina: fila de título (TIPO MARCA MODELO), fila `OS, n°, , HM, horas`, cabecera `FECHA, DESCRIPCION, HM, ACUM HM, SALDO`.
