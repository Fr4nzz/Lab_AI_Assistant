"""
Test extractors using saved HTML files.
This allows Claude Code to validate extraction logic without live browser access.
"""
import asyncio
import sys
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from playwright.async_api import async_playwright

# Paths
SCRIPT_DIR = Path(__file__).parent.absolute()
HTML_SAMPLES_DIR = SCRIPT_DIR / "html_samples"

# Import extraction JavaScript from extractors.py
from extractors import EXTRACT_ORDENES_JS, EXTRACT_REPORTES_JS, EXTRACT_ORDEN_EDIT_JS


async def test_extract_ordenes():
    """Test extraction of ordenes list from saved HTML."""
    html_file = HTML_SAMPLES_DIR / "ordenes_lista_20251223_182035.html"

    if not html_file.exists():
        print(f"  HTML file not found: {html_file}")
        return False

    print(f"\n{'='*70}")
    print("TEST: extract_ordenes_list")
    print(f"{'='*70}")
    print(f"  HTML file: {html_file.name}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Load local HTML file
        await page.goto(f"file://{html_file}")
        await page.wait_for_timeout(500)

        # Execute extraction
        result = await page.evaluate(EXTRACT_ORDENES_JS)

        await browser.close()

    print(f"\n  Results:")
    print(f"    Total ordenes extracted: {len(result)}")

    if len(result) > 0:
        print(f"\n  Sample order (first):")
        for key, value in result[0].items():
            print(f"    {key}: {value}")

        # Validate expected fields
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


async def test_extract_reportes():
    """Test extraction of reportes data from saved HTML."""
    html_file = HTML_SAMPLES_DIR / "reportes_2501181_20251223_182051.html"

    if not html_file.exists():
        print(f"  HTML file not found: {html_file}")
        return False

    print(f"\n{'='*70}")
    print("TEST: extract_reportes")
    print(f"{'='*70}")
    print(f"  HTML file: {html_file.name}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Load local HTML file
        await page.goto(f"file://{html_file}")
        await page.wait_for_timeout(500)

        # Execute extraction
        result = await page.evaluate(EXTRACT_REPORTES_JS)

        await browser.close()

    print(f"\n  Results:")
    print(f"    Numero orden: {result.get('numero_orden', 'N/A')}")
    print(f"    Paciente: {result.get('paciente', 'N/A')}")
    print(f"    Total examenes: {len(result.get('examenes', []))}")

    examenes = result.get('examenes', [])
    if examenes:
        print(f"\n  Examenes encontrados:")
        for exam in examenes:
            print(f"    - {exam.get('nombre', 'N/A')} ({len(exam.get('campos', []))} campos)")
            if exam.get('campos'):
                print(f"      Sample field: {exam['campos'][0].get('f', 'N/A')} = {exam['campos'][0].get('val', 'N/A')}")

        # Validate structure
        has_campos = any(len(e.get('campos', [])) > 0 for e in examenes)
        if not has_campos:
            print("\n  WARNING: No fields found in exams!")
            return False
        else:
            print(f"\n  Extraction successful!")
            return True
    else:
        print("  WARNING: No exams extracted!")
        return False


async def test_extract_orden_edit():
    """Test extraction of orden edit page from saved HTML."""
    html_file = HTML_SAMPLES_DIR / "edit_orden_2501181_20251223_182019.html"

    if not html_file.exists():
        print(f"  HTML file not found: {html_file}")
        return False

    print(f"\n{'='*70}")
    print("TEST: extract_orden_edit")
    print(f"{'='*70}")
    print(f"  HTML file: {html_file.name}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Load local HTML file
        await page.goto(f"file://{html_file}")
        await page.wait_for_timeout(500)

        # Execute extraction
        result = await page.evaluate(EXTRACT_ORDEN_EDIT_JS)

        await browser.close()

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
    else:
        print("  INFO: No exams found (may be empty order)")
        return True  # Not necessarily an error


async def test_fill_field_js():
    """Test the fill field JavaScript on reportes page."""
    html_file = HTML_SAMPLES_DIR / "reportes_2501181_20251223_182051.html"

    if not html_file.exists():
        print(f"  HTML file not found: {html_file}")
        return False

    print(f"\n{'='*70}")
    print("TEST: fill_field JavaScript")
    print(f"{'='*70}")
    print(f"  HTML file: {html_file.name}")

    # JavaScript to fill a field (simplified version for testing)
    fill_js = r"""
    (params) => {
        const rows = document.querySelectorAll('tr.parametro');

        for (const row of rows) {
            const labelCell = row.querySelector('td:first-child');
            const labelText = labelCell?.innerText?.trim();

            if (!labelText || !labelText.toLowerCase().includes(params.f.toLowerCase())) {
                continue;
            }

            const input = row.querySelector('input');
            const select = row.querySelector('select');

            if (input) {
                const prev = input.value;
                input.value = params.v;
                return {field: labelText, prev: prev, new: params.v, type: 'input'};
            } else if (select) {
                const prev = select.options[select.selectedIndex]?.text || '';
                for (const opt of select.options) {
                    if (opt.text.toLowerCase().includes(params.v.toLowerCase())) {
                        select.value = opt.value;
                        return {field: labelText, prev: prev, new: opt.text, type: 'select'};
                    }
                }
                return {err: 'Option not found: ' + params.v};
            }
        }
        return {err: 'Field not found: ' + params.f};
    }
    """

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(f"file://{html_file}")
        await page.wait_for_timeout(500)

        # Test cases
        test_cases = [
            {"f": "Hemoglobina", "v": "15.5"},
            {"f": "Color", "v": "Amarillo"},
            {"f": "Aspecto", "v": "Transparente"},
        ]

        print(f"\n  Fill test results:")
        all_passed = True

        for tc in test_cases:
            result = await page.evaluate(fill_js, tc)
            if "err" in result:
                print(f"    FAIL: {tc['f']} -> {result['err']}")
                all_passed = False
            else:
                print(f"    OK: {result.get('field', 'N/A')} ({result.get('type', '?')}) = {result.get('prev', '?')} -> {result.get('new', '?')}")

        await browser.close()

    if all_passed:
        print(f"\n  All fill tests passed!")
    else:
        print(f"\n  Some tests failed!")

    return all_passed


async def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("EXTRACTOR TESTS WITH SAVED HTML FILES")
    print("="*70)

    # Check HTML samples directory
    if not HTML_SAMPLES_DIR.exists():
        print(f"\n ERROR: HTML samples directory not found: {HTML_SAMPLES_DIR}")
        print("  Please run the inspect_*.py scripts first to generate HTML samples.")
        return

    html_files = list(HTML_SAMPLES_DIR.glob("*.html"))
    print(f"\n Found {len(html_files)} HTML sample files:")
    for f in html_files:
        print(f"  - {f.name}")

    # Run tests
    results = {}

    results['ordenes'] = await test_extract_ordenes()
    results['reportes'] = await test_extract_reportes()
    results['orden_edit'] = await test_extract_orden_edit()
    results['fill_field'] = await test_fill_field_js()

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
        print(f"\n  {total - passed} test(s) failed. Check output above for details.")


if __name__ == "__main__":
    asyncio.run(main())
