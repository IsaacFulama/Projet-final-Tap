import base64
from io import BytesIO

from PIL import Image, ImageDraw

from tap.core import local_signature


def _png_data_url():
    img = Image.new("RGB", (320, 180), "white")
    draw = ImageDraw.Draw(img)
    draw.line((40, 120, 140, 80, 240, 120), fill="black", width=4)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _payment_meta():
    return {
        "paiement_id": 12,
        "locataire_id": 7,
        "nom": "Mabika",
        "prenom": "Jean",
        "mois": "Août 2026",
        "montant": 100,
        "montant_total": 100,
        "montant_paye": 100,
        "reste_a_payer": 0,
        "devise": "USD",
        "statut": "En règle",
        "statut_paiement": "Complet",
        "statut_souscription": "Simple",
    }


def test_signature_payload_hash_is_stable():
    payload = local_signature.build_signature_payload(_payment_meta())

    assert payload["signataire_nom"] == "Mabika Jean"
    assert local_signature.compute_document_hash(payload) == local_signature.compute_document_hash(payload.copy())


def test_signature_host_can_be_overridden(monkeypatch):
    monkeypatch.setenv("TAP_SIGNATURE_HOST", "192.168.1.50")
    server = local_signature.LocalSignatureServer()
    session = server.create_session(_payment_meta())

    assert session.url.startswith("http://192.168.1.50:")


def test_decode_signature_image_accepts_png_data_url():
    raw = local_signature.decode_signature_image(_png_data_url())

    assert raw.startswith(b"\x89PNG\r\n\x1a\n")


def test_submit_signature_marks_session_signed(monkeypatch):
    saved = []
    server = local_signature.LocalSignatureServer()
    session = server.create_session(_payment_meta())

    def fake_save_signature(session_arg, signature_png, signer_ip, user_agent):
        saved.append((session_arg.token, signature_png, signer_ip, user_agent))

    monkeypatch.setattr(local_signature, "save_signature", fake_save_signature)
    monkeypatch.setattr(
        local_signature,
        "enregistrer_signature_et_mettre_a_jour_paiement",
        lambda session_payload, document_hash, signature_png, signer_ip, user_agent: (
            saved.append((session_payload["paiement_id"], signature_png, signer_ip, user_agent)) or (True, "ok")
        ),
    )

    response = server._app.test_client().post(
        f"/api/sign/{session.token}",
        json={"consent": True, "signature": _png_data_url()},
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "signed"
    assert response.get_json()["receipt_url"] == f"/receipt/{session.token}"
    assert server.status(session.token)["status"] == "signed"
    assert saved and saved[0][0] == session.payload["paiement_id"]


def test_signed_receipt_page_contains_print_action(monkeypatch):
    server = local_signature.LocalSignatureServer()
    session = server.create_session(_payment_meta())

    monkeypatch.setattr(local_signature, "save_signature", lambda *args: None)
    monkeypatch.setattr(
        local_signature,
        "enregistrer_signature_et_mettre_a_jour_paiement",
        lambda *args, **kwargs: (True, "ok"),
    )
    server._app.test_client().post(
        f"/api/sign/{session.token}",
        json={"consent": True, "signature": _png_data_url()},
    )

    response = server._app.test_client().get(f"/receipt/{session.token}")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Recu signe" in page
    assert "window.print()" in page
