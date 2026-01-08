# Token Efficiency Report: All Lab Tools

## Executive Summary

Comprehensive analysis of ALL lab tools shows significant token savings potential:

| Tool | Current | Compact | Savings |
|------|---------|---------|---------|
| **get_order_results** OUTPUT | 5,920 | 3,799 | **35.8%** |
| **get_order_info** OUTPUT | 3,630 | 1,200 | **66.9%** |
| **edit_results** INPUT | 332 | 272 | **18.1%** |
| **edit_order_exams** OUTPUT | 528 | 205 | **61.2%** |
| **create_new_order** OUTPUT | 550 | 182 | **66.9%** |
| **TOTAL** | **10,960** | **5,658** | **48.4%** |

**Overall: 48.4% token reduction across all tools** (~1,325 tokens saved per typical workflow)

---

## Test Methodology

Test script: `backend/test_token_efficiency.py`

- Parses actual HTML files from the application
- Replicates JS extractor logic in Python
- Compares current vs compact formats for all tools
- Measures character counts (tokens ≈ chars/4)

Run tests: `cd backend && python3 test_token_efficiency.py`

---

## 1. get_order_results (OUTPUT)

### Current Format (5,920 chars)

```json
{
  "orders": [{
    "order_num": "2501181",
    "tab_ready": true,
    "numero_orden": null,
    "paciente": "CHANDI VILLARROEL, Franz Alexander",
    "examenes": [{
      "nombre": "BIOMETRÍA HEMÁTICA",
      "estado": "Validado",
      "tipo_muestra": "Sangre Total EDTA",
      "campos": [
        {"f": "Hemoglobina", "tipo": "input", "val": "16.4", "opciones": null, "ref": "[14.5 - 18.5]g/dL"}
      ]
    }]
  }],
  "total": 1,
  "tip": "Use edit_results() with order_num to edit these results."
}
```

### Compact Format (3,799 chars) - 35.8% savings

```json
{
  "ord": "2501181",
  "pat": "CHANDI VILLARROEL, Franz Alexander",
  "exm": [{
    "nam": "BIOMETRÍA HEMÁTICA",
    "sts": "Val",
    "fld": [
      {"fnm": "Hemoglobina", "val": "16.4", "ref": "[14.5 - 18.5]g/dL"}
    ]
  }]
}
```

### Optimizations Applied:
- Remove wrapper: `orders[]`, `total`, `tip`
- Remove redundant: `tab_ready`, `numero_orden`, `tipo_muestra`
- Remove nulls: `opciones: null`, `tipo: "input"`
- Abbreviate: `examenes` → `exm`, `nombre` → `nam`, `estado` → `sts`, `campos` → `fld`, `f` → `fnm`
- Status: `"Validado"` → `"Val"`, `"Pendiente"` → `"Pnd"`

---

## 2. get_order_info (OUTPUT)

### Current Format (3,630 chars)

```json
{
  "orders": [{
    "order_id": 12345,
    "tab_index": 0,
    "numero_orden": "12345",
    "paciente": {
      "identificacion": "1234567890",
      "nombres": "CHANDI VILLARROEL, Franz Alexander",
      "apellidos": null
    },
    "examenes": [
      {"codigo": "GLU", "nombre": "GLUCOSA BASAL", "valor": "$5.00", "estado": "Validado"}
    ],
    "totales": {"subtotal": null, "descuento": null, "total": "$50.00"},
    "exams": [...]  // DUPLICATED!
  }],
  "total": 1,
  "tip": "Use edit_order_exams() with order_id or tab_index to add/remove exams."
}
```

### Compact Format (1,200 chars) - 66.9% savings

```json
{
  "ord": "12345",
  "ced": "1234567890",
  "pat": "CHANDI VILLARROEL, Franz Alexander",
  "exm": [
    {"cod": "GLU", "nam": "GLUCOSA BASAL", "prc": "$5.00", "sts": "Val"}
  ]
}
```

### Optimizations Applied:
- Remove wrapper and duplicates: `orders[]`, `exams[]` (duplicate of `examenes`)
- Flatten patient: `paciente.identificacion` → `ced`, `paciente.nombres` → `pat`
- Remove nulls: `apellidos`, `subtotal`, `descuento`
- Remove metadata: `tab_index`, `tip`, `total`
- Abbreviate: `codigo` → `cod`, `valor` → `prc`

