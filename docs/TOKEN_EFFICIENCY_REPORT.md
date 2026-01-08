# Token Efficiency Report: get_order_results Tool

## Executive Summary

The `get_order_results` tool currently returns verbose JSON (~6500 chars for a typical order with 17 exams). This report analyzes the current implementation and proposes optimizations to reduce token usage by **40-60%** while maintaining readability.

---

## Current Implementation Analysis

### Data Flow

```
HTML Page (reportes2)
    ↓
EXTRACT_REPORTES_JS (extractors.py:108-200)
    ↓
_get_order_results_impl (tools.py:615-699)
    ↓
get_order_results (tools.py:1225-1231)
    ↓
JSON string response to AI
```

### Current Output Structure

```json
{
  "orders": [{
    "order_num": "2501181",
    "tab_ready": true,
    "numero_orden": "2501181",
    "paciente": "MARTINEZ LOPEZ JUAN CARLOS",
    "examenes": [
      {
        "nombre": "BIOMETRIA HEMATICA COMPLETA",
        "estado": "Pendiente",
        "tipo_muestra": "Sangre Total EDTA",
        "campos": [
          {"f": "Globulos Blancos", "tipo": "input", "val": "", "opciones": null, "ref": "5.0 - 10.0 x10^3/uL"},
          {"f": "Globulos Rojos", "tipo": "input", "val": "", "opciones": null, "ref": "4.5 - 5.5 x10^6/uL"},
          {"f": "Hemoglobina", "tipo": "input", "val": "", "opciones": null, "ref": "12.0 - 16.0 g/dL"},
          {"f": "Hematocrito", "tipo": "input", "val": "", "opciones": null, "ref": "37.0 - 47.0 %"}
        ]
      },
      {
        "nombre": "COLESTEROL TOTAL",
        "estado": "Validado",
        "tipo_muestra": "Suero",
        "campos": [
          {"f": "Resultado", "tipo": "input", "val": "185", "opciones": null, "ref": "< 200 mg/dL"}
        ]
      }
    ]
  }],
  "total": 1,
  "tip": "Use edit_results() with order_num to edit these results."
}
```

### Token Waste Identified

| Issue | Example | Waste |
|-------|---------|-------|
| Duplicate order number | `"order_num"` and `"numero_orden"` | ~25 chars |
| `"tipo": "input"` for every field | `"tipo": "input"` | ~16 chars × N fields |
| `"opciones": null` for inputs | `"opciones": null` | ~17 chars × N fields |
| `"tipo_muestra"` not used for editing | `"tipo_muestra": "Suero"` | ~25 chars × N exams |
| Full status text | `"estado": "Pendiente"` | vs `"s": "P"` |
| Verbose tip every time | `"tip": "Use edit_results()..."` | ~50 chars |
| `"tab_ready": true` when always true | `"tab_ready": true` | ~18 chars |

---

## Proposed Optimizations

### Level 1: Quick Wins (Minimal Code Changes)

#### 1.1 Remove Redundant Fields

```javascript
// Before
{
  "order_num": "2501181",
  "numero_orden": "2501181",  // REMOVE - duplicate
  "tab_ready": true,          // REMOVE - always true when returned
  ...
}

// After
{
  "orden": "2501181",
  ...
}
```

#### 1.2 Abbreviate Status

```javascript
// Before
"estado": "Pendiente"
"estado": "Validado"

// After
"s": "P"  // Pendiente
"s": "V"  // Validado
```

#### 1.3 Remove Null Values

```javascript
// Before - for input fields
{"f": "Hemoglobina", "tipo": "input", "val": "", "opciones": null, "ref": "12-16 g/dL"}

// After - only include non-null
{"f": "Hemoglobina", "v": "", "r": "12-16 g/dL"}
```

#### 1.4 Only Include Options for Selects

```javascript
// Before
{"f": "Aspecto", "tipo": "select", "val": "Claro", "opciones": ["Claro", "Turbio", "Hemolizado"]}

// After - selects indicated by presence of 'o' key
{"f": "Aspecto", "v": "Claro", "o": ["Claro", "Turbio", "Hemolizado"]}
```

### Level 2: Structure Optimization

#### 2.1 Compact Exam Format

```json
{
  "orden": "2501181",
  "pac": "MARTINEZ LOPEZ JUAN CARLOS",
  "exs": [
    {
      "n": "BIOMETRIA HEMATICA COMPLETA",
      "s": "P",
      "c": [
        {"f": "Globulos Blancos", "v": "", "r": "5-10"},
        {"f": "Globulos Rojos", "v": "", "r": "4.5-5.5"},
        {"f": "Hemoglobina", "v": "", "r": "12-16"},
        {"f": "Hematocrito", "v": "", "r": "37-47"}
      ]
    }
  ]
}
```

Key changes:
- `"paciente"` → `"pac"`
- `"examenes"` → `"exs"`
- `"nombre"` → `"n"`
- `"estado"` → `"s"` (with P/V values)
- `"campos"` → `"c"`
- `"val"` → `"v"`
- `"ref"` → `"r"`
- Remove `"tipo"`, `"opciones"` (null), `"tipo_muestra"`, `"tab_ready"`

