"""Bounded, read-only inventory tools for the assistant."""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import date, datetime

from langchain_core.tools import tool
from sqlalchemy import text

from ai_service.config import (
    AI_DB_STATEMENT_TIMEOUT_MS,
    AI_READ_ONLY,
    AI_TOOL_MAX_MOVEMENTS,
    AI_TOOL_MAX_ROWS,
)
from ai_service.db import SessionLocal

logger = logging.getLogger(__name__)


def _limit(value: int, maximum: int) -> int:
    return max(1, min(value, maximum))


def _iso_date(value: str) -> str:
    """Normalize user/model dates before passing them to PostgreSQL."""
    value = value.strip()
    if not value:
        return ''

    for date_format in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
        try:
            return datetime.strptime(value, date_format).date().isoformat()
        except ValueError:
            continue

    raise ValueError(
        f'Invalid date format: {value}. Use DD/MM/YYYY or YYYY-MM-DD.'
    )


async def _fetch_all(query: str, params: dict) -> list[dict]:
    if SessionLocal is None:
        raise RuntimeError('Database tools are not configured.')
    if not AI_READ_ONLY:
        raise RuntimeError('Read-only tools are disabled by configuration.')

    started = time.perf_counter()
    operation_match = re.search(r'\bFROM\s+([a-z_]+)', query, re.IGNORECASE)
    operation = operation_match.group(1) if operation_match else 'query'
    try:
        async with SessionLocal() as session:
            async with session.begin():
                await session.execute(
                    text(f'SET LOCAL statement_timeout = {int(AI_DB_STATEMENT_TIMEOUT_MS)}')
                )
                query_started = time.perf_counter()
                result = await session.execute(text(query), params)
                rows = [dict(row) for row in result.mappings().all()]
                query_elapsed_ms = (time.perf_counter() - query_started) * 1000

        logger.info(
            'Database tool completed operation=%s query_elapsed_ms=%.1f total_elapsed_ms=%.1f rows=%s',
            operation,
            query_elapsed_ms,
            (time.perf_counter() - started) * 1000,
            len(rows),
        )
        return rows
    except Exception:
        logger.exception(
            'Database tool failed operation=%s total_elapsed_ms=%.1f',
            operation,
            (time.perf_counter() - started) * 1000,
        )
        raise


def _json(data: object) -> str:
    return json.dumps(data, default=str, ensure_ascii=False)


@tool
async def get_inventory_summary() -> str:
    """Return product count, total units, low-stock count, and out-of-stock count."""
    rows = await _fetch_all(
        """
        SELECT
            COUNT(*) AS product_count,
            COALESCE(SUM(quantity_in_stock), 0) AS total_units,
            COUNT(*) FILTER (WHERE quantity_in_stock <= reorder_level) AS low_stock_count,
            COUNT(*) FILTER (WHERE quantity_in_stock = 0) AS out_of_stock_count
        FROM products
        """,
        {},
    )
    return _json(rows[0])


@tool
async def search_products(
    query: str = '',
    category: str = '',
    low_stock_only: bool = False,
    limit: int = 20,
) -> str:
    """Search products by SKU/name/category and optionally return only low-stock products."""
    rows = await _fetch_all(
        """
        SELECT p.sku, p.name, c.name AS category, p.quantity_in_stock,
               p.reorder_level, p.description
        FROM products p
        JOIN categories c ON c.id = p.category_id
        WHERE (:query = '' OR p.sku ILIKE :pattern OR p.name ILIKE :pattern)
          AND (:category = '' OR c.name ILIKE :category_pattern)
          AND (NOT :low_stock_only OR p.quantity_in_stock <= p.reorder_level)
        ORDER BY p.name
        LIMIT :limit
        """,
        {
            'query': query.strip(),
            'pattern': f'%{query.strip()}%',
            'category': category.strip(),
            'category_pattern': f'%{category.strip()}%',
            'low_stock_only': low_stock_only,
            'limit': _limit(limit, AI_TOOL_MAX_ROWS),
        },
    )
    return _json(rows)


@tool
async def get_product_stock(sku: str) -> str:
    """Return current stock and reorder information for one product SKU."""
    rows = await _fetch_all(
        """
        SELECT p.sku, p.name, c.name AS category, p.quantity_in_stock,
               p.reorder_level,
               CASE WHEN p.quantity_in_stock <= p.reorder_level THEN true ELSE false END
                   AS needs_reorder
        FROM products p
        JOIN categories c ON c.id = p.category_id
        WHERE p.sku ILIKE :sku
        LIMIT 1
        """,
        {'sku': sku.strip()},
    )
    return _json(rows[0] if rows else {'found': False, 'sku': sku})


