from pathlib import Path

from tap.mobile.api import _payment_link_html, _portal_html, _receipt_html, create_app
from tap.mobile.offline_queue import OfflineQueue
from tap.mobile.payment_links import _decode_proof, inspect_proof
from tap.mobile.security import hash_access_token, tokens_match
from tap.mobile import runtime


def test_mobile_health_and_authentication():
    client = create_app().test_client()

    assert client.get("/api/mobile/health").get_json()["status"] == "ok"
    assert client.post("/api/mobile/sync", json={"events": []}).status_code == 401


def test_portal_html_escapes_token():
    page = _portal_html("a'><b>bad")

    assert "<b>bad" not in page
    assert "{{" not in page
    assert "function load()" in page


def test_receipt_html_contains_qr_image():
    receipt = _receipt_html(
        {"prenom": "A", "nom": "B"},
        {
            "mois": "08/2026",
            "montant_total": "100",
            "montant_paye": "100",
            "reste_a_payer": "0",
            "devise": "USD",
            "statut": "En règle",
        },
        "http://192.168.1.20:8765/portal/test/payments/1/receipt",
    )
    assert "data:image/png;base64," in receipt


def test_payment_link_html_contains_upload_form_and_escapes_values():
    page = _payment_link_html(
        "token'><bad",
        {
            "prenom": "A",
            "nom": "<B>",
            "mois": "08/2026",
            "montant_demande": "120.00",
            "devise": "USD",
        },
    )

    assert "Envoyer la preuve" in page
    assert "accept='image/png,image/jpeg,application/pdf'" in page
    assert "<B>" not in page
    assert "token'><bad" not in page


def test_payment_proof_decoder_accepts_png_and_rejects_other_formats():
    import base64

    encoded = base64.b64encode(b"\x89PNG\r\n\x1a\npng-content").decode("ascii")
    data, mime = _decode_proof(f"data:image/png;base64,{encoded}")

    assert data == b"\x89PNG\r\n\x1a\npng-content"
    assert mime == "image/png"

    try:
        _decode_proof("data:text/plain;base64,SGk=")
    except ValueError as exc:
        assert "PNG" in str(exc)
    else:
        raise AssertionError("Un format non autorisé a été accepté")


def test_payment_proof_checks_binary_signature_and_hash():
    data = b"\x89PNG\r\n\x1a\nvalid-png"
    audit = inspect_proof(data, "image/png")
    assert audit["size_bytes"] == len(data)
    assert len(audit["sha256"]) == 64

    try:
        inspect_proof(b"not-an-image", "image/png")
    except ValueError as exc:
        assert "Signature" in str(exc)
    else:
        raise AssertionError("Une signature binaire invalide a ete acceptee")


def test_token_hash_is_verifiable(monkeypatch):
    monkeypatch.setenv("TAP_PORTAL_TOKEN_PEPPER", "test-only-pepper-with-32-bytes!!")
    token = "temporary-token"

    assert tokens_match(token, hash_access_token(token))
    assert not tokens_match("other-token", hash_access_token(token))


def test_token_hash_requires_configured_pepper(monkeypatch):
    monkeypatch.delenv("TAP_PORTAL_TOKEN_PEPPER", raising=False)

    try:
        hash_access_token("token")
    except RuntimeError as exc:
        assert "TAP_PORTAL_TOKEN_PEPPER" in str(exc)
    else:
        raise AssertionError("Un pepper par defaut a ete accepte")


def test_mobile_payment_amount_requires_cents_and_api_key(monkeypatch):
    monkeypatch.setenv("TAP_MOBILE_API_KEY", "test-api-key")
    client = create_app().test_client()

    response = client.post(
        "/api/mobile/payments/1/record",
        headers={"X-TAP-Mobile-Key": "test-api-key"},
        json={"amount": "1.001"},
    )
    assert response.status_code == 400


def test_mobile_runtime_binds_lan_when_public_host_is_lan(monkeypatch):
    monkeypatch.setattr(runtime, "load_app_config", lambda: {
        "mobile_portal": {"host": "127.0.0.1", "public_host": "192.168.1.50", "port": 8765}
    })
    monkeypatch.setattr(runtime, "detect_lan_ip", lambda: "192.168.1.50")
    monkeypatch.setattr(runtime, "_load_or_create_secrets", lambda: {"api_key": "a", "token_pepper": "p"})
    monkeypatch.delenv("TAP_MOBILE_HOST", raising=False)
    monkeypatch.delenv("TAP_MOBILE_HOST_PUBLIC", raising=False)

    config = runtime.configure_mobile_environment()

    assert config["host"] == "0.0.0.0"
    assert config["public_host"] == "192.168.1.50"


def test_portal_routes_return_expected_auth_errors(monkeypatch):
    monkeypatch.setattr("tap.mobile.api.get_portal_data", lambda token: None)
    client = create_app().test_client()

    assert client.get("/api/portal/expired/data").status_code == 404
    assert client.get("/portal/expired").status_code == 200


def test_portal_payment_exports_are_scoped_and_downloadable(monkeypatch):
    payment = {
        "id": 7, "mois": "2026-08-01", "montant_total": "100.00",
        "montant_paye": "25.00", "reste_a_payer": "75.00", "devise": "USD",
        "statut": "Litigieux", "statut_paiement": "Partiel", "statut_affiche": "Partiel",
        "reference": "PAI-7", "prestation": "Loyer 08/2026",
        "methode_paiement": "Non renseignée", "est_signe": False,
    }
    monkeypatch.setattr("tap.mobile.api.get_portal_payments", lambda token, **kwargs: {
        "tenant": {"id": 3, "nom": "A", "prenom": "B"}, "payments": [payment]
    })
    client = create_app().test_client()

    csv_response = client.get("/api/portal/private/payments.csv")
    pdf_response = client.get("/api/portal/private/payments/7/invoice.pdf")
    detail_response = client.get("/api/portal/private/payments/7")

    assert csv_response.status_code == 200
    assert "PAI-7" in csv_response.get_data(as_text=True)
    assert pdf_response.status_code == 200
    assert pdf_response.mimetype == "application/pdf"
    assert pdf_response.data.startswith(b"%PDF")
    assert detail_response.status_code == 200
    assert detail_response.get_json()["payment"]["id"] == 7


def test_offline_queue_is_durable(tmp_path: Path):
    queue = OfflineQueue(tmp_path / "offline.sqlite")
    event_id = queue.enqueue(
        "record_payment",
        {"payment_id": 12, "amount": 25, "base_paid": 100},
        "device-test",
    )

    assert queue.pending()[0]["event_id"] == event_id
    queue.mark_result(event_id, "conflict", {"message": "changed"})
    assert queue.pending() == []
