#!/usr/bin/env python3
"""
Process tarifas CSV to generate curated exam list.

Usage:
    python process_tarifas.py <input_csv> [output_csv]

Example:
    python process_tarifas.py ../tarifas-2025-12-25-05-56-18.csv
    python process_tarifas.py ../tarifas-2025-12-25-05-56-18.csv lista_de_examenes.csv

This script:
1. Reads the tarifas CSV (header on line 5, semicolon-separated)
2. Merges rows with same Código (Descuento + Particular prices)
3. Outputs a clean CSV with unique exams and both prices
"""
import csv
import sys
import re
from pathlib import Path
from collections import defaultdict


def parse_price(price_str: str) -> float:
    """Parse price string like '$17.00 ' to float."""
    if not price_str:
        return 0.0
    # Remove $ and whitespace, then convert
    cleaned = re.sub(r'[$\s]', '', price_str)
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def process_tarifas(input_path: str, output_path: str = None):
    """
    Process tarifas CSV and generate curated exam list.

    Args:
        input_path: Path to input tarifas CSV
        output_path: Path to output CSV (default: backend/config/lista_de_examenes.csv)
    """
    input_file = Path(input_path)
    if not input_file.exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)

    # Default output path
    if output_path is None:
        output_path = Path(__file__).parent.parent / "config" / "lista_de_examenes.csv"
    else:
        output_path = Path(output_path)

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Store exams by code
    exams = defaultdict(lambda: {
        'codigo': '',
        'nombre': '',
        'seccion': '',
        'tiempo': '',
        'muestra': '',
        'tecnica': '',
        'precio_particular': 0.0,
        'precio_descuento': 0.0,
    })

    print(f"Reading: {input_file}")

    with open(input_file, 'r', encoding='utf-8-sig') as f:
        # Skip first 4 lines (header info)
        for _ in range(4):
            next(f)

        reader = csv.DictReader(f, delimiter=';')
        row_count = 0

        for row in reader:
            row_count += 1
            codigo = row.get('Código', '').strip()
            if not codigo:
                continue

            tarifa = row.get('Tarifa', '').strip()
            precio = parse_price(row.get('Valor', ''))

            # Store exam info (use first occurrence for metadata)
            if not exams[codigo]['codigo']:
                exams[codigo]['codigo'] = codigo
                exams[codigo]['nombre'] = row.get('Examen', '').strip()
                exams[codigo]['seccion'] = row.get('Sección', '').strip()
                exams[codigo]['tiempo'] = row.get('Tiempo de procesamiento', '').strip()
                exams[codigo]['muestra'] = row.get('Muestras', '').strip()
                exams[codigo]['tecnica'] = row.get('Técnica', '').strip()

            # Store price based on tarifa type
            if 'Descuento' in tarifa:
                exams[codigo]['precio_descuento'] = precio
            elif 'Particular' in tarifa:
                exams[codigo]['precio_particular'] = precio

    print(f"Processed {row_count} rows, found {len(exams)} unique exams")

    # Sort by section then by name
    sorted_exams = sorted(exams.values(), key=lambda x: (x['seccion'], x['nombre']))

    # Write output CSV
    fieldnames = ['codigo', 'nombre', 'seccion', 'precio_particular', 'precio_descuento', 'tiempo', 'muestra', 'tecnica']

    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for exam in sorted_exams:
            writer.writerow(exam)

    print(f"Output: {output_path}")
    print(f"Total exams: {len(sorted_exams)}")

    # Print summary by section
    sections = defaultdict(int)
    for exam in sorted_exams:
        sections[exam['seccion']] += 1

    print("\nExams by section:")
    for section, count in sorted(sections.items()):
        print(f"  {section}: {count}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python process_tarifas.py <input_csv> [output_csv]")
        print("Example: python process_tarifas.py ../../tarifas-2025-12-25-05-56-18.csv")
        sys.exit(1)

    input_csv = sys.argv[1]
    output_csv = sys.argv[2] if len(sys.argv) > 2 else None

    process_tarifas(input_csv, output_csv)
