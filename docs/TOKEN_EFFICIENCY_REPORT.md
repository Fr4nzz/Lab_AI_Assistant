# Token Efficiency Report: get_order_results Tool

## Executive Summary

The `get_order_results` tool currently returns verbose JSON. Testing with real HTML data from order 2501181 (17 exams, 46 fields) shows:

| Format | Characters | Est. Tokens | Savings |
|--------|-----------|-------------|---------|
| **Current (verbose)** | 5,920 | ~1,480 | baseline |
| **Compact (~3 char keys)** | 3,799 | ~949 | **35.8%** |
| Minimal (2 char keys) | 3,573 | ~893 | 39.6% |

**Recommendation**: Use the **Compact format** with ~3 character abbreviations for a good balance of token savings (36%) and AI readability.

---

## Test Methodology

A Python test script (`backend/test_token_efficiency.py`) was created to:
1. Parse actual HTML files from the application (restored from commit d193bae)
2. Extract data using logic equivalent to `EXTRACT_REPORTES_JS`
3. Compare output formats and character counts

**Test data**: `html_samples/reportes_2501181_20251223_182051.html`
- 17 exams
- 46 fields total
- Real patient data

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

### Current Output Structure (5,920 chars)

```json
{
  "orders": [{
    "order_num": "2501181",
    "tab_ready": true,
    "numero_orden": null,
    "paciente": "CHANDI VILLARROEL, Franz Alexander",
    "examenes": [
      {
        "nombre": "BIOMETRÍA HEMÁTICA",
        "estado": "Validado",
        "tipo_muestra": "Sangre Total EDTA",
        "campos": [
          {"f": "Recuento de Glóbulos Rojos", "tipo": "input", "val": "5.81", "opciones": null, "ref": "[5 - 6.5]10^6/µL"},
          {"f": "Hemoglobina", "tipo": "input", "val": "16.4", "opciones": null, "ref": "[14.5 - 18.5]g/dL"},
          {"f": "Hematocrito", "tipo": "input", "val": "50", "opciones": null, "ref": "[45 - 55]%"}
        ]
      }
    ]
  }],
  "total": 1,
  "tip": "Use edit_results() with order_num to edit these results."
}
```

### Token Waste Identified

| Issue | Waste per occurrence | Total waste (46 fields) |
|-------|---------------------|------------------------|
| `"tipo": "input"` for every field | 16 chars | ~736 chars |
| `"opciones": null` for inputs | 17 chars | ~782 chars |
| `"tipo_muestra": "..."` per exam | ~25 chars | ~425 chars |
| `"tab_ready": true` | 18 chars | 18 chars |
| `"tip": "Use edit_results..."` | 55 chars | 55 chars |
| Duplicate `numero_orden`/`order_num` | ~25 chars | 25 chars |

**Total estimated waste: ~2,000+ chars (34%)**

---

## Proposed Format: Compact (~3 char keys)

### Key Abbreviations (AI-Friendly)

| Current Key | Compact Key | Meaning |
|-------------|-------------|---------|
| `paciente` | `pat` | Patient name |
| `examenes` | `exm` | Exams list |
| `nombre` | `nam` | Exam name |
| `estado` | `sts` | Status (Val/Pnd) |
| `campos` | `fld` | Fields list |
| field name | `fnm` | Field name |
| `val` | `val` | Value (unchanged) |
| `ref` | `ref` | Reference (unchanged, only if present) |
| `opciones` | `opt` | Options (only for selects) |

### Proposed Output Structure (3,799 chars)

```json
{
  "ord": "2501181",
  "pat": "CHANDI VILLARROEL, Franz Alexander",
  "exm": [
    {
      "nam": "BIOMETRÍA HEMÁTICA",
      "sts": "Val",
      "fld": [
        {"fnm": "Recuento de Glóbulos Rojos", "val": "5.81", "ref": "[5 - 6.5]10^6/µL"},
        {"fnm": "Hemoglobina", "val": "16.4", "ref": "[14.5 - 18.5]g/dL"},
        {"fnm": "Hematocrito", "val": "50", "ref": "[45 - 55]%"}
      ]
    }
  ]
}
```

### Key Optimizations

1. **Remove wrapper objects**: No `"orders": [...]`, `"total"`, `"tip"`
2. **Remove redundant fields**: No `"tipo"`, `"tipo_muestra"`, `"tab_ready"`, `"numero_orden"`
3. **Omit null values**: `"opciones": null` removed for input fields
4. **Abbreviated status**: `"Val"` instead of `"Validado"`, `"Pnd"` instead of `"Pendiente"`
5. **~3 char keys**: Readable abbreviations that any AI can understand

---

## Actual Test Results

### Full Comparison (17 exams, 46 fields)

