# POInvoiceMatcher

Purchase Order to Invoice Verification backend processor.

## Archetype

Email-forward-first AP invoice ingestion: suppliers email invoices in as attachments, such as PDF, Excel, CSV, or plain text. This module extracts structured invoice records for a downstream poller to verify against purchase orders.

## What the poller expects as input

The poller calls `process_file(file_bytes)` with raw file bytes from an attachment or upload. `process_file` returns a list of records:

```python
[
    {
        "title": "vendor_name",
        "status": "Needs Review",
        "details": {},
        "due_date": "YYYY-MM-DD or None"
    }
]
```

`details` may include `vendor_name`, `invoice_number`, `invoice_date`, `due_date`, `purchase_order_number`, `po_line_item_reference`, `item_code`, `item_description`, `quantity_invoiced`, `unit_price`, `line_amount`, `tax_amount`, `freight_amount`, `discount_amount`, `invoice_total`, `currency`, `payment_terms`, `vendor_tax_id`, and `line_items`.

## Files

- `processor.py` — main `process_file(file_bytes)` extraction entry point.
- `run_demo.py` — hardcoded CSV demo.
- `run_tests.py` — lightweight CSV and plain-text tests.
- `requirements.txt` — Python dependencies.

## Supported file formats

- PDF
- Excel
- CSV
- Plain text

Dashboard: https://poinvoicematcher-purchase-order-to-invoi.vokrix.co
Vercel: poinvoicematcher-purchase-order-to-invoi
Railway: poinvoicematcher-purchase-order-to-invoi
Cloudflare: poinvoicematcher-purchase-order-to-invoi.vokrix.co
