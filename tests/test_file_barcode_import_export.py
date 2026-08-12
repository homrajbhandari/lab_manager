import io
import os
import tempfile
from pathlib import Path

from openpyxl import Workbook


_TEST_ROOT = Path(tempfile.mkdtemp(prefix="lab-manager-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TEST_ROOT / 'test.db').as_posix()}"
os.environ["UPLOAD_ROOT"] = str(_TEST_ROOT / "uploads")
os.environ.setdefault("SECRET_KEY", "test-secret")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


client = TestClient(app)


def _create_project(title: str = "Attachment Project") -> int:
    response = client.post(
        "/projects/",
        json={
            "title": title,
            "description": "Project used by integration tests",
            "status": "active",
            "priority": "medium",
        },
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


def _create_sample(project_id: int) -> int:
    response = client.post(
        "/samples/",
        json={
            "name": "Sample A",
            "description": "sample attachment target",
            "sample_type": "blood",
            "status": "available",
            "storage_location": "freezer-1",
            "project_id": project_id,
        },
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


def test_project_attachment_upload_list_download_delete():
    project_id = _create_project()

    upload = client.post(
        f"/projects/{project_id}/attachments/",
        files={
            "file": (
                "protocol.pdf",
                b"%PDF-1.4 protocol",
                "application/pdf",
            )
        },
    )

    assert upload.status_code == 201
    uploaded = upload.json()["data"]
    assert uploaded["filename"] == "protocol.pdf"
    assert uploaded["size_bytes"] == len(b"%PDF-1.4 protocol")
    assert uploaded["download_url"].endswith("/download")

    listed = client.get(f"/projects/{project_id}/attachments/")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    downloaded = client.get(uploaded["download_url"])
    assert downloaded.status_code == 200
    assert downloaded.content == b"%PDF-1.4 protocol"

    deleted = client.delete(
        f"/projects/{project_id}/attachments/{uploaded['id']}"
    )
    assert deleted.status_code == 200

    listed_after_delete = client.get(f"/projects/{project_id}/attachments/")
    assert listed_after_delete.json()["total"] == 0


def test_sample_image_and_dataset_uploads():
    project_id = _create_project("Sample Attachment Project")
    sample_id = _create_sample(project_id)

    image_upload = client.post(
        f"/samples/{sample_id}/attachments/",
        data={"kind": "image"},
        files={"file": ("cells.png", b"PNGDATA", "image/png")},
    )
    assert image_upload.status_code == 201
    assert image_upload.json()["data"]["kind"] == "image"

    dataset_upload = client.post(
        f"/samples/{sample_id}/attachments/",
        data={"kind": "dataset"},
        files={"file": ("measurements.csv", b"x,y\n1,2\n", "text/csv")},
    )
    assert dataset_upload.status_code == 201
    assert dataset_upload.json()["data"]["kind"] == "dataset"

    listed = client.get(f"/samples/{sample_id}/attachments/")
    assert listed.status_code == 200
    assert listed.json()["total"] == 2


def test_inventory_barcode_scan_and_quantity_adjustment():
    created = client.post(
        "/inventory/",
        json={
            "name": "Nitrile Gloves",
            "description": "Medium size",
            "category": "PPE",
            "quantity": 10,
            "unit": "box",
            "location": "Store A",
            "supplier": "Lab Supply",
            "barcode": "INV-GLV-001",
        },
    )
    assert created.status_code == 201
    assert created.json()["data"]["barcode"] == "INV-GLV-001"

    duplicate = client.post(
        "/inventory/",
        json={
            "name": "Duplicate Gloves",
            "category": "PPE",
            "quantity": 1,
            "unit": "box",
            "location": "Store B",
            "barcode": "INV-GLV-001",
        },
    )
    assert duplicate.status_code == 409

    scanned = client.post(
        "/inventory/scan",
        json={"barcode": "INV-GLV-001"},
    )
    assert scanned.status_code == 200
    assert scanned.json()["data"]["name"] == "Nitrile Gloves"

    adjusted = client.post(
        "/inventory/scan/quantity",
        json={"barcode": "INV-GLV-001", "delta": -3},
    )
    assert adjusted.status_code == 200
    assert adjusted.json()["data"]["quantity"] == 7

    overdraw = client.post(
        "/inventory/scan/quantity",
        json={"barcode": "INV-GLV-001", "delta": -8},
    )
    assert overdraw.status_code == 422


def test_import_export_csv_and_xlsx():
    csv_payload = (
        "title,description,status,priority\n"
        "Imported Project A,from csv,active,high\n"
        "Imported Project B,from csv,on_hold,medium\n"
    )
    imported_projects = client.post(
        "/import/projects",
        files={"file": ("projects.csv", csv_payload, "text/csv")},
    )
    assert imported_projects.status_code == 201
    assert imported_projects.json()["data"]["imported"] == 2
    assert imported_projects.json()["data"]["failed"] == 0

    exported_csv = client.get("/export/projects?file_format=csv")
    assert exported_csv.status_code == 200
    assert "title,description,status,priority" in exported_csv.text
    assert "Imported Project A" in exported_csv.text

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(
        [
            "name",
            "description",
            "category",
            "quantity",
            "unit",
            "location",
            "supplier",
            "barcode",
        ]
    )
    worksheet.append(
        [
            "Imported Reagent",
            "from xlsx",
            "Chemical",
            5,
            "ml",
            "Shelf 2",
            "Chem Co",
            "INV-XLSX-001",
        ]
    )
    workbook_bytes = io.BytesIO()
    workbook.save(workbook_bytes)
    workbook_bytes.seek(0)

    imported_inventory = client.post(
        "/import/inventory",
        files={
            "file": (
                "inventory.xlsx",
                workbook_bytes.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert imported_inventory.status_code == 201
    assert imported_inventory.json()["data"]["imported"] == 1

    exported_xlsx = client.get("/export/inventory?file_format=xlsx")
    assert exported_xlsx.status_code == 200
    assert exported_xlsx.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
