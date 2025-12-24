"""
Analyze HTML structure to understand extraction patterns.
"""
from pathlib import Path
from bs4 import BeautifulSoup
import re

SCRIPT_DIR = Path(__file__).parent.absolute()
HTML_SAMPLES_DIR = SCRIPT_DIR / "html_samples"


def analyze_ordenes():
    """Analyze ordenes HTML structure."""
    html_file = HTML_SAMPLES_DIR / "ordenes_lista_20251223_182035.html"

    with open(html_file, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'lxml')

    print("\n" + "="*70)
    print("ANALYZING ORDENES HTML STRUCTURE")
    print("="*70)

    # Find main table
    tables = soup.find_all('table')
    print(f"\nTotal tables: {len(tables)}")

    for i, table in enumerate(tables[:3]):
        print(f"\n--- Table {i} ---")
        thead = table.find('thead')
        if thead:
            headers = [th.get_text(strip=True) for th in thead.find_all('th')]
            print(f"Headers: {headers}")

        tbody = table.find('tbody')
        if tbody:
            rows = tbody.find_all('tr')
            print(f"Rows in tbody: {len(rows)}")

            if rows:
                # Analyze first row
                first_row = rows[0]
                cells = first_row.find_all('td')
                print(f"\nFirst row cells ({len(cells)}):")

                for j, cell in enumerate(cells):
                    text = cell.get_text(separator='|', strip=True)[:100]
                    classes = cell.get('class', [])
                    print(f"  Cell {j}: classes={classes}")
                    print(f"    Text: {text}")

                    # Check for data-registro
                    dr = cell.find(attrs={'data-registro': True})
                    if dr:
                        print(f"    data-registro found!")


def analyze_reportes():
    """Analyze reportes HTML structure."""
    html_file = HTML_SAMPLES_DIR / "reportes_2501181_20251223_182051.html"

    with open(html_file, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'lxml')

    print("\n" + "="*70)
    print("ANALYZING REPORTES HTML STRUCTURE")
    print("="*70)

    # Find exam rows
    exam_rows = soup.find_all('tr', class_='examen')
    param_rows = soup.find_all('tr', class_='parametro')

    print(f"\nExam rows (tr.examen): {len(exam_rows)}")
    print(f"Parameter rows (tr.parametro): {len(param_rows)}")

    if exam_rows:
        print("\n--- First exam row structure ---")
        first_exam = exam_rows[0]
        cells = first_exam.find_all('td')
        print(f"Cells: {len(cells)}")

        for j, cell in enumerate(cells):
            print(f"\n  Cell {j}:")
            # Get direct text (not nested)
            direct_text = ''.join(cell.find_all(string=True, recursive=False)).strip()
            full_text = cell.get_text(separator='|', strip=True)[:80]

            # Find strong tag
            strong = cell.find('strong')
            if strong:
                print(f"    <strong>: {strong.get_text(strip=True)}")

            # Find badge
            badge = cell.find(class_='badge')
            if badge:
                print(f"    .badge: {badge.get_text(strip=True)}")

            print(f"    Full text: {full_text}")

    if param_rows:
        print("\n--- First parameter row structure ---")
        first_param = param_rows[0]
        cells = first_param.find_all('td')
        print(f"Cells: {len(cells)}")

        for j, cell in enumerate(cells):
            text = cell.get_text(strip=True)[:60]
            inp = cell.find('input')
            sel = cell.find('select')
            print(f"  Cell {j}: {text}")
            if inp:
                print(f"    <input> value: {inp.get('value', '')}")
            if sel:
                selected = sel.find('option', selected=True)
                print(f"    <select> selected: {selected.get_text(strip=True) if selected else 'none'}")


def analyze_orden_edit():
    """Analyze orden edit HTML structure."""
    html_file = HTML_SAMPLES_DIR / "edit_orden_2501181_20251223_182019.html"

    with open(html_file, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'lxml')

    print("\n" + "="*70)
    print("ANALYZING ORDEN EDIT HTML STRUCTURE")
    print("="*70)

    # Find patient identification
    id_input = soup.find('input', id='identificacion')
    print(f"\n#identificacion: {id_input.get('value') if id_input else 'NOT FOUND'}")

    # Find nombres
    nombres_input = soup.find('input', id='nombres')
    print(f"#nombres: {nombres_input.get('value') if nombres_input else 'NOT FOUND'}")

    apellidos_input = soup.find('input', id='apellidos')
    print(f"#apellidos: {apellidos_input.get('value') if apellidos_input else 'NOT FOUND'}")

    # Find order number in title/header
    headers = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5'])
    print(f"\nHeaders found: {len(headers)}")
    for h in headers[:5]:
        text = h.get_text(strip=True)[:80]
        print(f"  {h.name}: {text}")

    # Find breadcrumb or title with order number
    breadcrumb = soup.find(class_='breadcrumb')
    if breadcrumb:
        print(f"\nBreadcrumb: {breadcrumb.get_text(strip=True)[:80]}")

    # Find card-header
    card_headers = soup.find_all(class_='card-header')
    print(f"\nCard headers: {len(card_headers)}")
    for ch in card_headers[:3]:
        text = ch.get_text(strip=True)[:80]
        print(f"  {text}")

    # Find examenes-seleccionados
    exam_container = soup.find(id='examenes-seleccionados')
    if exam_container:
        print(f"\n#examenes-seleccionados found!")
        tbody = exam_container.find('tbody')
        if tbody:
            rows = tbody.find_all('tr')
            print(f"  Rows: {len(rows)}")
            if rows:
                first_row = rows[0]
                cells = first_row.find_all('td')
                print(f"\n  First row cells:")
                for j, cell in enumerate(cells):
                    text = cell.get_text(separator='|', strip=True)[:60]
                    print(f"    Cell {j}: {text}")
    else:
        # Try to find table with exams
        print("\n#examenes-seleccionados NOT FOUND, searching tables...")
        tables = soup.find_all('table')
        for i, table in enumerate(tables[:5]):
            tbody = table.find('tbody')
            if tbody and tbody.find_all('tr'):
                rows = tbody.find_all('tr')
                if len(rows) > 0:
                    first_text = rows[0].get_text(strip=True)[:60]
                    if 'BIOMETRÍA' in first_text or 'GLUCOSA' in first_text:
                        print(f"  Table {i} might be exams table!")
                        print(f"    First row: {first_text}")


if __name__ == "__main__":
    analyze_ordenes()
    analyze_reportes()
    analyze_orden_edit()
