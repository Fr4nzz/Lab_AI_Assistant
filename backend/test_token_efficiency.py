#!/usr/bin/env python3
"""
Test script to compare token efficiency of different output formats.
Parses HTML sample files and outputs current vs proposed formats.
"""

import json
import re
from pathlib import Path
from bs4 import BeautifulSoup


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for JSON/text."""
    return len(text) // 4


# ============================================================================
# CURRENT FORMAT EXTRACTORS (matches extractors.py)
# ============================================================================

def extract_reportes_current(html: str) -> dict:
    """Current extraction format - matches EXTRACT_REPORTES_JS in extractors.py"""
    soup = BeautifulSoup(html, 'lxml')
    examenes = []
    current = None

    tipos_muestra = ['Sangre Total EDTA', 'Suero', 'Orina', 'Heces', 'Plasma']

    for row in soup.select('tr.examen, tr.parametro'):
        if 'examen' in row.get('class', []):
            if current and current['campos']:
                examenes.append(current)

            strong = row.find('strong')
            nombre = strong.get_text(strip=True) if strong else ''

            badge = row.find(class_='badge')
            estado = badge.get_text(strip=True) if badge else None

            tipo_muestra = None
            full_text = row.get_text()
            for tipo in tipos_muestra:
                if tipo in full_text:
                    tipo_muestra = tipo
                    break

            current = {
                'nombre': nombre,
                'estado': estado,
                'tipo_muestra': tipo_muestra,
                'campos': []
            }

        elif 'parametro' in row.get('class', []) and current:
            cells = row.find_all('td')
            if len(cells) < 2:
                continue

            nombre_campo = cells[0].get_text(strip=True)
            select = cells[1].find('select')
            inp = cells[1].find('input')

            if not select and not inp:
                continue

            campo = {
                'f': nombre_campo,
                'tipo': 'select' if select else 'input',
                'val': None,
                'opciones': None,
                'ref': cells[2].get_text(strip=True) if len(cells) > 2 else None
            }

            if select:
                selected_opt = select.find('option', selected=True)
                campo['val'] = selected_opt.get_text(strip=True) if selected_opt else ''
                campo['opciones'] = [opt.get_text(strip=True) for opt in select.find_all('option') if opt.get_text(strip=True)]
            elif inp:
                campo['val'] = inp.get('value', '')

            current['campos'].append(campo)

    if current and current['campos']:
        examenes.append(current)

    # Extract order number from URL-like patterns in the HTML
    numero_orden = None
    match = re.search(r'numeroOrden=(\d+)', html)
    if match:
        numero_orden = match.group(1)

    # Extract patient name
    paciente = None
    for span in soup.select('span.paciente'):
        text = span.get_text(strip=True)
        if text and text != 'Paciente' and len(text) > 3:
            paciente = text
            break

    return {
        'numero_orden': numero_orden,
        'paciente': paciente,
        'examenes': examenes
    }


def format_current_output(data: dict, order_num: str = "2501181") -> dict:
    """Format as current tool output - matches _get_order_results_impl"""
    return {
        "orders": [{
            "order_num": order_num,
            "tab_ready": True,
            **data
        }],
        "total": 1,
        "tip": "Use edit_results() with order_num to edit these results."
    }


# ============================================================================
# PROPOSED FORMAT EXTRACTORS (optimized with ~3 char abbreviations)
# ============================================================================

def extract_reportes_compact(html: str) -> dict:
    """
    Compact extraction format with ~3 char abbreviations.

    Keys:
    - ord: order number
    - pat: patient name
    - exm: exams list
    - nam: exam name
    - sts: status (Pnd=Pendiente, Val=Validado)
    - fld: fields list
    - fnm: field name
    - val: value
    - ref: reference (only if present)
    - opt: options (only for selects)
    """
    soup = BeautifulSoup(html, 'lxml')
    exams = []
    current = None

    for row in soup.select('tr.examen, tr.parametro'):
        if 'examen' in row.get('class', []):
            if current and current['fld']:
                exams.append(current)

            strong = row.find('strong')
            nombre = strong.get_text(strip=True) if strong else ''

            badge = row.find(class_='badge')
            estado_text = badge.get_text(strip=True) if badge else None

            # Abbreviated status
            if estado_text == 'Validado':
                sts = 'Val'
            elif estado_text == 'Pendiente':
                sts = 'Pnd'
            else:
                sts = estado_text

            current = {
                'nam': nombre,
                'sts': sts,
                'fld': []
            }

        elif 'parametro' in row.get('class', []) and current:
            cells = row.find_all('td')
            if len(cells) < 2:
                continue

            field_name = cells[0].get_text(strip=True)
            select = cells[1].find('select')
            inp = cells[1].find('input')

            if not select and not inp:
                continue

            campo = {
                'fnm': field_name,
                'val': None
            }

            if select:
                selected_opt = select.find('option', selected=True)
                campo['val'] = selected_opt.get_text(strip=True) if selected_opt else ''
                campo['opt'] = [opt.get_text(strip=True) for opt in select.find_all('option') if opt.get_text(strip=True)]
            elif inp:
                campo['val'] = inp.get('value', '')

            # Only include ref if present and non-empty
            if len(cells) > 2:
                ref = cells[2].get_text(strip=True)
                if ref:
                    campo['ref'] = ref

            current['fld'].append(campo)

    if current and current['fld']:
        exams.append(current)

    # Extract order number
    ord_num = None
    match = re.search(r'numeroOrden=(\d+)', html)
    if match:
        ord_num = match.group(1)

    # Extract patient name
    pat = None
    for span in soup.select('span.paciente'):
        text = span.get_text(strip=True)
        if text and text != 'Paciente' and len(text) > 3:
            pat = text
            break

    return {
        'ord': ord_num,
        'pat': pat,
        'exm': exams
    }


def format_compact_output(data: dict) -> dict:
    """Format as compact tool output - no wrapper, direct data"""
    return data


# ============================================================================
# EVEN MORE COMPACT FORMAT (2 char keys, minimal)
# ============================================================================

def extract_reportes_minimal(html: str) -> dict:
    """
    Minimal format - only essential data, 2-char keys.

    Keys: or (order), pa (patient), ex (exams), nm (name), st (status),
          fl (fields), fn (field name), vl (value), rf (ref), op (options)
    """
    soup = BeautifulSoup(html, 'lxml')
    exams = []
    current = None

    for row in soup.select('tr.examen, tr.parametro'):
        if 'examen' in row.get('class', []):
            if current and current['fl']:
                exams.append(current)

            strong = row.find('strong')
            nombre = strong.get_text(strip=True) if strong else ''

            badge = row.find(class_='badge')
            estado_text = badge.get_text(strip=True) if badge else None
            st = 'V' if estado_text == 'Validado' else 'P' if estado_text == 'Pendiente' else None

            current = {'nm': nombre, 'st': st, 'fl': []}

        elif 'parametro' in row.get('class', []) and current:
            cells = row.find_all('td')
            if len(cells) < 2:
                continue

            field_name = cells[0].get_text(strip=True)
            select = cells[1].find('select')
            inp = cells[1].find('input')

            if not select and not inp:
                continue

            campo = {'fn': field_name}

            if select:
                selected_opt = select.find('option', selected=True)
                campo['vl'] = selected_opt.get_text(strip=True) if selected_opt else ''
                campo['op'] = [opt.get_text(strip=True) for opt in select.find_all('option') if opt.get_text(strip=True)]
            elif inp:
                campo['vl'] = inp.get('value', '')

            if len(cells) > 2:
                ref = cells[2].get_text(strip=True)
                if ref:
                    campo['rf'] = ref

            current['fl'].append(campo)

    if current and current['fl']:
        exams.append(current)

    ord_num = None
    match = re.search(r'numeroOrden=(\d+)', html)
    if match:
        ord_num = match.group(1)

    pat = None
    for span in soup.select('span.paciente'):
        text = span.get_text(strip=True)
        if text and text != 'Paciente' and len(text) > 3:
            pat = text
            break

    return {'or': ord_num, 'pa': pat, 'ex': exams}


# ============================================================================
# MAIN TEST
# ============================================================================

def main():
    html_dir = Path(__file__).parent / 'html_samples'
    reportes_file = html_dir / 'reportes_2501181_20251223_182051.html'

    if not reportes_file.exists():
        print(f"ERROR: File not found: {reportes_file}")
        return

    html = reportes_file.read_text(encoding='utf-8')

    print("=" * 80)
    print("TOKEN EFFICIENCY TEST - get_order_results output comparison")
    print("=" * 80)
    print()

    # Current format
    current_data = extract_reportes_current(html)
    current_output = format_current_output(current_data)
    current_json = json.dumps(current_output, ensure_ascii=False, indent=2)
    current_json_compact = json.dumps(current_output, ensure_ascii=False, separators=(',', ':'))

    # Compact format (~3 char keys)
    compact_data = extract_reportes_compact(html)
    compact_output = format_compact_output(compact_data)
    compact_json = json.dumps(compact_output, ensure_ascii=False, indent=2)
    compact_json_compact = json.dumps(compact_output, ensure_ascii=False, separators=(',', ':'))

    # Minimal format (2 char keys)
    minimal_data = extract_reportes_minimal(html)
    minimal_json = json.dumps(minimal_data, ensure_ascii=False, indent=2)
    minimal_json_compact = json.dumps(minimal_data, ensure_ascii=False, separators=(',', ':'))

    # Stats
    print("STATISTICS:")
    print("-" * 60)

    exam_count = len(current_data['examenes'])
    field_count = sum(len(ex['campos']) for ex in current_data['examenes'])
    print(f"Exams found: {exam_count}")
    print(f"Fields found: {field_count}")
    print()

    print("FORMAT COMPARISON (minified JSON - actual tool output):")
    print("-" * 60)

    formats = [
        ("CURRENT (verbose)", current_json_compact),
        ("COMPACT (~3 char keys)", compact_json_compact),
        ("MINIMAL (2 char keys)", minimal_json_compact),
    ]

    baseline_chars = len(current_json_compact)
    baseline_tokens = estimate_tokens(current_json_compact)

    for name, json_str in formats:
        chars = len(json_str)
        tokens = estimate_tokens(json_str)
        savings_pct = ((baseline_chars - chars) / baseline_chars * 100) if baseline_chars > 0 else 0

        print(f"{name}:")
        print(f"  Characters: {chars:,}")
        print(f"  Est. Tokens: {tokens:,}")
        if name != "CURRENT (verbose)":
            print(f"  Savings: {savings_pct:.1f}%")
        print()

    # Show sample outputs
    print()
    print("=" * 80)
    print("SAMPLE OUTPUTS (first exam only, pretty-printed)")
    print("=" * 80)

    print("\n--- CURRENT FORMAT ---")
    sample_current = {
        "orders": [{
            "order_num": current_output["orders"][0]["order_num"],
            "tab_ready": True,
            "numero_orden": current_output["orders"][0].get("numero_orden"),
            "paciente": current_output["orders"][0].get("paciente"),
            "examenes": current_output["orders"][0]["examenes"][:1]  # First exam only
        }],
        "total": 1,
        "tip": current_output["tip"]
    }
    print(json.dumps(sample_current, ensure_ascii=False, indent=2))

    print("\n--- COMPACT FORMAT (~3 char keys) ---")
    sample_compact = {
        "ord": compact_output["ord"],
        "pat": compact_output["pat"],
        "exm": compact_output["exm"][:1]  # First exam only
    }
    print(json.dumps(sample_compact, ensure_ascii=False, indent=2))

    print("\n--- MINIMAL FORMAT (2 char keys) ---")
    sample_minimal = {
        "or": minimal_data["or"],
        "pa": minimal_data["pa"],
        "ex": minimal_data["ex"][:1]  # First exam only
    }
    print(json.dumps(sample_minimal, ensure_ascii=False, indent=2))

    # Key legend
    print()
    print("=" * 80)
    print("KEY LEGEND (for ~3 char compact format)")
    print("=" * 80)
    print("""
    ord = order number (numero de orden)
    pat = patient name (paciente)
    exm = exams list (examenes)
    nam = exam name (nombre del examen)
    sts = status: "Val"=Validado, "Pnd"=Pendiente
    fld = fields list (campos)
    fnm = field name (nombre del campo)
    val = value (valor)
    ref = reference range (only if present)
    opt = options for select fields (only if select)
    """)


if __name__ == '__main__':
    main()
