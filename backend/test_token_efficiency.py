#!/usr/bin/env python3
"""
Test script to compare token efficiency of different output formats.
Parses HTML sample files and outputs current vs proposed formats for ALL tools.
"""

import json
import re
from pathlib import Path
from bs4 import BeautifulSoup


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for JSON/text."""
    return len(text) // 4


# ============================================================================
# get_order_results: CURRENT vs COMPACT
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

    numero_orden = None
    match = re.search(r'numeroOrden=(\d+)', html)
    if match:
        numero_orden = match.group(1)

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


def format_get_results_current(data: dict, order_num: str = "2501181") -> dict:
    """Format as current tool output"""
    return {
        "orders": [{
            "order_num": order_num,
            "tab_ready": True,
            **data
        }],
        "total": 1,
        "tip": "Use edit_results() with order_num to edit these results."
    }


def extract_reportes_compact(html: str) -> dict:
    """Compact extraction format with ~3 char abbreviations"""
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
            sts = 'Val' if estado_text == 'Validado' else 'Pnd' if estado_text == 'Pendiente' else None

            current = {'nam': nombre, 'sts': sts, 'fld': []}

        elif 'parametro' in row.get('class', []) and current:
            cells = row.find_all('td')
            if len(cells) < 2:
                continue

            field_name = cells[0].get_text(strip=True)
            select = cells[1].find('select')
            inp = cells[1].find('input')

            if not select and not inp:
                continue

            campo = {'fnm': field_name}

            if select:
                selected_opt = select.find('option', selected=True)
                campo['val'] = selected_opt.get_text(strip=True) if selected_opt else ''
                campo['opt'] = [opt.get_text(strip=True) for opt in select.find_all('option') if opt.get_text(strip=True)]
            elif inp:
                campo['val'] = inp.get('value', '')

            if len(cells) > 2:
                ref = cells[2].get_text(strip=True)
                if ref:
                    campo['ref'] = ref

            current['fld'].append(campo)

    if current and current['fld']:
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

    return {'ord': ord_num, 'pat': pat, 'exm': exams}


# ============================================================================
# get_order_info: CURRENT vs COMPACT
# ============================================================================

def extract_orden_edit_current(html: str) -> dict:
    """Current EXTRACT_ORDEN_EDIT_JS format"""
    soup = BeautifulSoup(html, 'lxml')

    result = {
        "numero_orden": None,
        "paciente": {
            "identificacion": None,
            "nombres": None,
            "apellidos": None
        },
        "examenes": [],
        "totales": {
            "subtotal": None,
            "descuento": None,
            "total": None
        }
    }

    # Order number from URL pattern in HTML
    match = re.search(r'ordenes/(\d+)', html)
    if match:
        result["numero_orden"] = match.group(1)

    # Patient name
    for span in soup.select('span.paciente'):
        text = span.get_text(strip=True)
        if text and text != 'Paciente' and len(text) > 3:
            result["paciente"]["nombres"] = text
            break

    # Cedula
    cedula_match = re.search(r'\b(\d{10})\b', soup.get_text())
    if cedula_match:
        result["paciente"]["identificacion"] = cedula_match.group(1)

    # Exams from #examenes-seleccionados
    container = soup.select_one('#examenes-seleccionados')
    if container:
        for row in container.select('tbody tr'):
            cells = row.find_all('td')
            if not cells:
                continue

            cell_text = cells[0].get_text()
            parts = [p.strip() for p in cell_text.split('\n') if p.strip()]

            nombre_raw = parts[0] if parts else ''
            codigo = None
            nombre = nombre_raw

            if ' - ' in nombre_raw:
                split_name = nombre_raw.split(' - ')
                codigo = split_name[0].strip()
                nombre = ' - '.join(split_name[1:]).strip()

            estado = None
            for part in parts[1:]:
                if part == 'V':
                    estado = 'Validado'
                    break
                if part == 'P':
                    estado = 'Pendiente'
                    break

            valor = cells[1].get_text(strip=True) if len(cells) > 1 else None

            if nombre:
                result["examenes"].append({
                    "codigo": codigo,
                    "nombre": nombre,
                    "valor": valor,
                    "estado": estado
                })

    return result


def format_get_order_info_current(data: dict, order_id: int = 12345) -> dict:
    """Current get_order_info output wrapper"""
    return {
        "orders": [{
            "order_id": order_id,
            "tab_index": 0,
            **data,
            "exams": data.get("examenes", [])  # duplicated as "exams"
        }],
        "total": 1,
        "tip": "Use edit_order_exams() with order_id or tab_index to add/remove exams."
    }


def extract_orden_edit_compact(html: str) -> dict:
    """Compact format for get_order_info"""
    soup = BeautifulSoup(html, 'lxml')

    # Order number
    ord_num = None
    match = re.search(r'ordenes/(\d+)', html)
    if match:
        ord_num = match.group(1)

    # Patient
    pat = None
    ced = None
    for span in soup.select('span.paciente'):
        text = span.get_text(strip=True)
        if text and text != 'Paciente' and len(text) > 3:
            pat = text
            break

    cedula_match = re.search(r'\b(\d{10})\b', soup.get_text())
    if cedula_match:
        ced = cedula_match.group(1)

    # Exams
    exm = []
    container = soup.select_one('#examenes-seleccionados')
    if container:
        for row in container.select('tbody tr'):
            cells = row.find_all('td')
            if not cells:
                continue

            cell_text = cells[0].get_text()
            parts = [p.strip() for p in cell_text.split('\n') if p.strip()]

            nombre_raw = parts[0] if parts else ''
            cod = None
            nam = nombre_raw

            if ' - ' in nombre_raw:
                split_name = nombre_raw.split(' - ')
                cod = split_name[0].strip()
                nam = ' - '.join(split_name[1:]).strip()

            sts = None
            for part in parts[1:]:
                if part == 'V':
                    sts = 'Val'
                    break
                if part == 'P':
                    sts = 'Pnd'
                    break

            prc = cells[1].get_text(strip=True) if len(cells) > 1 else None

            if cod:
                exam = {"cod": cod, "nam": nam}
                if sts:
                    exam["sts"] = sts
                if prc:
                    exam["prc"] = prc
                exm.append(exam)

    return {"ord": ord_num, "ced": ced, "pat": pat, "exm": exm}


# ============================================================================
# edit_results INPUT: CURRENT vs COMPACT
# ============================================================================

def generate_edit_results_input_current(exam_data: list, order_num: str = "2501181") -> list:
    """Generate current edit_results input from exam data"""
    edits = []
    for exam in exam_data[:3]:  # First 3 exams as sample
        exam_name = exam.get('nombre') or exam.get('nam', '')
        campos = exam.get('campos') or exam.get('fld', [])
        for campo in campos[:2]:  # First 2 fields per exam
            field_name = campo.get('f') or campo.get('fnm', '')
            edits.append({
                "orden": order_num,
                "e": exam_name,
                "f": field_name,
                "v": "7.5"  # Sample value
            })
    return edits


def generate_edit_results_input_compact(exam_data: list, order_num: str = "2501181") -> list:
    """Generate compact edit_results input - same format (already short keys)"""
    # edit_results already uses short keys: orden, e, f, v
    # The only optimization is using tab_index instead of orden
    edits = []
    for exam in exam_data[:3]:
        exam_name = exam.get('nombre') or exam.get('nam', '')
        campos = exam.get('campos') or exam.get('fld', [])
        for campo in campos[:2]:
            field_name = campo.get('f') or campo.get('fnm', '')
            edits.append({
                "t": 1,  # tab_index instead of orden
                "e": exam_name,
                "f": field_name,
                "v": "7.5"
            })
    return edits


# ============================================================================
# edit_order_exams OUTPUT: CURRENT vs COMPACT
# ============================================================================

def generate_edit_order_exams_output_current() -> dict:
    """Sample current edit_order_exams output"""
    return {
        "identifier": "order_12345",
        "tab_index": None,
        "order_id": 12345,
        "is_new_order": False,
        "added": ["GLU", "BH"],
        "removed": ["EMO"],
        "failed_add": [],
        "failed_remove": [],
        "cedula_updated": True,
        "cedula": "1234567890",
        "current_exams": [
            {"codigo": "GLU", "nombre": "GLUCOSA BASAL", "valor": "$5.00", "estado": "Pendiente", "can_remove": True},
            {"codigo": "BH", "nombre": "BIOMETRIA HEMATICA", "valor": "$8.00", "estado": "Pendiente", "can_remove": True}
        ],
        "totals": {"total": "$13.00"},
        "status": "pending_save",
        "next_step": "Revisa los cambios y haz click en 'Guardar'."
    }


def generate_edit_order_exams_output_compact() -> dict:
    """Compact edit_order_exams output"""
    return {
        "ord": 12345,
        "add": ["GLU", "BH"],
        "rem": ["EMO"],
        "ced": "1234567890",
        "exm": [
            {"cod": "GLU", "nam": "GLUCOSA BASAL", "prc": "$5.00"},
            {"cod": "BH", "nam": "BIOMETRIA HEMATICA", "prc": "$8.00"}
        ],
        "tot": "$13.00",
        "sts": "save"  # pending save
    }


# ============================================================================
# create_new_order OUTPUT: CURRENT vs COMPACT
# ============================================================================

def generate_create_order_output_current() -> dict:
    """Sample current create_new_order output"""
    return {
        "success": True,
        "tab_index": 2,
        "is_cotizacion": False,
        "cedula": "1234567890",
        "added_exams": ["GLU", "BH", "EMO"],
        "failed_exams": [],
        "current_exams": [
            {"codigo": "GLU", "nombre": "GLUCOSA BASAL", "valor": "$5.00", "estado": None, "can_remove": True},
            {"codigo": "BH", "nombre": "BIOMETRIA HEMATICA", "valor": "$8.00", "estado": None, "can_remove": True},
            {"codigo": "EMO", "nombre": "ELEMENTAL Y MICROSCOPICO DE ORINA", "valor": "$4.00", "estado": None, "can_remove": True}
        ],
        "totals": {"total": "$17.00"},
        "status": "ready_to_save",
        "next_step": "Revisa los exámenes y haz click en 'Guardar'."
    }


def generate_create_order_output_compact() -> dict:
    """Compact create_new_order output"""
    return {
        "ok": True,
        "tab": 2,
        "ced": "1234567890",
        "add": ["GLU", "BH", "EMO"],
        "exm": [
            {"cod": "GLU", "prc": "$5.00"},
            {"cod": "BH", "prc": "$8.00"},
            {"cod": "EMO", "prc": "$4.00"}
        ],
        "tot": "$17.00",
        "sts": "save"
    }


# ============================================================================
# MAIN TEST
# ============================================================================

def compare_formats(name: str, current: dict, compact: dict):
    """Compare two formats and print results"""
    current_json = json.dumps(current, ensure_ascii=False, separators=(',', ':'))
    compact_json = json.dumps(compact, ensure_ascii=False, separators=(',', ':'))

    curr_chars = len(current_json)
    comp_chars = len(compact_json)
    savings = ((curr_chars - comp_chars) / curr_chars * 100) if curr_chars > 0 else 0

    print(f"\n{'='*60}")
    print(f"{name}")
    print(f"{'='*60}")
    print(f"CURRENT:  {curr_chars:,} chars (~{curr_chars//4:,} tokens)")
    print(f"COMPACT:  {comp_chars:,} chars (~{comp_chars//4:,} tokens)")
    print(f"SAVINGS:  {savings:.1f}% ({curr_chars - comp_chars:,} chars)")

    return {
        "name": name,
        "current_chars": curr_chars,
        "compact_chars": comp_chars,
        "savings_pct": savings
    }


def main():
    html_dir = Path(__file__).parent / 'html_samples'
    reportes_file = html_dir / 'reportes_2501181_20251223_182051.html'
    edit_orden_file = html_dir / 'edit_orden_2501181_20251223_182019.html'

    print("=" * 70)
    print("COMPREHENSIVE TOKEN EFFICIENCY TEST - ALL TOOLS")
    print("=" * 70)

    results = []

    # ========== get_order_results ==========
    if reportes_file.exists():
        html = reportes_file.read_text(encoding='utf-8')
        current_data = extract_reportes_current(html)
        current_output = format_get_results_current(current_data)
        compact_output = extract_reportes_compact(html)

        exam_count = len(current_data['examenes'])
        field_count = sum(len(ex['campos']) for ex in current_data['examenes'])
        print(f"\nTest data: {exam_count} exams, {field_count} fields")

        results.append(compare_formats(
            "get_order_results OUTPUT",
            current_output,
            compact_output
        ))

        # Show sample outputs
        print("\n--- CURRENT FORMAT (first exam) ---")
        sample = {"orders": [{"examenes": current_data["examenes"][:1]}]}
        print(json.dumps(sample, ensure_ascii=False, indent=2)[:800] + "...")

        print("\n--- COMPACT FORMAT (first exam) ---")
        sample_compact = {"exm": compact_output["exm"][:1]}
        print(json.dumps(sample_compact, ensure_ascii=False, indent=2)[:600] + "...")

    # ========== get_order_info ==========
    if edit_orden_file.exists():
        html = edit_orden_file.read_text(encoding='utf-8')
        current_data = extract_orden_edit_current(html)
        current_output = format_get_order_info_current(current_data)
        compact_output = extract_orden_edit_compact(html)

        results.append(compare_formats(
            "get_order_info OUTPUT",
            current_output,
            compact_output
        ))

    # ========== edit_results INPUT ==========
    if reportes_file.exists():
        html = reportes_file.read_text(encoding='utf-8')
        current_data = extract_reportes_current(html)

        current_input = generate_edit_results_input_current(current_data['examenes'])
        compact_input = generate_edit_results_input_compact(current_data['examenes'])

        results.append(compare_formats(
            "edit_results INPUT (6 edits)",
            {"data": current_input},
            {"data": compact_input}
        ))

        print("\n--- CURRENT INPUT FORMAT ---")
        print(json.dumps({"data": current_input[:2]}, ensure_ascii=False, indent=2))

        print("\n--- COMPACT INPUT FORMAT (using tab index) ---")
        print(json.dumps({"data": compact_input[:2]}, ensure_ascii=False, indent=2))

    # ========== edit_order_exams OUTPUT ==========
    current_out = generate_edit_order_exams_output_current()
    compact_out = generate_edit_order_exams_output_compact()

    results.append(compare_formats(
        "edit_order_exams OUTPUT",
        current_out,
        compact_out
    ))

    print("\n--- CURRENT OUTPUT ---")
    print(json.dumps(current_out, ensure_ascii=False, indent=2))

    print("\n--- COMPACT OUTPUT ---")
    print(json.dumps(compact_out, ensure_ascii=False, indent=2))

    # ========== create_new_order OUTPUT ==========
    current_create = generate_create_order_output_current()
    compact_create = generate_create_order_output_compact()

    results.append(compare_formats(
        "create_new_order OUTPUT",
        current_create,
        compact_create
    ))

    # ========== SUMMARY ==========
    print("\n")
    print("=" * 70)
    print("SUMMARY - ALL TOOLS")
    print("=" * 70)
    print(f"{'Tool':<35} {'Current':>10} {'Compact':>10} {'Savings':>10}")
    print("-" * 70)

    total_current = 0
    total_compact = 0

    for r in results:
        print(f"{r['name']:<35} {r['current_chars']:>10,} {r['compact_chars']:>10,} {r['savings_pct']:>9.1f}%")
        total_current += r['current_chars']
        total_compact += r['compact_chars']

    total_savings = ((total_current - total_compact) / total_current * 100) if total_current > 0 else 0
    print("-" * 70)
    print(f"{'TOTAL':<35} {total_current:>10,} {total_compact:>10,} {total_savings:>9.1f}%")

    print("\n")
    print("=" * 70)
    print("KEY ABBREVIATIONS LEGEND")
    print("=" * 70)
    print("""
    COMMON KEYS:
    ord = order number/ID         pat = patient name
    ced = cedula                  exm = exams list
    sts = status (Val/Pnd)        tot = total price

    EXAM FIELDS:
    nam = exam name               cod = exam code
    fld = fields list             prc = price
    fnm = field name              val = value
    ref = reference range         opt = options (select)

    EDIT OPERATIONS:
    add = added items             rem = removed items
    tab = tab index               ok  = success

    STATUS VALUES:
    Val = Validado                Pnd = Pendiente
    save = pending save
    """)


if __name__ == '__main__':
    main()