```
FORMAT COMPARISON (minified JSON - actual tool output):
------------------------------------------------------------
CURRENT (verbose):
  Characters: 5,920
  Est. Tokens: 1,480

COMPACT (~3 char keys):
  Characters: 3,799
  Est. Tokens: 949
  Savings: 35.8%

MINIMAL (2 char keys):
  Characters: 3,573
  Est. Tokens: 893
  Savings: 39.6%
```

### Why ~3 char keys over 2 char keys?

The difference between 3-char and 2-char keys is only **~4% additional savings** (39.6% vs 35.8%), but 3-char keys are significantly more readable:

| 2-char | 3-char | Readability |
|--------|--------|-------------|
| `nm` | `nam` | "nam" clearly means "name" |
| `st` | `sts` | "sts" clearly means "status" |
| `fl` | `fld` | "fld" clearly means "field" |
| `fn` | `fnm` | "fnm" clearly means "field name" |
| `vl` | `val` | "val" clearly means "value" |
| `rf` | `ref` | "ref" clearly means "reference" |

For cheaper/simpler AI models, the extra readability of 3-char keys is worth the small token cost.

---

## Implementation Plan

### Step 1: Update EXTRACT_REPORTES_JS (extractors.py)

```javascript
EXTRACT_REPORTES_JS = r"""
() => {
    const exm = [];
    let current = null;

    document.querySelectorAll('tr.examen, tr.parametro').forEach(row => {
        if (row.classList.contains('examen')) {
            if (current && current.fld.length > 0) exm.push(current);

            const strong = row.querySelector('strong');
            const nam = strong?.innerText?.trim() || '';

            const badge = row.querySelector('.badge');
            const estadoText = badge?.innerText?.trim();
            const sts = estadoText === 'Validado' ? 'Val' :
                       estadoText === 'Pendiente' ? 'Pnd' : null;

            current = { nam, sts, fld: [] };
        } else if (row.classList.contains('parametro') && current) {
            const cells = row.querySelectorAll('td');
            if (cells.length < 2) return;

            const fnm = cells[0]?.innerText?.trim();
            const select = cells[1]?.querySelector('select');
            const input = cells[1]?.querySelector('input');
            if (!select && !input) return;

            const campo = { fnm };

            if (select) {
                const selOpt = select.options[select.selectedIndex];
                campo.val = selOpt?.text || '';
                campo.opt = Array.from(select.options)
                    .map(o => o.text.trim())
                    .filter(t => t);
            } else {
                campo.val = input.value;
            }

            // Only include ref if present
            const ref = cells[2]?.innerText?.trim();
            if (ref) campo.ref = ref;

            current.fld.push(campo);
        }
    });

    if (current && current.fld.length > 0) exm.push(current);

    // Order number from URL
    let ord = null;
    const urlMatch = window.location.search.match(/numeroOrden=(\d+)/);
    if (urlMatch) ord = urlMatch[1];

    // Patient name
    let pat = null;
    document.querySelectorAll('span.paciente').forEach(span => {
        const text = span.innerText?.trim();
        if (text && text !== 'Paciente' && text.length > 3) pat = text;
    });

    return { ord, pat, exm };
}
"""
```

### Step 2: Update _get_order_results_impl (tools.py)

```python
async def _get_order_results_impl(order_nums: List[str] = None, tab_indices: List[int] = None) -> dict:
    # ... existing logic ...

    # Simplified return - no wrapper for single order
    if len(results) == 1:
        return results[0]
    return {"orders": results}
```

### Step 3: Update Tool Docstring

```python
@tool
async def get_order_results(order_nums: List[str] = None, tab_indices: List[int] = None) -> str:
    """Get exam results for editing.

    Args:
        order_nums: Order numbers to fetch (opens/reuses tabs)
        tab_indices: Tab indices to read from (from CONTEXT)

    Returns compact format:
        ord: order number
        pat: patient name
        exm: [{nam: exam name, sts: Val|Pnd, fld: [{fnm, val, ref?, opt?}]}]

    Use edit_results(data=[{orden, e, f, v}]) to edit.
    """
```

---

## edit_results Compatibility

The `edit_results` tool input format remains unchanged:

```python
{"orden": "2501181", "e": "BIOMETRÍA HEMÁTICA", "f": "Hemoglobina", "v": "16.5"}
```

The AI reads with compact keys (`fnm`, `val`) but writes with the existing format (`e`, `f`, `v`).

---

## Test Script Usage

Run the test script to verify token savings:

```bash
cd backend
python3 test_token_efficiency.py
```

Output shows character counts, token estimates, and sample outputs for comparison.

---

## Conclusion

**Recommended: Compact format with ~3 char keys**

- **35.8% token reduction** (5,920 → 3,799 chars)
- **~530 tokens saved** per tool call
- Readable abbreviations for cheaper AI models
- Backward compatible with edit_results
- Only 4% less efficient than minimal 2-char format, but much more readable

The ~3 char abbreviations (`nam`, `sts`, `fld`, `fnm`, `val`, `ref`, `opt`) are intuitive enough that any AI model can understand them without confusion.
