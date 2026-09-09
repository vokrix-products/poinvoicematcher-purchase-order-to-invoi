import json
from processor import process_file

test_bytes = b"supplier,product,price\nAcme,Widget,9.99"
results = process_file(test_bytes)

assert isinstance(results, list)
assert len(results) == 1
assert results[0]["title"] == "Acme"
assert results[0]["status"] == "Needs Review"

print(json.dumps(results, default=str, indent=2))