---

## 3. edit_results (INPUT)

### Current Format (332 chars for 6 edits)

```json
{
  "data": [
    {"orden": "2501181", "e": "BIOMETRÍA HEMÁTICA", "f": "Hemoglobina", "v": "16.5"},
    {"orden": "2501181", "e": "BIOMETRÍA HEMÁTICA", "f": "Hematocrito", "v": "50"}
  ]
}
```

### Compact Format (272 chars) - 18.1% savings

```json
{
  "data": [
    {"t": 1, "e": "BIOMETRÍA HEMÁTICA", "f": "Hemoglobina", "v": "16.5"},
    {"t": 1, "e": "BIOMETRÍA HEMÁTICA", "f": "Hematocrito", "v": "50"}
  ]
}
```

### Optimizations Applied:
- Use tab index `t` instead of `orden` (shorter, also avoids AI needing to remember order number)
- Keys already short (`e`, `f`, `v`)

### Note on Input Optimization
The edit_results input is already fairly efficient. The main improvement is using `t` (tab_index) instead of `orden` which:
1. Saves ~5 chars per edit (×N edits)
2. Is more reliable (AI doesn't need to remember/copy order number)
3. Works with already-opened tabs from CONTEXT

---

## 4. edit_order_exams (OUTPUT)

### Current Format (528 chars)

```json
{
  "identifier": "order_12345",
  "tab_index": null,
  "order_id": 12345,
  "is_new_order": false,
  "added": ["GLU", "BH"],
  "removed": ["EMO"],
  "failed_add": [],
  "failed_remove": [],
  "cedula_updated": true,
  "cedula": "1234567890",
  "current_exams": [
    {"codigo": "GLU", "nombre": "GLUCOSA BASAL", "valor": "$5.00", "estado": "Pendiente", "can_remove": true}
  ],
  "totals": {"total": "$13.00"},
  "status": "pending_save",
  "next_step": "Revisa los cambios y haz click en 'Guardar'."
}
```

### Compact Format (205 chars) - 61.2% savings

```json
{
  "ord": 12345,
  "add": ["GLU", "BH"],
  "rem": ["EMO"],
  "ced": "1234567890",
  "exm": [
    {"cod": "GLU", "nam": "GLUCOSA BASAL", "prc": "$5.00"}
  ],
  "tot": "$13.00",
  "sts": "save"
}
```

### Optimizations Applied:
- Remove redundant IDs: `identifier`, `tab_index` (use `ord` only)
- Remove booleans: `is_new_order`, `cedula_updated`, `can_remove`
- Remove empty arrays: `failed_add`, `failed_remove` (only include if non-empty)
- Remove verbose messages: `next_step`
- Flatten: `totals.total` → `tot`
- Abbreviate: `current_exams` → `exm`, `status` → `sts`

---

## 5. create_new_order (OUTPUT)

### Current Format (550 chars)

```json
{
  "success": true,
  "tab_index": 2,
  "is_cotizacion": false,
  "cedula": "1234567890",
  "added_exams": ["GLU", "BH", "EMO"],
  "failed_exams": [],
  "current_exams": [
    {"codigo": "GLU", "nombre": "GLUCOSA BASAL", "valor": "$5.00", "estado": null, "can_remove": true}
  ],
  "totals": {"total": "$17.00"},
  "status": "ready_to_save",
  "next_step": "Revisa los exámenes y haz click en 'Guardar'."
}
```

### Compact Format (182 chars) - 66.9% savings

```json
{
  "ok": true,
  "tab": 2,
  "ced": "1234567890",
  "add": ["GLU", "BH", "EMO"],
  "exm": [
    {"cod": "GLU", "prc": "$5.00"}
  ],
  "tot": "$17.00",
  "sts": "save"
}
```

### Optimizations Applied:
- Abbreviate: `success` → `ok`, `tab_index` → `tab`
- Remove nulls/empty: `is_cotizacion`, `failed_exams`, `estado: null`
- Simplify exams: Only `cod` and `prc` needed (name not useful post-add)
- Remove verbose: `next_step`, `can_remove`

---

## Key Abbreviations Reference

### Common Keys (Used Across Tools)

| Current | Compact | Meaning |
|---------|---------|---------|
| `order_num`, `order_id` | `ord` | Order number/ID |
| `paciente` | `pat` | Patient name |
| `cedula`, `identificacion` | `ced` | Cedula/ID |
| `examenes`, `exams` | `exm` | Exams list |
| `estado`, `status` | `sts` | Status |
| `total`, `totales.total` | `tot` | Total price |

### Exam/Field Keys

| Current | Compact | Meaning |
|---------|---------|---------|
| `nombre` | `nam` | Name |
| `codigo` | `cod` | Code |
| `campos` | `fld` | Fields list |
| field name (`f`) | `fnm` | Field name |
| `val` | `val` | Value (unchanged) |
| `ref` | `ref` | Reference (unchanged) |
| `opciones` | `opt` | Options (select only) |
| `valor` | `prc` | Price |

### Status Values

| Current | Compact |
|---------|---------|
| `"Validado"` | `"Val"` |
| `"Pendiente"` | `"Pnd"` |
| `"pending_save"` | `"save"` |

### Operation Keys

| Current | Compact | Meaning |
|---------|---------|---------|
| `added` | `add` | Added items |
| `removed` | `rem` | Removed items |
| `tab_index` | `tab` | Tab index |
| `success` | `ok` | Success flag |

---

## Implementation Plan

### Phase 1: Update Extractors (extractors.py)

Update JavaScript extractors to use compact keys:

1. **EXTRACT_REPORTES_JS** → Output compact format
2. **EXTRACT_ORDEN_EDIT_JS** → Output compact format
3. **EXTRACT_ADDED_EXAMS_JS** → Output compact format

### Phase 2: Update Tool Implementations (tools.py)

1. **_get_order_results_impl**: Remove wrapper, use compact data
2. **_get_order_info_impl**: Flatten structure, remove duplicates
3. **_edit_order_exams_impl**: Simplify output, remove verbose messages
4. **_create_order_impl**: Simplify output

### Phase 3: Update Tool Docstrings

Document compact key meanings in tool docstrings so AI understands the format:

```python
@tool
async def get_order_results(...) -> str:
    """Get exam results.

    Returns: {ord, pat, exm: [{nam, sts, fld: [{fnm, val, ref?, opt?}]}]}
    Keys: ord=order, pat=patient, exm=exams, nam=name, sts=Val|Pnd,
          fld=fields, fnm=field name, val=value, ref=reference, opt=options
    """
```

### Phase 4: Update edit_results Input Schema

Allow `t` as alias for `tab_index`:

```python
class EditResultsInput(BaseModel):
    data: List[Dict[str, str]] = Field(
        description="List of edits. Each: {t (tab_index) OR orden, e (exam), f (field), v (value)}"
    )
```

---

## Expected Impact

### Per Typical Workflow

A typical workflow involves:
1. `get_order_results` (1x) → Save ~530 tokens
2. `edit_results` (1x, ~10 edits) → Save ~30 tokens
3. `get_order_info` (1x) → Save ~607 tokens
4. `edit_order_exams` (1x) → Save ~80 tokens

**Total per workflow: ~1,247 tokens saved**

### Cost Impact

At $15/1M input tokens (Claude Sonnet):
- 1,247 tokens saved × 100 workflows/day = 124,700 tokens/day
- Monthly savings: ~$56/month

At $3/1M input tokens (Claude Haiku):
- Monthly savings: ~$11/month

The main benefit is **faster responses** and **longer context windows** rather than direct cost savings.

---

## Backward Compatibility

The `edit_results` input format remains compatible:
- Current: `{"orden": "2501181", "e": "...", "f": "...", "v": "..."}`
- Also accepts: `{"t": 1, "e": "...", "f": "...", "v": "..."}`

AI reads compact output but can write with either format.

---

## Conclusion

**Recommended: Implement all compact formats**

| Priority | Tool | Savings | Complexity |
|----------|------|---------|------------|
| HIGH | get_order_info | 66.9% | Low |
| HIGH | create_new_order | 66.9% | Low |
| HIGH | edit_order_exams | 61.2% | Low |
| MEDIUM | get_order_results | 35.8% | Medium |
| LOW | edit_results input | 18.1% | Low |

Total estimated savings: **48.4%** across all tool I/O

The ~3 character abbreviations (`nam`, `sts`, `fld`, `fnm`, `val`, `ref`, `opt`, `cod`, `prc`, etc.) are readable enough for any AI model while providing significant token savings.