@tool
async def list_stock_movements(
    sku: str = '',
    movement_type: str = '',
    days: int = 30,
    date_from: str = '',
    date_to: str = '',
    performed_by: str = '',
    limit: int = 50,
) -> str:
    """List stock movements, optionally filtered by SKU, type, date range, or user."""
    safe_days = max(1, min(days, 365))
    normalized_date_from = _iso_date(date_from)
    normalized_date_to = _iso_date(date_to)
    rows = await _fetch_all(
        """
        SELECT sm.created_at, p.sku, p.name, sm.movement_type, sm.quantity,
               sm.reference_note, sm.purchase_order_id, sm.sales_order_id,
               u.username AS performed_by
        FROM stock_movements sm
        JOIN products p ON p.id = sm.product_id
        JOIN users u ON u.id = sm.performed_by_id
        WHERE sm.created_at >= CURRENT_TIMESTAMP - (:days * INTERVAL '1 day')
          AND (:sku = '' OR p.sku ILIKE :sku)
          AND (:movement_type = '' OR sm.movement_type = :movement_type)
          AND (:date_from = '' OR sm.created_at >= CAST(:date_from AS date))
          AND (:date_to = '' OR sm.created_at < CAST(:date_to AS date) + INTERVAL '1 day')
          AND (:performed_by = '' OR u.username ILIKE :performed_by_pattern)
        ORDER BY sm.created_at DESC
        LIMIT :limit
        """,
        {
            'days': safe_days,
            'sku': sku.strip(),
            'movement_type': movement_type.strip().lower(),
            'date_from': normalized_date_from,
            'date_to': normalized_date_to,
            'performed_by': performed_by.strip(),
            'performed_by_pattern': f'%{performed_by.strip()}%',
            'limit': _limit(limit, AI_TOOL_MAX_MOVEMENTS),
        },
    )
    return _json(rows)


@tool
async def list_purchase_orders(
    status: str = '',
    supplier: str = '',
    date_from: str = '',
    date_to: str = '',
    created_by: str = '',
    limit: int = 20,
) -> str:
    """List purchase orders, optionally filtered by status, supplier, date range, or creator."""
    normalized_date_from = _iso_date(date_from)
    normalized_date_to = _iso_date(date_to)
    rows = await _fetch_all(
        """
        SELECT po.id, po.status, po.is_direct, po.created_at, po.received_at,
               s.name AS supplier, u.username AS created_by,
               COUNT(poi.id) AS line_count,
               COALESCE(SUM(poi.quantity), 0) AS total_units
        FROM purchase_orders po
        JOIN suppliers s ON s.id = po.supplier_id
        JOIN users u ON u.id = po.created_by_id
        LEFT JOIN purchase_order_items poi ON poi.purchase_order_id = po.id
        WHERE (:status = '' OR po.status = :status)
          AND (:supplier = '' OR s.name ILIKE :supplier_pattern)
          AND (:date_from = '' OR po.created_at >= CAST(:date_from AS date))
          AND (:date_to = '' OR po.created_at < CAST(:date_to AS date) + INTERVAL '1 day')
          AND (:created_by = '' OR u.username ILIKE :created_by_pattern)
        GROUP BY po.id, s.name, u.username
        ORDER BY po.created_at DESC
        LIMIT :limit
        """,
        {
            'status': status.strip().lower(),
            'supplier': supplier.strip(),
            'supplier_pattern': f'%{supplier.strip()}%',
            'date_from': normalized_date_from,
            'date_to': normalized_date_to,
            'created_by': created_by.strip(),
            'created_by_pattern': f'%{created_by.strip()}%',
            'limit': _limit(limit, AI_TOOL_MAX_ROWS),
        },
    )
    return _json(rows)


@tool
async def list_sales_orders(
    status: str = '',
    customer: str = '',
    date_from: str = '',
    date_to: str = '',
    created_by: str = '',
    limit: int = 20,
) -> str:
    """List sales orders, optionally filtered by status, customer, date range, or creator."""
    normalized_date_from = _iso_date(date_from)
    normalized_date_to = _iso_date(date_to)
    rows = await _fetch_all(
        """
        SELECT so.id, so.status, so.is_direct, so.created_at, so.dispatched_at,
               c.name AS customer, u.username AS created_by,
               COUNT(soi.id) AS line_count,
               COALESCE(SUM(soi.quantity), 0) AS total_units
        FROM sales_orders so
        JOIN customers c ON c.id = so.customer_id
        JOIN users u ON u.id = so.created_by_id
        LEFT JOIN sales_order_items soi ON soi.sales_order_id = so.id
        WHERE (:status = '' OR so.status = :status)
          AND (:customer = '' OR c.name ILIKE :customer_pattern)
          AND (:date_from = '' OR so.created_at >= CAST(:date_from AS date))
          AND (:date_to = '' OR so.created_at < CAST(:date_to AS date) + INTERVAL '1 day')
          AND (:created_by = '' OR u.username ILIKE :created_by_pattern)
        GROUP BY so.id, c.name, u.username
        ORDER BY so.created_at DESC
        LIMIT :limit
        """,
        {
            'status': status.strip().lower(),
            'customer': customer.strip(),
            'customer_pattern': f'%{customer.strip()}%',
            'date_from': normalized_date_from,
            'date_to': normalized_date_to,
            'created_by': created_by.strip(),
            'created_by_pattern': f'%{created_by.strip()}%',
            'limit': _limit(limit, AI_TOOL_MAX_ROWS),
        },
    )
    return _json(rows)


