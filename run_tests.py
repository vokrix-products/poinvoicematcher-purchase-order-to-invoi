from processor import process_file


def test_csv():
    data = b"supplier,product,price\nAcme,Widget,9.99"
    records = process_file(data)

    assert isinstance(records, list)
    assert len(records) == 1
    record = records[0]

    assert record["title"] == "Acme"
    assert record["status"] == "Needs Review"
    assert record["due_date"] is None
    assert record["details"]["vendor_name"] == "Acme"
    assert record["details"]["line_items"][0]["item_description"] == "Widget"
    assert record["details"]["line_items"][0]["unit_price"] == "9.99"


def test_text_regex():
    data = b"Invoice Number: INV-100\nVendor: Globex\nInvoice Date: 01/20/2025\nDue Date: 02/20/2025\nTotal: $200.00"
    records = process_file(data)

    assert records
    record = records[0]
    assert record["title"] == "Globex"
    assert record["due_date"] == "2025-02-20"
    assert record["details"]["invoice_number"] == "INV-100"
    assert record["details"]["invoice_total"] == "200.00"


test_csv()
test_text_regex()
print("All tests passed.")
