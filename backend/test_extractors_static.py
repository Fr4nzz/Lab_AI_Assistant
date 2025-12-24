"""
Test extractors using saved HTML files with BeautifulSoup.
This version doesn't require Playwright and can run in any environment.
Improved extraction based on actual HTML structure analysis.
"""
from pathlib import Path
from bs4 import BeautifulSoup
import json
import re

# Paths
SCRIPT_DIR = Path(__file__).parent.absolute()
HTML_SAMPLES_DIR = SCRIPT_DIR / "html_samples"


def extract_ordenes_from_html(html_content: str) -> list:
    """
    Extract orders from HTML using BeautifulSoup.
    Based on actual HTML structure:
    - Cell 0: Order number (may contain | separator)
    - Cell 1: Date and time
    - Cell 2: Patient info (cedula, age, sex, name)
    - Cell 3: Status (contains data-registro)
    - Cell 4: Value
    """
    soup = BeautifulSoup(html_content, 'lxml')
    ordenes = []

    # Find main orders table (first table with proper headers)
    tables = soup.find_all('table')
    orders_table = None

    for table in tables:
        thead = table.find('thead')
        if thead:
            headers = [th.get_text(strip=True) for th in thead.find_all('th')]
            if 'No.' in headers and 'Paciente' in headers:
                orders_table = table
                break

    if not orders_table:
        return ordenes

    tbody = orders_table.find('tbody')
    if not tbody:
        return ordenes

    rows = tbody.find_all('tr')

    for i, row in enumerate(rows[:20]):
        cells = row.find_all('td')
        if len(cells) < 5:
            continue

        # Extract ID from data-registro attribute (in cell 3)
        id_interno = None
        data_registro = cells[3].find(attrs={'data-registro': True}) if len(cells) > 3 else None
        if data_registro:
            try:
                data = json.loads(data_registro.get('data-registro', '{}'))
                id_interno = data.get('id')
            except json.JSONDecodeError:
                pass

        # Order number - clean up separator
        num_text = cells[0].get_text(separator='', strip=True)

        # Date - use separator to get proper format
        fecha_text = cells[1].get_text(separator=' ', strip=True)

        # Patient cell - complex structure
        # Format: "CEDULA E: AGE S: SEX NAME buttons..."
        paciente_cell = cells[2]
        paciente_text = paciente_cell.get_text(separator='|', strip=True)
        parts = paciente_text.split('|')

        cedula = parts[0].strip() if parts else ''
        edad = None
        sexo = None
        nombre = ''

        # Parse the patient info
        for j, part in enumerate(parts):
            part = part.strip()
            if part.startswith('E:'):
                # Next part might be age
                pass
            elif re.match(r'^\d+a$', part):
                edad = part
            elif part.startswith('S:'):
                pass
            elif part in ['M', 'F']:
                sexo = part
            elif len(part) > 5 and part.isupper() and not any(c.isdigit() for c in part):
                # Likely the patient name (all caps, no numbers)
                nombre = part
                break

        # Estado
        estado = cells[3].get_text(strip=True) if len(cells) > 3 else None
        # Remove the badge/button text if present
        estado_badge = cells[3].find(class_='badge') if len(cells) > 3 else None
        if estado_badge:
            estado = estado_badge.get_text(strip=True)

        # Valor
        valor = cells[4].get_text(strip=True) if len(cells) > 4 else None

        orden = {
            'num': num_text,
            'fecha': fecha_text,
            'cedula': cedula,
            'paciente': nombre,
            'sexo': sexo,
            'edad': edad,
            'estado': estado,
            'valor': valor,
            'id': id_interno
        }
        ordenes.append(orden)

    return ordenes


def extract_reportes_from_html(html_content: str) -> dict:
    """
    Extract exam results from HTML using BeautifulSoup.
    Based on actual HTML structure:
    - tr.examen: One cell with <strong> for name, .badge for status
    - tr.parametro: 5 cells - name, input/select, reference, etc.
    """
    soup = BeautifulSoup(html_content, 'lxml')
    examenes = []
    current_exam = None

    # Find all exam and parameter rows
    rows = soup.select('tr.examen, tr.parametro')

    for row in rows:
        classes = row.get('class', [])

        if 'examen' in classes:
            # Save previous exam if it has fields
            if current_exam and current_exam['campos']:
                examenes.append(current_exam)

            # Extract exam name from <strong> tag
            strong = row.find('strong')
            nombre = strong.get_text(strip=True) if strong else ''

            # Extract status from badge
            badge = row.select_one('.badge')
            estado = badge.get_text(strip=True) if badge else None

            # Extract tipo_muestra - usually after the number
            full_text = row.get_text(separator='|', strip=True)
            tipo_muestra = None

            # Parse: "NOMBRE|1|TIPO_MUESTRA|ESTADO|..."
            text_parts = full_text.split('|')
            for part in text_parts:
                part = part.strip()
                if part in ['Sangre Total EDTA', 'Suero', 'Orina', 'Heces']:
                    tipo_muestra = part
                    break

            current_exam = {
                'nombre': nombre,
                'estado': estado,
                'tipo_muestra': tipo_muestra,
                'campos': []
            }

        elif 'parametro' in classes and current_exam:
            cells = row.find_all('td')
            if len(cells) < 2:
                continue

            nombre_campo = cells[0].get_text(strip=True)
            select = cells[1].select_one('select')
            inp = cells[1].select_one('input')

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
                selected = select.select_one('option[selected]')
                campo['val'] = selected.get_text(strip=True) if selected else ''
                campo['opciones'] = [opt.get_text(strip=True) for opt in select.find_all('option') if opt.get_text(strip=True)]
            elif inp:
                campo['val'] = inp.get('value', '')

            current_exam['campos'].append(campo)

    # Add last exam
    if current_exam and current_exam['campos']:
        examenes.append(current_exam)

    return {
        'numero_orden': None,  # Would need URL parsing
        'paciente': None,
        'examenes': examenes
    }


