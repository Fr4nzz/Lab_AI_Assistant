"""
Orders cache module for fuzzy search and overlap detection.

This module manages a cached list of orders from the downloaded XLSX file
and provides fuzzy search functionality when exact matches fail.
"""
import csv
import logging
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
from datetime import datetime

try:
    from rapidfuzz import fuzz, process
except ImportError:
    fuzz = None
    process = None

logger = logging.getLogger(__name__)

# File paths
CONFIG_DIR = Path(__file__).parent / "config"
ORDERS_FILE = CONFIG_DIR / "lista_de_ordenes.csv"
ORDERS_LAST_UPDATE_FILE = CONFIG_DIR / "ordenes_last_update.txt"

# Cache
_cached_orders: List[Dict] = []
_orders_loaded: bool = False


def load_orders_cache() -> List[Dict]:
    """Load orders from CSV file into cache."""
    global _cached_orders, _orders_loaded

    if not ORDERS_FILE.exists():
        logger.warning(f"[OrdersCache] Orders file not found: {ORDERS_FILE}")
        _cached_orders = []
        _orders_loaded = True
        return _cached_orders

    orders = []
    try:
        with open(ORDERS_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                orders.append({
                    'order_num': row.get('order_num', ''),
                    'fecha': row.get('fecha', ''),
                    'patient_name': row.get('patient_name', ''),
                    'nombres': row.get('nombres', ''),
                    'apellidos': row.get('apellidos', ''),
                    'cedula': row.get('cedula', ''),
                    'examenes': row.get('examenes', ''),
                    'total': row.get('total', ''),
                })

        logger.info(f"[OrdersCache] Loaded {len(orders)} orders from cache")
        _cached_orders = orders
        _orders_loaded = True

    except Exception as e:
        logger.error(f"[OrdersCache] Error loading orders: {e}")
        _cached_orders = []
        _orders_loaded = True

    return _cached_orders


def get_cached_orders() -> List[Dict]:
    """Get cached orders, loading if not already loaded."""
    global _orders_loaded
    if not _orders_loaded:
        load_orders_cache()
    return _cached_orders


def reload_orders_cache() -> List[Dict]:
    """Force reload orders from file."""
    global _orders_loaded
    _orders_loaded = False
    return load_orders_cache()


def get_cached_order_nums() -> Set[str]:
    """Get set of all order numbers in cache."""
    orders = get_cached_orders()
    return {o['order_num'] for o in orders if o['order_num']}


def check_overlap(page1_order_nums: Set[str]) -> Tuple[bool, int]:
    """
    Check if page 1 orders overlap with cached orders.

    Args:
        page1_order_nums: Set of order numbers from page 1

    Returns:
        Tuple of (has_overlap, overlap_count)
    """
    cached_nums = get_cached_order_nums()
    if not cached_nums:
        return False, 0

    overlap = page1_order_nums & cached_nums
    return len(overlap) > 0, len(overlap)


def fuzzy_search_patient(
    query: str,
    min_score: int = 70,
    max_results: int = 10
) -> List[Dict]:
    """
    Fuzzy search for patient names in cached orders.

    Uses a hybrid approach:
    - Groups by unique patient name for diversity
    - Returns 1-2 most recent orders per unique patient
    - Limits to max_results total

    Args:
        query: Search query (patient name)
        min_score: Minimum similarity score (0-100)
        max_results: Maximum number of results

    Returns:
        List of matching orders with similarity scores
    """
    if not fuzz or not process:
        logger.warning("[OrdersCache] rapidfuzz not installed, fuzzy search disabled")
        return []

    orders = get_cached_orders()

    # If cache is empty but file exists, try reloading (handles race condition with background update)
    if not orders and ORDERS_FILE.exists():
        logger.info("[OrdersCache] Cache empty but file exists, reloading...")
        orders = reload_orders_cache()

    if not orders:
        return []

    # Create list of (patient_name, index) for fuzzy matching
    patient_names = []
    name_to_indices = {}  # Map name to list of order indices

    for i, order in enumerate(orders):
        name = order.get('patient_name', '').upper()
        if name:
            if name not in name_to_indices:
                name_to_indices[name] = []
                patient_names.append(name)
            name_to_indices[name].append(i)

    if not patient_names:
        return []

    # Normalize query
    query_upper = query.upper().strip()

    # Use rapidfuzz to find matches
    # Use token_set_ratio which handles word order differences well
    matches = process.extract(
        query_upper,
        patient_names,
        scorer=fuzz.token_set_ratio,
        limit=50  # Get more initially, then filter
    )

    # Filter by minimum score and group by unique patient
    results = []
    seen_patients = set()

    for match_name, score, _ in matches:
        if score < min_score:
            continue

        if match_name in seen_patients:
            continue

        seen_patients.add(match_name)

        # Get orders for this patient (most recent first)
        indices = name_to_indices.get(match_name, [])
        patient_orders = [orders[i] for i in indices[:2]]  # Max 2 orders per patient

        for order in patient_orders:
            results.append({
                'order_num': order['order_num'],
                'fecha': order['fecha'],
                'patient_name': order['patient_name'],
                'cedula': order['cedula'],
                'examenes': order['examenes'][:50] if order['examenes'] else '',
                'total': order['total'],
                'similarity_score': score,
            })

            if len(results) >= max_results:
                break

        if len(results) >= max_results:
            break

    return results


def merge_orders(
    page1_orders: List[Dict],
    cached_orders: List[Dict],
    max_orders: int = 20
) -> List[Dict]:
    """
    Merge page 1 orders with cached orders, deduplicated.

    Args:
        page1_orders: Orders from page 1 (most recent)
        cached_orders: Orders from cached file
        max_orders: Maximum number of orders to return

    Returns:
        Merged list of orders, most recent first
    """
    seen_nums = set()
    merged = []

    # First add page 1 orders (they are most recent)
    for order in page1_orders:
        num = order.get('num') or order.get('order_num', '')
        if num and num not in seen_nums:
            seen_nums.add(num)
            merged.append(order)

    # Then add cached orders that aren't already in page 1
    for order in cached_orders:
        num = order.get('order_num', '')
        if num and num not in seen_nums:
            seen_nums.add(num)
            # Convert cached order format to match page 1 format
            merged.append({
                'num': order.get('order_num', ''),
                'fecha': order.get('fecha', ''),
                'paciente': order.get('patient_name', ''),
                'cedula': order.get('cedula', ''),
                'estado': '',  # Not in cached data
                'id': '',  # Not in cached data
            })

    return merged[:max_orders]


def get_orders_last_update() -> Optional[str]:
    """Get timestamp of last orders update."""
    if ORDERS_LAST_UPDATE_FILE.exists():
        return ORDERS_LAST_UPDATE_FILE.read_text().strip()
    return None


def set_orders_last_update(timestamp: str = None):
    """Set timestamp of last orders update."""
    if timestamp is None:
        timestamp = datetime.now().isoformat()
    ORDERS_LAST_UPDATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    ORDERS_LAST_UPDATE_FILE.write_text(timestamp)


def format_fuzzy_results(results: List[Dict], query: str) -> str:
    """
    Format fuzzy search results for AI context.

    Args:
        results: List of fuzzy match results
        query: Original search query

    Returns:
        Formatted string for AI
    """
    if not results:
        return f"No se encontraron coincidencias para '{query}'."

    lines = [f"No se encontró coincidencia exacta para '{query}'. Sugerencias por similitud:"]
    lines.append("")

    for i, r in enumerate(results, 1):
        score = r.get('similarity_score', 0)
        lines.append(f"{i}. {r['patient_name']} ({score}% similitud)")
        lines.append(f"   └─ Ord. {r['order_num']} | {r['fecha']} | {r['examenes'][:40]}... | {r['total']}")
        lines.append("")

    lines.append("Usa search_orders con el nombre exacto de una sugerencia para obtener más detalles.")

    return "\n".join(lines)
