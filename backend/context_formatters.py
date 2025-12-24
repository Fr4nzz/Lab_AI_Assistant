"""
Context Formatters - Format extracted data for AI consumption.
Optimized for minimal tokens while maintaining clarity.
"""
from typing import List, Dict, Any


def format_ordenes_context(data: List[Dict], limit: int = 10) -> str:
    """
    Format ordenes list as compact table.
    ~30 tokens per order instead of ~50.
    """
    lines = []
    lines.append(f"# Órdenes Recientes ({len(data)} total)")
    lines.append("")
    lines.append("| # | Orden | Paciente | Cédula | S/E | Estado | ID |")
    lines.append("|---|-------|----------|--------|-----|--------|-----|")

    for i, o in enumerate(data[:limit]):
        sexo_edad = f"{o.get('sexo', '?')}/{o.get('edad', '?')}"
        paciente = (o.get('paciente', '') or '')[:25]  # Truncate long names
        lines.append(
            f"| {i+1} | {o['num']} | {paciente} | {o['cedula']} | {sexo_edad} | {o['estado']} | {o['id']} |"
        )

    lines.append("")
    lines.append("*Usa el ID interno para get_orden() o add_exam()*")

    return "\n".join(lines)


def format_reportes_context(data: Dict, show_empty_only: bool = False) -> str:
    """
    Format reportes data. Option to show only empty fields (fields to fill).

    Args:
        data: Extracted reportes data
        show_empty_only: If True, only show fields that need to be filled
    """
    lines = []

    # Header with order and patient info
    orden = data.get('numero_orden') or 'N/A'
    paciente = data.get('paciente') or 'N/A'
    lines.append(f"# Reportes - Orden {orden}")
    lines.append(f"**Paciente**: {paciente}")
    lines.append("")

    examenes = data.get('examenes', [])

    # Count total and empty fields
    total_campos = 0
    campos_vacios = 0

    for exam in examenes:
        for campo in exam.get('campos', []):
            total_campos += 1
            if not campo.get('val'):
                campos_vacios += 1

    lines.append(f"**Resumen**: {len(examenes)} exámenes, {total_campos} campos ({campos_vacios} vacíos)")
    lines.append("")

    for exam in examenes:
        estado = f"[{exam['estado']}]" if exam.get('estado') else "[Pendiente]"
        muestra = f"({exam['tipo_muestra']})" if exam.get('tipo_muestra') else ""

        campos = exam.get('campos', [])
        campos_con_valor = [c for c in campos if c.get('val')]
        campos_sin_valor = [c for c in campos if not c.get('val')]

        lines.append(f"## {exam['nombre']} {estado} {muestra}")

        if show_empty_only:
            # Only show empty fields (what needs to be filled)
            if campos_sin_valor:
                lines.append("**Campos por llenar:**")
                for c in campos_sin_valor:
                    tipo = "select" if c.get('tipo') == 'select' else "input"
                    opciones = ""
                    if c.get('opciones'):
                        opciones = f" → Opciones: {', '.join(c['opciones'][:5])}"
                    lines.append(f"  - {c['f']} [{tipo}]{opciones}")
            else:
                lines.append("✓ Completo")
        else:
            # Show all fields compactly
            if campos:
                # Group by filled/empty
                if campos_con_valor:
                    vals = [f"{c['f']}={c['val']}" for c in campos_con_valor[:8]]
                    if len(campos_con_valor) > 8:
                        vals.append(f"...+{len(campos_con_valor)-8} más")
                    lines.append(f"  Valores: {', '.join(vals)}")

                if campos_sin_valor:
                    empty = [c['f'] for c in campos_sin_valor]
                    lines.append(f"  **Vacíos**: {', '.join(empty)}")

        lines.append("")

    return "\n".join(lines)


def format_orden_edit_context(data: Dict) -> str:
    """Format orden edit data compactly."""
    lines = []

    orden = data.get('numero_orden') or 'N/A'
    paciente = data.get('paciente', {})
    nombre = paciente.get('nombres') or 'N/A'
    cedula = paciente.get('identificacion') or 'N/A'

    lines.append(f"# Editar Orden {orden}")
    lines.append(f"**Paciente**: {nombre} ({cedula})")
    lines.append("")

    examenes = data.get('examenes', [])
    lines.append(f"## Exámenes ({len(examenes)})")

    # Group by status
    validados = [e for e in examenes if e.get('estado') == 'Validado']
    pendientes = [e for e in examenes if e.get('estado') != 'Validado']

    if pendientes:
        lines.append("**Pendientes:**")
        for e in pendientes:
            codigo = f"[{e['codigo']}]" if e.get('codigo') else ""
            lines.append(f"  - {codigo} {e['nombre']}")

    if validados:
        codes = [e.get('codigo', e['nombre'][:3]) for e in validados]
        lines.append(f"**Validados**: {', '.join(codes)}")

    # Totales
    totales = data.get('totales', {})
    if totales.get('total'):
        lines.append(f"\n**Total**: {totales['total']}")

    return "\n".join(lines)


def format_for_fill_operation(exam_name: str, campos: List[Dict]) -> str:
    """
    Format a single exam's fields for a fill operation.
    Used when AI needs to show what it will fill.
    """
    lines = []
    lines.append(f"## {exam_name}")

    for c in campos:
        if c.get('tipo') == 'select':
            opciones = c.get('opciones', [])
            lines.append(f"  {c['f']}: [{c.get('val', '_')}] → {', '.join(opciones[:5])}")
        else:
            ref = f"(ref: {c['ref']})" if c.get('ref') else ""
            lines.append(f"  {c['f']}: [{c.get('val', '_')}] {ref}")

    return "\n".join(lines)


def format_compact_json(data: Dict, page_type: str) -> str:
    """
    Format data as compact JSON for minimum tokens.
    Best for when AI needs raw data access.
    """
    import json

    if page_type == "ordenes":
        # Compact order format
        compact = []
        for o in data.get('ordenes', [])[:10]:
            compact.append({
                "n": o['num'],
                "p": o.get('paciente', '')[:20],
                "c": o['cedula'],
                "s": o.get('sexo'),
                "e": o.get('edad'),
                "st": o['estado'],
                "id": o['id']
            })
        return json.dumps({"ordenes": compact}, ensure_ascii=False)

    elif page_type == "reportes":
        # Compact reportes: only show structure, not all values
        compact = {
            "orden": data.get('numero_orden'),
            "paciente": data.get('paciente'),
            "examenes": []
        }
        for ex in data.get('examenes', []):
            campos_info = []
            for c in ex.get('campos', []):
                campos_info.append({
                    "f": c['f'],
                    "t": c['tipo'][0],  # 'i' or 's'
                    "v": c.get('val', ''),
                    "empty": not bool(c.get('val'))
                })
            compact["examenes"].append({
                "nombre": ex['nombre'],
                "estado": ex.get('estado'),
                "campos": campos_info
            })
        return json.dumps(compact, ensure_ascii=False, indent=2)

    else:
        return json.dumps(data, ensure_ascii=False, indent=2)