def extract_orden_edit_from_html(html_content: str) -> dict:
    """
    Extract order edit data from HTML using BeautifulSoup.
    Based on actual HTML structure:
    - #examenes-seleccionados contains the exams table
    - First cell format: "CODE - NAME|V|1|tiempo"
    """
    soup = BeautifulSoup(html_content, 'lxml')

    result = {
        'numero_orden': None,
        'paciente': {
            'identificacion': None,
            'nombres': None,
            'apellidos': None
        },
        'examenes': [],
        'totales': {
            'subtotal': None,
            'descuento': None,
            'total': None
        }
    }

    # Try to find order number from URL-like pattern or title
    # Look in script tags or data attributes
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string:
            match = re.search(r'numeroOrden["\']?\s*[:=]\s*["\']?(\d{7})', script.string)
            if match:
                result['numero_orden'] = match.group(1)
                break

    # Look for patient name - find span.paciente with actual name (not just label)
    paciente_spans = soup.select('span.paciente')
    for span in paciente_spans:
        text = span.get_text(strip=True)
        # Skip if just "Paciente" label, look for actual name
        if text and text != 'Paciente' and len(text) > 3:
            result['paciente']['nombres'] = text
            break

    # Also try to find cedula/identificacion in visible text
    cedula_match = re.search(r'\b(\d{10})\b', soup.get_text())
    if cedula_match:
        result['paciente']['identificacion'] = cedula_match.group(1)

    # Exams from #examenes-seleccionados
    container = soup.select_one('#examenes-seleccionados')
    if container:
        for row in container.select('tbody tr'):
            cells = row.find_all('td')
            if len(cells) < 1:
                continue

            # First cell contains: "CODE - NAME|V|1|time"
            cell_text = cells[0].get_text(separator='|', strip=True)
            parts = cell_text.split('|')

            # First part is "CODE - NAME"
            nombre_raw = parts[0].strip() if parts else ''

            # Clean the name - extract just the exam name
            # Format: "BH - BIOMETRÍA HEMÁTICA" -> "BIOMETRÍA HEMÁTICA"
            nombre = nombre_raw
            if ' - ' in nombre_raw:
                nombre = nombre_raw.split(' - ', 1)[1].strip()

            # Find estado (usually V = Validado)
            estado = None
            for part in parts[1:]:
                part = part.strip()
                if part == 'V':
                    estado = 'Validado'
                    break
                elif part == 'P':
                    estado = 'Pendiente'
                    break

            # Valor from second cell
            valor = cells[1].get_text(strip=True) if len(cells) > 1 else None

            if nombre:
                result['examenes'].append({
                    'codigo': nombre_raw.split(' - ')[0].strip() if ' - ' in nombre_raw else None,
                    'nombre': nombre,
                    'valor': valor,
                    'estado': estado
                })

    return result


def test_extract_ordenes():
    """Test ordenes extraction."""
    html_file = HTML_SAMPLES_DIR / "ordenes_lista_20251223_182035.html"

    if not html_file.exists():
        print(f"  HTML file not found: {html_file}")
        return False

    print(f"\n{'='*70}")
    print("TEST: extract_ordenes_list")
    print(f"{'='*70}")
    print(f"  HTML file: {html_file.name}")

    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()

    result = extract_ordenes_from_html(html_content)

    print(f"\n  Results:")
    print(f"    Total ordenes extracted: {len(result)}")

    if result:
        print(f"\n  First 3 orders:")
        for i, orden in enumerate(result[:3]):
            print(f"\n    Order {i+1}:")
            print(f"      num: {orden['num']}")
            print(f"      fecha: {orden['fecha']}")
            print(f"      cedula: {orden['cedula']}")
            print(f"      paciente: {orden['paciente']}")
            print(f"      sexo: {orden['sexo']}, edad: {orden['edad']}")
            print(f"      estado: {orden['estado']}")
            print(f"      id: {orden['id']}")

        # Validate
        has_paciente = any(o['paciente'] for o in result[:5])
        has_id = any(o['id'] for o in result[:5])

        if has_paciente and has_id:
            print(f"\n  VALIDATION: Patient names and IDs extracted correctly!")
            return True
        else:
            print(f"\n  WARNING: Missing patient ({has_paciente}) or ID ({has_id})")
            return False
    else:
        print("  WARNING: No orders extracted!")
        return False


