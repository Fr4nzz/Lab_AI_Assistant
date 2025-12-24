"""
Preview how data looks when sent to AI.
Compares OLD verbose format vs NEW optimized format.
"""
from pathlib import Path
import json

SCRIPT_DIR = Path(__file__).parent.absolute()
HTML_SAMPLES_DIR = SCRIPT_DIR / "html_samples"

# Import extraction functions
from test_extractors_static import (
    extract_ordenes_from_html,
    extract_reportes_from_html,
    extract_orden_edit_from_html
)

# Import optimized formatters
from context_formatters import (
    format_ordenes_context,
    format_reportes_context,
    format_orden_edit_context
)


# ============================================================
# OLD FORMAT (verbose)
# ============================================================

def format_ordenes_OLD(data: list) -> str:
    """OLD: Verbose format."""
    lines = []
    lines.append(f"## Órdenes Recientes ({len(data)} órdenes)")
    lines.append("")

    for i, orden in enumerate(data[:10]):
        lines.append(f"### Orden #{orden['num']}")
        lines.append(f"- **ID interno**: {orden['id']}")
        lines.append(f"- **Fecha**: {orden['fecha']}")
        lines.append(f"- **Paciente**: {orden['paciente']}")
        lines.append(f"- **Cédula**: {orden['cedula']}")
        lines.append(f"- **Sexo/Edad**: {orden['sexo']}/{orden['edad']}")
        lines.append(f"- **Estado**: {orden['estado']}")
        lines.append(f"- **Valor**: {orden['valor']}")
        lines.append("")

    return "\n".join(lines)


def format_reportes_OLD(data: dict) -> str:
    """OLD: Shows ALL fields with full detail."""
    lines = []
    lines.append(f"## Reportes - Orden #{data.get('numero_orden', 'N/A')}")
    lines.append(f"**Paciente**: {data.get('paciente', 'N/A')}")
    lines.append("")

    for exam in data.get('examenes', []):
        estado = f" [{exam['estado']}]" if exam.get('estado') else ""
        lines.append(f"#### {exam['nombre']}{estado}")

        for campo in exam.get('campos', []):
            ref = f" (ref: {campo['ref']})" if campo.get('ref') else ""
            val = campo.get('val', '')
            lines.append(f"  - {campo['f']}: **{val}**{ref}")
        lines.append("")

    return "\n".join(lines)


def format_orden_edit_OLD(data: dict) -> str:
    """OLD: Verbose format."""
    lines = []
    lines.append(f"## Editar Orden #{data.get('numero_orden', 'N/A')}")
    lines.append("")

    paciente = data.get('paciente', {})
    lines.append("### Paciente")
    lines.append(f"- **Nombre**: {paciente.get('nombres', 'N/A')}")
    lines.append(f"- **Cédula**: {paciente.get('identificacion', 'N/A')}")
    lines.append("")

    lines.append(f"### Exámenes en la orden ({len(data.get('examenes', []))})")
    for exam in data.get('examenes', []):
        codigo = f"[{exam['codigo']}] " if exam.get('codigo') else ""
        estado = f" - {exam['estado']}" if exam.get('estado') else ""
        lines.append(f"  - {codigo}{exam['nombre']}{estado}")

    return "\n".join(lines)


# ============================================================
# COMPARISON
# ============================================================

def compare_formats(name: str, old_text: str, new_text: str):
    """Compare old vs new format with token estimation."""
    old_tokens = len(old_text) // 4
    new_tokens = len(new_text) // 4
    savings = old_tokens - new_tokens
    pct = (savings / old_tokens * 100) if old_tokens > 0 else 0

    print(f"\n{'='*70}")
    print(f"COMPARISON: {name}")
    print(f"{'='*70}")

    print(f"\n--- OLD FORMAT ({old_tokens} tokens) ---")
    print(old_text[:1500])
    if len(old_text) > 1500:
        print("... [truncated]")

    print(f"\n--- NEW FORMAT ({new_tokens} tokens) ---")
    print(new_text[:1500])
    if len(new_text) > 1500:
        print("... [truncated]")

    print(f"\n📊 Token savings: {savings} tokens ({pct:.1f}% reduction)")


def main():
    print("\n" + "="*70)
    print("AI CONTEXT FORMAT COMPARISON: OLD vs NEW")
    print("="*70)

    # Load HTML files
    ordenes_html = (HTML_SAMPLES_DIR / "ordenes_lista_20251223_182035.html").read_text(encoding='utf-8')
    reportes_html = (HTML_SAMPLES_DIR / "reportes_2501181_20251223_182051.html").read_text(encoding='utf-8')
    edit_html = (HTML_SAMPLES_DIR / "edit_orden_2501181_20251223_182019.html").read_text(encoding='utf-8')

    # Extract data
    ordenes_data = extract_ordenes_from_html(ordenes_html)
    reportes_data = extract_reportes_from_html(reportes_html)
    edit_data = extract_orden_edit_from_html(edit_html)

    # 1. Compare Ordenes
    old_ordenes = format_ordenes_OLD(ordenes_data)
    new_ordenes = format_ordenes_context(ordenes_data)
    compare_formats("ORDENES", old_ordenes, new_ordenes)

    # 2. Compare Reportes
    old_reportes = format_reportes_OLD(reportes_data)
    new_reportes = format_reportes_context(reportes_data)
    compare_formats("REPORTES (full)", old_reportes, new_reportes)

    # 3. Reportes - empty only mode
    new_reportes_empty = format_reportes_context(reportes_data, show_empty_only=True)
    compare_formats("REPORTES (empty fields only)", old_reportes, new_reportes_empty)

    # 4. Compare Orden Edit
    old_edit = format_orden_edit_OLD(edit_data)
    new_edit = format_orden_edit_context(edit_data)
    compare_formats("ORDEN EDIT", old_edit, new_edit)

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)

    old_total = len(old_ordenes) + len(old_reportes) + len(old_edit)
    new_total = len(new_ordenes) + len(new_reportes) + len(new_edit)
    new_empty = len(new_ordenes) + len(new_reportes_empty) + len(new_edit)

    print(f"\n  OLD total: ~{old_total//4} tokens")
    print(f"  NEW total: ~{new_total//4} tokens")
    print(f"  NEW (empty only): ~{new_empty//4} tokens")
    print(f"\n  Savings: {(old_total - new_total)//4} tokens ({(1 - new_total/old_total)*100:.1f}%)")
    print(f"  Savings (empty only): {(old_total - new_empty)//4} tokens ({(1 - new_empty/old_total)*100:.1f}%)")


if __name__ == "__main__":
    main()
