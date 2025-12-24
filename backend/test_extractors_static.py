"""
Test extractors using saved HTML files with BeautifulSoup.
This version doesn't require Playwright and can run in any environment.
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
    Mimics the JavaScript extraction logic.
    """
    soup = BeautifulSoup(html_content, 'lxml')
    ordenes = []

    # Find table rows
    rows = soup.select('table tbody tr')

    for i, row in enumerate(rows[:20]):
        cells = row.find_all('td')
        if len(cells) < 4:
            continue

        # Extract ID from data-registro attribute
        id_interno = None
        data_registro = row.select_one('[data-registro]')
        if data_registro:
            try:
                data = json.loads(data_registro.get('data-registro', '{}'))
                id_interno = data.get('id')
            except json.JSONDecodeError:
                pass

        # Patient cell (usually cell 2)
        paciente_text = cells[2].get_text(separator='\n').strip() if len(cells) > 2 else ''
        paciente_lines = paciente_text.split('\n')
        cedula = paciente_lines[0].split(' ')[0] if paciente_lines else ''

        # Extract sex and age
        sexo, edad = None, None
        match = re.search(r'([MF])\s*(\d+a)', paciente_text)
        if match:
            sexo = match.group(1)
            edad = match.group(2)

        orden = {
            'num': cells[0].get_text(strip=True) if cells else None,
            'fecha': cells[1].get_text(strip=True).replace('\n', ' ') if len(cells) > 1 else None,
            'cedula': cedula,
            'paciente': paciente_lines[1] if len(paciente_lines) > 1 else '',
            'sexo': sexo,
            'edad': edad,
            'estado': cells[3].get_text(strip=True) if len(cells) > 3 else None,
            'valor': cells[4].get_text(strip=True) if len(cells) > 4 else None,
            'id': id_interno
        }
        ordenes.append(orden)

    return ordenes


def extract_reportes_from_html(html_content: str) -> dict:
    """
    Extract exam results from HTML using BeautifulSoup.
    Mimics the JavaScript extraction logic.
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

            # Start new exam
            nombre_text = row.get_text(strip=True).split('\n')[0]
            badge = row.select_one('.badge')
            estado = badge.get_text(strip=True) if badge else None

            # Clean nombre
            nombre = nombre_text.replace(estado, '').strip() if estado else nombre_text

            current_exam = {
                'nombre': nombre,
                'estado': estado,
                'tipo_muestra': None,
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
                campo['opciones'] = [opt.get_text(strip=True) for opt in select.find_all('option')]
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

    # Numero de orden from title
    titulo = soup.select_one('h1, h2, .card-header')
    if titulo:
        match = re.search(r'(\d{7})', titulo.get_text())
        if match:
            result['numero_orden'] = match.group(1)

    # Patient data
    id_input = soup.select_one('#identificacion')
    if id_input:
        result['paciente']['identificacion'] = id_input.get('value', '')

    # Exams selected
    container = soup.select_one('#examenes-seleccionados')
    if container:
        for row in container.select('tbody tr'):
            cells = row.find_all('td')
            if len(cells) < 2:
                continue

            nombre = cells[0].get_text(strip=True)
            valor = cells[1].get_text(strip=True)
            badge = cells[0].select_one('.badge')
            estado = badge.get_text(strip=True) if badge else None

            if nombre:
                result['examenes'].append({
                    'nombre': nombre.replace(estado, '').strip() if estado else nombre,
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
    print("TEST: extract_ordenes_list (BeautifulSoup)")
    print(f"{'='*70}")
    print(f"  HTML file: {html_file.name}")

    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()

    result = extract_ordenes_from_html(html_content)

    print(f"\n  Results:")
    print(f"    Total ordenes extracted: {len(result)}")

    if result:
        print(f"\n  Sample order (first):")
        for key, value in result[0].items():
            print(f"    {key}: {value}")

        expected_fields = ['num', 'fecha', 'cedula', 'paciente', 'estado', 'id']
        missing = [f for f in expected_fields if f not in result[0]]
        if missing:
            print(f"\n  WARNING: Missing fields: {missing}")
            return False
        else:
            print(f"\n  All expected fields present!")
            return True
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
    print("TEST: extract_reportes (BeautifulSoup)")
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
        for exam in examenes:
            campos = exam.get('campos', [])
            print(f"    - {exam.get('nombre', 'N/A')} ({len(campos)} campos)")
            if campos:
                sample = campos[0]
                print(f"      Sample: {sample.get('f', 'N/A')} [{sample.get('tipo', '?')}] = {sample.get('val', 'N/A')}")
                if sample.get('opciones'):
                    print(f"        Opciones: {sample['opciones'][:3]}...")

        print(f"\n  Extraction successful!")
        return True
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
    print("TEST: extract_orden_edit (BeautifulSoup)")
    print(f"{'='*70}")
    print(f"  HTML file: {html_file.name}")

    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()

    result = extract_orden_edit_from_html(html_content)

    print(f"\n  Results:")
    print(f"    Numero orden: {result.get('numero_orden', 'N/A')}")
    print(f"    Paciente ID: {result.get('paciente', {}).get('identificacion', 'N/A')}")
    print(f"    Total examenes: {len(result.get('examenes', []))}")

    examenes = result.get('examenes', [])
    if examenes:
        print(f"\n  Examenes en la orden:")
        for exam in examenes[:5]:
            print(f"    - {exam.get('nombre', 'N/A')} - {exam.get('valor', 'N/A')}")
        if len(examenes) > 5:
            print(f"    ... y {len(examenes) - 5} más")

    print(f"\n  Extraction successful!")
    return True


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("EXTRACTOR TESTS WITH SAVED HTML FILES (BeautifulSoup)")
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
        print(f"\n  {total - passed} test(s) failed.")


if __name__ == "__main__":
    main()