def test_extract_reportes():
    """Test reportes extraction."""
    html_file = HTML_SAMPLES_DIR / "reportes_2501181_20251223_182051.html"

    if not html_file.exists():
        print(f"  HTML file not found: {html_file}")
        return False

    print(f"\n{'='*70}")
    print("TEST: extract_reportes")
    print(f"{'='*70}")
    print(f"  HTML file: {html_file.name}")

    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()

    result = extract_reportes_from_html(html_content)

    print(f"\n  Results:")
    print(f"    Total examenes: {len(result.get('examenes', []))}")

    examenes = result.get('examenes', [])
    if examenes:
        print(f"\n  Examenes encontrados:")
        for exam in examenes[:5]:
            campos = exam.get('campos', [])
            estado = f" [{exam.get('estado', 'N/A')}]" if exam.get('estado') else ""
            muestra = f" ({exam.get('tipo_muestra', '')})" if exam.get('tipo_muestra') else ""
            print(f"    - {exam.get('nombre', 'N/A')}{estado}{muestra} - {len(campos)} campos")

            if campos:
                sample = campos[0]
                ref = f" ref: {sample.get('ref', '')}" if sample.get('ref') else ""
                print(f"        {sample.get('f', 'N/A')} [{sample.get('tipo', '?')}] = {sample.get('val', 'N/A')}{ref}")

        # Validate names are clean
        first_name = examenes[0].get('nombre', '')
        is_clean = len(first_name) < 50 and 'Seleccione' not in first_name

        if is_clean:
            print(f"\n  VALIDATION: Exam names are clean!")
            return True
        else:
            print(f"\n  WARNING: Exam names may be dirty: '{first_name}'")
            return False
    else:
        print("  WARNING: No exams extracted!")
        return False


def test_extract_orden_edit():
    """Test orden edit extraction."""
    html_file = HTML_SAMPLES_DIR / "edit_orden_2501181_20251223_182019.html"

    if not html_file.exists():
        print(f"  HTML file not found: {html_file}")
        return False

    print(f"\n{'='*70}")
    print("TEST: extract_orden_edit")
    print(f"{'='*70}")
    print(f"  HTML file: {html_file.name}")

    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()

    result = extract_orden_edit_from_html(html_content)

    print(f"\n  Results:")
    print(f"    Numero orden: {result.get('numero_orden', 'N/A')}")
    print(f"    Paciente: {result.get('paciente', {}).get('nombres', 'N/A')}")
    print(f"    Total examenes: {len(result.get('examenes', []))}")

    examenes = result.get('examenes', [])
    if examenes:
        print(f"\n  Examenes en la orden:")
        for exam in examenes[:5]:
            codigo = f"[{exam.get('codigo', '')}] " if exam.get('codigo') else ""
            estado = f" - {exam.get('estado', '')}" if exam.get('estado') else ""
            print(f"    - {codigo}{exam.get('nombre', 'N/A')}{estado}")

        if len(examenes) > 5:
            print(f"    ... y {len(examenes) - 5} más")

        # Validate names are clean
        first_name = examenes[0].get('nombre', '')
        is_clean = 'hace un año' not in first_name and len(first_name) < 50

        if is_clean:
            print(f"\n  VALIDATION: Exam names are clean!")
            return True
        else:
            print(f"\n  WARNING: Exam names may be dirty: '{first_name}'")
            return False

    print(f"\n  Extraction completed!")
    return True


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("EXTRACTOR TESTS WITH SAVED HTML FILES")
    print("="*70)

    if not HTML_SAMPLES_DIR.exists():
        print(f"\n ERROR: HTML samples directory not found: {HTML_SAMPLES_DIR}")
        return

    html_files = list(HTML_SAMPLES_DIR.glob("*.html"))
    print(f"\n Found {len(html_files)} HTML sample files:")
    for f in html_files:
        print(f"  - {f.name}")

    results = {}
    results['ordenes'] = test_extract_ordenes()
    results['reportes'] = test_extract_reportes()
    results['orden_edit'] = test_extract_orden_edit()

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = "PASS" if result else "FAIL"
        print(f"  {name}: {status}")

    print(f"\n  Total: {passed}/{total} tests passed")

    if passed == total:
        print("\n  All tests passed!")
    else:
        print(f"\n  {total - passed} test(s) failed. Review output above.")


if __name__ == "__main__":
    main()
