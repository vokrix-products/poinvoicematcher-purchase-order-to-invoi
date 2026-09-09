import csv
import io
import re
from datetime import datetime

import pdfplumber
import openpyxl


ITEM_KEYS = {"item_code", "item_description", "quantity_invoiced", "unit_price", "line_amount"}


def _normalize_header(value):
    if value is None:
        return ""
    value = str(value).strip().lower()
    value = re.sub(r"[\s_]+", " ", value)
    return value


def _map_header(header):
    h = _normalize_header(header)
    if not h:
        return None

    if "due" in h and "date" in h:
        return "due_date"
    if "invoice" in h and "date" in h:
        return "invoice_date"
    if "invoice" in h and ("number" in h or "no" in h or "#" in h or h == "invoice"):
        return "invoice_number"
    if "vendor" in h or "supplier" in h:
        return "vendor_name"
    if "remit" in h and "to" in h:
        return "remit_to_address"
    if "bill" in h and "to" in h:
        return "bill_to_address"
    if "ship" in h and "to" in h:
        return "ship_to_address"
    if "tax" in h and ("id" in h or "vat" in h or "ein" in h or "tin" in h):
        return "vendor_tax_id"
    if "purchase" in h or "po" in h:
        if "line" in h:
            return "po_line_item_reference"
        return "purchase_order_number"
    if "sku" in h or "product code" in h or ("item" in h and "code" in h):
        return "item_code"
    if "description" in h or h == "product":
        return "item_description"
    if "price" in h or "rate" in h:
        return "unit_price"
    if "quantity" in h or h == "qty":
        return "quantity_invoiced"
    if "line" in h and "amount" in h:
        return "line_amount"
    if "tax" in h and "amount" in h:
        return "tax_amount"
    if "freight" in h:
        return "freight_amount"
    if "discount" in h:
        return "discount_amount"
    if "currency" in h:
        return "currency"
    if "payment" in h and "terms" in h or h == "terms":
        return "payment_terms"
    if "document" in h and ("id" in h or "number" in h):
        return "document_id"
    if "total" in h or h == "amount":
        return "invoice_total"
    return None


def _clean_value(value):
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="ignore")
    value = str(value).strip()
    return value or None


def _parse_date(value):
    if not value:
        return None
    value = str(value).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%m-%d-%Y", "%d-%m-%Y", "%Y/%m/%d", "%m/%d/%y", "%d/%m/%y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def _extract_text_from_bytes(file_bytes):
    if file_bytes.startswith(b"%PDF"):
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            if text.strip():
                return text
        except Exception:
            pass

    try:
        workbook = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True, read_only=True)
        lines = []
        for sheet in workbook.worksheets:
            for row in sheet.iter_rows(values_only=True):
                line = ",".join("" if cell is None else str(cell) for cell in row)
                if line.strip(","):
                    lines.append(line)
        if lines:
            return "\n".join(lines)
    except Exception:
        pass

    return file_bytes.decode("utf-8", errors="ignore")


def _looks_like_csv(text):
    lines = text.strip().splitlines()
    if len(lines) < 2:
        return False
    first_line = lines[0]
    return any(delim in first_line for delim in (",", "\t", ";", "|"))


def _parse_csv(text):
    lines = text.strip().splitlines()
    if len(lines) < 2:
        return {}, None

    sample = "\n".join(lines[:5])
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        delimiter = dialect.delimiter
    except Exception:
        if "," in lines[0]:
            delimiter = ","
        elif "\t" in lines[0]:
            delimiter = "\t"
        elif ";" in lines[0]:
            delimiter = ";"
        elif "|" in lines[0]:
            delimiter = "|"
        else:
            return {}, None

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    if len(rows) < 2:
        return {}, None

    headers = [_normalize_header(h) for h in rows[0]]
    data_rows = rows[1:]

    details = {}
    due_date = None
    first_row = data_rows[0]
    for header, value in zip(headers, first_row):
        key = _map_header(header)
        value = _clean_value(value)
        if key is None or not value:
            continue
        if key == "due_date":
            due_date = _parse_date(value)
        else:
            details[key] = value

    line_items = []
    for row in data_rows:
        item = {}
        for idx, header in enumerate(headers):
            key = _map_header(header)
            if key in ITEM_KEYS:
                value = _clean_value(row[idx] if idx < len(row) else "")
                if value:
                    item[key] = value
        if item:
            line_items.append(item)

    if line_items:
        details["line_items"] = line_items

    return details, due_date