#### 2.2 Simplified Reference Values

```javascript
// Before
"ref": "5.0 - 10.0 x10^3/uL"

// After - only range numbers
"r": "5-10"  // Units are standard for each field, AI can learn them
```

### Level 3: Advanced Optimizations (Optional)

#### 3.1 Array-Based Field Format

```json
{
  "orden": "2501181",
  "pac": "MARTINEZ LOPEZ",
  "exs": {
    "BIOMETRIA HEMATICA": {
      "s": "P",
      "c": [
        ["Globulos Blancos", "", "5-10"],
        ["Globulos Rojos", "", "4.5-5.5"],
        ["Hemoglobina", "", "12-16"]
      ]
    }
  }
}
```

Each campo: `[field_name, value, reference]`

#### 3.2 Only Return Changed/Empty Fields

If the AI is primarily editing empty fields:

```json
{
  "orden": "2501181",
  "empty": [
    {"ex": "BIOMETRIA", "f": "Globulos Blancos", "r": "5-10"},
    {"ex": "BIOMETRIA", "f": "Globulos Rojos", "r": "4.5-5.5"}
  ],
  "filled": 15,
  "total": 18
}
```

---

## Token Comparison

### Sample Order: 17 exams, 18 parameters

| Format | Est. Chars | Est. Tokens | Savings |
|--------|-----------|-------------|---------|
| Current (verbose) | 6,533 | ~1,633 | baseline |
| Level 1 (quick wins) | 4,500 | ~1,125 | **31%** |
| Level 2 (compact) | 3,200 | ~800 | **51%** |
| Level 3 (array-based) | 2,400 | ~600 | **63%** |

*Token estimate: ~4 chars per token for JSON*

---

## Recommended Implementation

### Phase 1: Immediate (Low Risk)

Modify `EXTRACT_REPORTES_JS` in `extractors.py`:

```javascript
// extractors.py - Updated EXTRACT_REPORTES_JS
() => {
    const exs = [];
    let current = null;

    document.querySelectorAll('tr.examen, tr.parametro').forEach(row => {
        if (row.classList.contains('examen')) {
            if (current && current.c.length > 0) exs.push(current);

            const nombre = row.querySelector('strong')?.innerText?.trim() || '';
            const badge = row.querySelector('.badge');
            const estado = badge?.innerText?.trim();

            current = {
                n: nombre,
                s: estado === 'Validado' ? 'V' : estado === 'Pendiente' ? 'P' : null,
                c: []
            };
        } else if (row.classList.contains('parametro') && current) {
            const cells = row.querySelectorAll('td');
            if (cells.length < 2) return;

            const f = cells[0]?.innerText?.trim();
            const select = cells[1]?.querySelector('select');
            const input = cells[1]?.querySelector('input');
            if (!select && !input) return;

            const campo = { f };

            if (select) {
                campo.v = select.options[select.selectedIndex]?.text || '';
                campo.o = Array.from(select.options).map(o => o.text.trim()).filter(t => t);
            } else {
                campo.v = input.value;
            }

            // Only include ref if present
            const ref = cells[2]?.innerText?.trim();
            if (ref) campo.r = ref;

            current.c.push(campo);
        }
    });

    if (current && current.c.length > 0) exs.push(current);

    let orden = null;
    const urlMatch = window.location.search.match(/numeroOrden=(\d+)/);
    if (urlMatch) orden = urlMatch[1];

    let pac = null;
    document.querySelectorAll('span.paciente').forEach(span => {
        const text = span.innerText?.trim();
        if (text && text !== 'Paciente' && text.length > 3) pac = text;
    });

    return { orden, pac, exs };
}
```

### Phase 2: Update Tool Output

Modify `_get_order_results_impl` in `tools.py`:

```python
# Remove tip from every response, use docstring instead
return {
    "orders": results,
    "count": len(results)
}

# Or even simpler for single order:
return results[0] if len(results) == 1 else {"orders": results}
```

### Phase 3: Update Tool Docstring

```python
@tool
async def get_order_results(order_nums: List[str] = None, tab_indices: List[int] = None) -> str:
    """Get exam results for editing.

    Returns:
      orden: order number
      pac: patient name
      exs: [{n: exam, s: P|V status, c: [{f: field, v: value, r: ref?, o: options?}]}]

    Use edit_results(data=[{orden, e, f, v}]) to edit values.
    """
```

---

## edit_results Compatibility

The `edit_results` tool expects:
```python
{"orden": "2501181", "e": "BIOMETRIA", "f": "Globulos Blancos", "v": "7.5"}
```

This remains compatible - we're just changing the GET format, not the EDIT format.

---

## Conclusion

**Recommended approach: Level 2 (Compact Format)**

- **51% token reduction** with minimal complexity
- Maintains readability and intuitive structure
- Backward compatible with edit_results
- AI can easily understand abbreviated keys through tool docstring

The abbreviated keys (`n`, `s`, `c`, `f`, `v`, `r`, `o`) are documented in the tool docstring, making them intuitive for the AI while reducing token usage significantly.
