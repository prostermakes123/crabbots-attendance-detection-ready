from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import app

ROOT = Path(__file__).resolve().parents[1]


def test_detection_status_and_photo_endpoint_work_without_sface():
    image_path = ROOT / "tests" / "fixtures" / "faces" / "Sophie_Adenot.jpg"
    with TestClient(app) as client:
        status = client.get("/api/detection/status")
        assert status.status_code == 200
        status_data = status.json()
        assert status_data["ready"] is True
        assert status_data["backend"] in {"yunet", "haar"}

        with image_path.open("rb") as image_file:
            response = client.post(
                "/api/detection/photo",
                files={"file": (image_path.name, image_file, "image/jpeg")},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["backend"] in {"yunet", "haar"}
    assert data["face_count"] >= 1
    assert data["latency_ms"] >= 0
    assert data["annotated_image"].startswith("data:image/jpeg;base64,")
    assert data["detections"]
    assert len(data["detections"][0]["bbox"]) == 4


def test_detection_endpoint_rejects_non_image_upload():
    with TestClient(app) as client:
        response = client.post(
            "/api/detection/photo",
            files={"file": ("not-an-image.jpg", b"not really a jpeg", "image/jpeg")},
        )
    assert response.status_code == 422
