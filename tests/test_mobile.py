from pathlib import Path

from tap.mobile.api import _payment_link_html, _portal_html, _receipt_html, create_app
from tap.mobile.offline_queue import OfflineQueue
from tap.mobile.payment_links import _decode_proof
from tap.mobile.security import hash_access_token, tokens_match


def test_mobile_health_and_authentication():
    client = create_app().test_client()

    assert client.get("/api/mobile/health").get_json()["status"] == "ok"
    assert client.post("/api/mobile/sync", json={"events": []}).status_code == 401


def test_portal_html_escapes_token():
    client = create_app().test_client()

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

    encoded = base64.b64encode(b"png-content").decode("ascii")
    data, mime = _decode_proof(f"data:image/png;base64,{encoded}")

    assert data == b"png-content"
    assert mime == "image/png"

    try:
        _decode_proof("data:text/plain;base64,SGk=")
    except ValueError as exc:
        assert "PNG" in str(exc)
    else:
        raise AssertionError("Un format non autorisé a été accepté")


def test_token_hash_is_verifiable():
    token = "temporary-token"

    assert tokens_match(token, hash_access_token(token))
    assert not tokens_match("other-token", hash_access_token(token))


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
