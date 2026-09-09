import json
import os
import time
from datetime import datetime, timezone

import requests

import processor

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
PRODUCT_ID = os.environ["PRODUCT_ID"]

REST_URL = f"{SUPABASE_URL}/rest/v1"
SB_HEADERS = {
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "apikey": SUPABASE_SERVICE_KEY,
}


def download_file(bucket, file_path):
    if file_path.startswith(bucket + "/"):
        file_path = file_path[len(bucket) + 1:]
    url = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{file_path}"
    resp = requests.get(url, headers={
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "apikey": SUPABASE_SERVICE_KEY,
    })
    resp.raise_for_status()
    return resp.content


def upload_file(bucket, file_path, content, content_type="application/json"):
    if file_path.startswith(bucket + "/"):
        file_path = file_path[len(bucket) + 1:]
    url = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{file_path}"
    resp = requests.post(url, headers={
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "apikey": SUPABASE_SERVICE_KEY,
        "Content-Type": content_type,
    }, data=content)
    resp.raise_for_status()
    return resp.json()


def insert_notification(customer_id, title, body, notif_type):
    try:
        payload = {
            "product_id": PRODUCT_ID,
            "customer_id": customer_id,
            "title": title,
            "body": body,
            "type": notif_type,
            "read": False,
        }
        requests.post(f"{REST_URL}/notifications", headers={
            **SB_HEADERS,
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }, json=payload)
    except Exception:
        pass


def poll():
    while True:
        try:
            jobs_url = f"{REST_URL}/jobs?job_type=eq.process_upload&status=eq.pending&product_id=eq.{PRODUCT_ID}&select=*"
            resp = requests.get(jobs_url, headers=SB_HEADERS)
            resp.raise_for_status()
            jobs = resp.json()

            for job in jobs:
                job_id = job["id"]
                customer_id = job["customer_id"]
                input_file = job["input_file_path"]
                try:
                    file_bytes = download_file("uploads", input_file)
                    records = processor.process_file(file_bytes)

                    for r in records:
                        insert_payload = {
                            "product_id": PRODUCT_ID,
                            "customer_id": customer_id,
                            "title": r["title"],
                            "status": r["status"],
                            "details": r.get("details") or {},
                            "source_file_path": input_file,
                            "due_date": r.get("due_date"),
                        }
                        insert_resp = requests.post(f"{REST_URL}/records", headers={
                            **SB_HEADERS,
                            "Content-Type": "application/json",
                            "Prefer": "return=minimal",
                        }, json=insert_payload)
                        insert_resp.raise_for_status()

                    result_path = f"results/{job_id}.json"
                    result_bytes = json.dumps(records).encode("utf-8")
                    upload_file("results", result_path, result_bytes, "application/json")

                    summary = f"Processed {len(records)} record(s)."
                    update_payload = {
                        "status": "completed",
                        "output_file_path": result_path,
                        "result_summary": summary,
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    }
                    requests.patch(f"{REST_URL}/jobs?id=eq.{job_id}", headers={
                        **SB_HEADERS,
                        "Content-Type": "application/json",
                        "Prefer": "return=minimal",
                    }, json=update_payload).raise_for_status()

                    insert_notification(
                        customer_id,
                        "Processing complete",
                        "Your upload has been processed successfully.",
                        "success",
                    )
                except Exception as exc:
                    update_payload = {
                        "status": "failed",
                        "result_summary": str(exc),
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    }
                    try:
                        requests.patch(f"{REST_URL}/jobs?id=eq.{job_id}", headers={
                            **SB_HEADERS,
                            "Content-Type": "application/json",
                            "Prefer": "return=minimal",
                        }, json=update_payload).raise_for_status()
                    except Exception:
                        pass
                    insert_notification(
                        customer_id,
                        "Processing failed",
                        "There was an error processing your upload.",
                        "error",
                    )
        except Exception as exc:
            print("Poll error:", exc)
        time.sleep(60)


if __name__ == "__main__":
    print("Poller started")
    poll()