@tool
async def find_pending_dispatches(
    date_from: str = '',
    date_to: str = '',
    created_by: str = '',
    limit: int = 20,
) -> str:
    """Find pending sales orders and show which product quantities are short for dispatch."""
    normalized_date_from = _iso_date(date_from)
    normalized_date_to = _iso_date(date_to)
    rows = await _fetch_all(
        """
        SELECT so.id AS sales_order_id, so.created_at, c.name AS customer,
               u.username AS created_by, p.sku, p.name AS product,
               soi.quantity AS ordered_quantity, p.quantity_in_stock,
               GREATEST(soi.quantity - p.quantity_in_stock, 0) AS shortage
        FROM sales_orders so
        JOIN customers c ON c.id = so.customer_id
        JOIN users u ON u.id = so.created_by_id
        JOIN sales_order_items soi ON soi.sales_order_id = so.id
        JOIN products p ON p.id = soi.product_id
        WHERE so.status = 'pending'
          AND soi.quantity > p.quantity_in_stock
          AND (:date_from = '' OR so.created_at >= CAST(:date_from AS date))
          AND (:date_to = '' OR so.created_at < CAST(:date_to AS date) + INTERVAL '1 day')
          AND (:created_by = '' OR u.username ILIKE :created_by_pattern)
        ORDER BY so.created_at DESC, so.id, p.name
        LIMIT :limit
        """,
        {
            'date_from': normalized_date_from,
            'date_to': normalized_date_to,
            'created_by': created_by.strip(),
            'created_by_pattern': f'%{created_by.strip()}%',
            'limit': _limit(limit, AI_TOOL_MAX_ROWS),
        },
    )
    return _json(rows)


@tool
async def search_suppliers(query: str = '', limit: int = 20) -> str:
    """Search suppliers by name, email, phone, or address."""
    rows = await _fetch_all(
        """
        SELECT id, name, email, phone, address, created_at
        FROM suppliers
        WHERE (:query = '' OR name ILIKE :pattern OR email ILIKE :pattern
               OR phone ILIKE :pattern OR address ILIKE :pattern)
        ORDER BY name
        LIMIT :limit
        """,
        {'query': query.strip(), 'pattern': f'%{query.strip()}%', 'limit': _limit(limit, AI_TOOL_MAX_ROWS)},
    )
    return _json(rows)


@tool
async def search_customers(query: str = '', limit: int = 20) -> str:
    """Search customers by name, email, phone, or address."""
    rows = await _fetch_all(
        """
        SELECT id, name, email, phone, address, created_at
        FROM customers
        WHERE (:query = '' OR name ILIKE :pattern OR email ILIKE :pattern
               OR phone ILIKE :pattern OR address ILIKE :pattern)
        ORDER BY name
        LIMIT :limit
        """,
        {'query': query.strip(), 'pattern': f'%{query.strip()}%', 'limit': _limit(limit, AI_TOOL_MAX_ROWS)},
    )
    return _json(rows)


@tool
async def get_recent_activity(days: int = 30, limit: int = 30) -> str:
    """Return a compact recent activity feed combining stock movements and order events."""
    safe_days = max(1, min(days, 365))
    rows = await _fetch_all(
        """
        SELECT created_at, event_type, reference, status, party, units
        FROM (
            SELECT sm.created_at, 'stock_movement' AS event_type,
                   COALESCE(sm.reference_note, sm.movement_type) AS reference,
                   sm.movement_type AS status, p.name AS party, sm.quantity AS units
            FROM stock_movements sm
            JOIN products p ON p.id = sm.product_id
            WHERE sm.created_at >= CURRENT_TIMESTAMP - (:days * INTERVAL '1 day')
            UNION ALL
            SELECT po.created_at, 'purchase_order', 'Purchase #' || po.id,
                   po.status, s.name, COALESCE(SUM(poi.quantity), 0)
            FROM purchase_orders po
            JOIN suppliers s ON s.id = po.supplier_id
            LEFT JOIN purchase_order_items poi ON poi.purchase_order_id = po.id
            WHERE po.created_at >= CURRENT_TIMESTAMP - (:days * INTERVAL '1 day')
            GROUP BY po.id, s.name
            UNION ALL
            SELECT so.created_at, 'sales_order', 'Sale #' || so.id,
                   so.status, c.name, COALESCE(SUM(soi.quantity), 0)
            FROM sales_orders so
            JOIN customers c ON c.id = so.customer_id
            LEFT JOIN sales_order_items soi ON soi.sales_order_id = so.id
            WHERE so.created_at >= CURRENT_TIMESTAMP - (:days * INTERVAL '1 day')
            GROUP BY so.id, c.name
        ) activity
        ORDER BY created_at DESC
        LIMIT :limit
        """,
        {'days': safe_days, 'limit': _limit(limit, AI_TOOL_MAX_ROWS)},
    )
    return _json(rows)


READ_ONLY_TOOLS = [
    get_inventory_summary,
    search_products,
    get_product_stock,
    list_stock_movements,
    list_purchase_orders,
    list_sales_orders,
    find_pending_dispatches,
    search_suppliers,
    search_customers,
    get_recent_activity,
]
