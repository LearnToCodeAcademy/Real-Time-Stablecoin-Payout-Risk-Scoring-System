from fastapi.testclient import TestClient

import api


def test_health_and_model_endpoints_are_live():
    with TestClient(api.app) as client:
        health = client.get("/health")
        models = client.get("/model_info")

    assert health.status_code == 200
    assert health.json()["version"] == "3.0.0"
    assert health.json()["live_stream"]["state"] == "offline"
    assert models.status_code == 200


def test_local_training_is_locked_by_default():
    with TestClient(api.app) as client:
        response = client.post("/training/train", json={"token": "usdt", "model": "rf"})

    assert response.status_code == 403


def test_websocket_sends_real_source_status_not_demo_event():
    with TestClient(api.app) as client:
        with client.websocket_connect("/ws/live-alerts") as websocket:
            message = websocket.receive_json()

    assert message["type"] == "status"
    assert message["live"]["state"] == "offline"
    assert "demo" not in message