def _search(pattern, text):
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def _parse_text_regex(text):
    details = {}

    invoice_number = _search(r"invoice\s*number\s*[:#]?\s*([A-Za-z0-9][A-Za-z0-9\-/_]*)", text)
    if invoice_number:
        details["invoice_number"] = invoice_number

    vendor_name = _search(r"(?:vendor|supplier)\s*(?:name)?\s*[:#]?\s*([^\n\r]+)", text)
    if vendor_name:
        details["vendor_name"] = vendor_name

    invoice_date_raw = _search(r"invoice\s*date\s*[:#]?\s*([0-9]{1,4}[-/][0-9]{1,2}[-/][0-9]{1,4})", text)
    if invoice_date_raw:
        details["invoice_date"] = _parse_date(invoice_date_raw) or invoice_date_raw

    due_date_raw = _search(r"(?:payment\s*due\s*date|due\s*date)\s*[:#]?\s*([0-9]{1,4}[-/][0-9]{1,2}[-/][0-9]{1,4})", text)
    due_date = _parse_date(due_date_raw) if due_date_raw else None

    details["vendor_tax_id"] = _search(r"(?:tax\s*id|vat|ein|tin)\s*[:#]?\s*([A-Za-z0-9\-]+)", text)
    details["remit_to_address"] = _search(r"remit\s*to\s*[:#]?\s*([^\n\r]+)", text)
    details["bill_to_address"] = _search(r"bill\s*to\s*[:#]?\s*([^\n\r]+)", text)
    details["ship_to_address"] = _search(r"ship\s*to\s*[:#]?\s*([^\n\r]+)", text)
    details["purchase_order_number"] = _search(r"(?:purchase\s*order|po)\s*(?:number|no\.?|#)?\s*[:#]?\s*([A-Za-z0-9\-/_]+)", text)
    details["po_line_item_reference"] = _search(r"po\s*line\s*(?:item|reference)?\s*[:#]?\s*([A-Za-z0-9\-/_]+)", text)
    details["item_code"] = _search(r"(?:item\s*code|sku|product\s*code)\s*[:#]?\s*([A-Za-z0-9\-]+)", text)
    details["item_description"] = _search(r"(?:item\s*description|description|product)\s*[:#]?\s*([^\n\r]+)", text)
    details["quantity_invoiced"] = _search(r"(?:quantity|qty)\s*[:#]?\s*([\d,]+\.?\d*)", text)
    details["unit_price"] = _search(r"(?:unit\s*price|price\s*each|rate)\s*[:#]?\s*(?:[$€£]\s*)?([\d,]+\.?\d*)", text)
    details["line_amount"] = _search(r"(?:line\s*amount|amount)\s*[:#]?\s*(?:[$€£]\s*)?([\d,]+\.?\d*)", text)
    details["tax_amount"] = _search(r"(?:tax\s*amount|sales\s*tax|vat\s*amount)\s*[:#]?\s*(?:[$€£]\s*)?([\d,]+\.?\d*)", text)
    details["freight_amount"] = _search(r"freight\s*[:#]?\s*(?:[$€£]\s*)?([\d,]+\.?\d*)", text)
    details["discount_amount"] = _search(r"discount\s*[:#]?\s*(?:[$€£]\s*)?([\d,]+\.?\d*)", text)
    details["invoice_total"] = _search(r"(?:total\s*amount|invoice\s*total|amount\s*due|total)\s*[:#]?\s*(?:[$€£]\s*)?([\d,]+\.?\d*)", text)
    details["currency"] = _search(r"(?:currency|invoice\s+currency)\s*[:#]?\s*([A-Z]{3})", text)
    details["payment_terms"] = _search(r"(?:payment\s*terms|terms)\s*[:#]?\s*([^\n\r]+)", text)
    details["document_id"] = _search(r"(?:document\s*id|doc\s*id)\s*[:#]?\s*([A-Za-z0-9\-]+)", text)

    details = {k: v for k, v in details.items() if v not in (None, "", [])}
    return details, due_date


def _parse_document_text(text):
    if _looks_like_csv(text):
        details, due_date = _parse_csv(text)
        if details:
            return details, due_date

    return _parse_text_regex(text)


def _build_record(details, due_date):
    title = details.get("vendor_name") or details.get("invoice_number") or "Unnamed Vendor"
    status = "On Hold" if not details.get("vendor_name") else "Needs Review"

    return {
        "title": title,
        "status": status,
        "details": details,
        "due_date": due_date,
    }


def process_file(file_bytes: bytes) -> list[dict]:
    text = _extract_text_from_bytes(file_bytes)
    details, due_date = _parse_document_text(text)

    if not details:
        details = {"raw_text": text[:2000]}

    record = _build_record(details, due_date)
    return [record]
