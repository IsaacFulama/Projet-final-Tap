from __future__ import annotations

import base64
import hashlib
import html
import json
import os
import secrets
import socket
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from flask import Flask, jsonify, request
from werkzeug.serving import make_server

from tap.infrastructure.database.connection import obtenir_connexion
from tap.infrastructure.database.repository import (
    enregistrer_signature_et_mettre_a_jour_paiement,
)


SIGNATURE_EXPIRATION_MINUTES = 10
MAX_SIGNATURE_BYTES = 600_000


@dataclass
class SignatureSession:
    token: str
    url: str
    payload: dict[str, Any]
    document_hash: str
    expires_at: datetime
    status: str = "pending"
    error: str = ""
    signed_at: datetime | None = None
    signature_data_url: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at


class LocalSignatureServer:
    def __init__(self) -> None:
        self._app = Flask(__name__)
        self._server = None
        self._thread: threading.Thread | None = None
        self._sessions: dict[str, SignatureSession] = {}
        self._lock = threading.Lock()
        self._configure_routes()

    @property
    def port(self) -> int | None:
        if self._server is None:
            return None
        return int(self._server.server_port)

    def ensure_started(self) -> None:
        if self._server is not None:
            return

        self._server = make_server("0.0.0.0", 0, self._app)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="tap-local-signature-server",
            daemon=True,
        )
        self._thread.start()

    def create_session(self, payment_meta: dict[str, Any]) -> SignatureSession:
        self.ensure_started()
        token = secrets.token_urlsafe(32)
        payload = build_signature_payload(payment_meta)
        document_hash = compute_document_hash(payload)
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=SIGNATURE_EXPIRATION_MINUTES
        )
        host = os.getenv("TAP_SIGNATURE_HOST", "").strip() or get_lan_ip()
        host = host.removeprefix("http://").removeprefix("https://").rstrip("/")
        url = f"http://{host}:{self.port}/sign/{token}"

        session = SignatureSession(
            token=token,
            url=url,
            payload=payload,
            document_hash=document_hash,
            expires_at=expires_at,
        )
        with self._lock:
            self._cleanup_expired_locked()
            self._sessions[token] = session
        return session

    def get_session(self, token: str) -> SignatureSession | None:
        with self._lock:
            session = self._sessions.get(token)
            if session and session.expired and session.status == "pending":
                session.status = "expired"
            return session

    def status(self, token: str) -> dict[str, str]:
        session = self.get_session(token)
        if session is None:
            return {"status": "missing", "message": "Lien de signature introuvable."}
        if session.status == "signed":
            return {"status": "signed", "message": "Signature reçue."}
        if session.status == "expired":
            return {"status": "expired", "message": "Lien expiré."}
        if session.status == "error":
            return {"status": "error", "message": session.error}
        remaining = max(0, int((session.expires_at - datetime.now(timezone.utc)).total_seconds()))
        return {"status": "pending", "message": f"En attente ({remaining}s)."}

    def _configure_routes(self) -> None:
        @self._app.get("/sign/<token>")
        def sign_page(token: str):
            session = self.get_session(token)
            if session is None:
                return render_message_page("Lien invalide", "Cette demande de signature n'existe pas."), 404
            if session.status == "signed":
                return render_message_page("Deja signe", "La signature a deja ete recue.")
            if session.status == "expired":
                return render_message_page("Lien expire", "Demandez un nouveau QR code au gestionnaire."), 410
            return render_signature_page(token, session)

        @self._app.get("/api/sign/<token>/status")
        def sign_status(token: str):
            return jsonify(self.status(token))

        @self._app.get("/receipt/<token>")
        def signed_receipt(token: str):
            session = self.get_session(token)
            if session is None:
                return render_message_page("Lien invalide", "Ce recu signe n'existe pas."), 404
            if session.status != "signed":
                return render_message_page("Recu indisponible", "Le recu sera disponible apres signature."), 409
            return render_signed_receipt_page(session)

        @self._app.post("/api/sign/<token>")
        def submit_signature(token: str):
            session = self.get_session(token)
            if session is None:
                return jsonify({"status": "missing", "message": "Lien invalide."}), 404
            if session.expired:
                session.status = "expired"
                return jsonify({"status": "expired", "message": "Lien expire."}), 410
            if session.status == "signed":
                return jsonify({"status": "signed", "message": "Signature deja recue."})

            data = request.get_json(silent=True) or {}
            if not data.get("consent"):
                return jsonify({"status": "error", "message": "Consentement requis."}), 400

            try:
                signature_data_url = data.get("signature", "")
                signature_bytes = decode_signature_image(signature_data_url)
                success, db_message = enregistrer_signature_et_mettre_a_jour_paiement(
                    session.payload,
                    session.document_hash,
                    signature_bytes,
                    request.remote_addr or "",
                    request.headers.get("User-Agent", ""),
                )
                if not success:
                    raise RuntimeError(db_message)
            except Exception as exc:
                session.status = "error"
                session.error = str(exc)
                return jsonify({"status": "error", "message": str(exc)}), 400

            session.status = "signed"
            session.signed_at = datetime.now(timezone.utc)
            session.signature_data_url = signature_data_url

            return jsonify({
                "status": "signed",
                "message": "Signature enregistree.",
                "receipt_url": f"/receipt/{token}",
            })

    def _cleanup_expired_locked(self) -> None:
        expired_tokens = [
            token
            for token, session in self._sessions.items()
            if session.expired and session.status != "pending"
        ]
        for token in expired_tokens:
            self._sessions.pop(token, None)


def build_signature_payload(payment_meta: dict[str, Any]) -> dict[str, str]:
    full_name = f"{payment_meta.get('nom', '')} {payment_meta.get('prenom', '')}".strip()
    return {
        "paiement_id": int(payment_meta.get("paiement_id", 0)),
        "locataire_id": str(payment_meta.get("locataire_id", "")),
        "nom": str(payment_meta.get("nom", "")),
        "prenom": str(payment_meta.get("prenom", "")),
        "signataire_nom": full_name,
        "mois": str(payment_meta.get("mois", "")),
        "montant": str(payment_meta.get("montant", "")),
        "montant_total": str(payment_meta.get("montant_total", payment_meta.get("montant", "0"))),
        "montant_paye": str(payment_meta.get("montant_paye", "")),
        "montant_paye_signature": str(payment_meta.get("montant_paye_signature", "0")),
        "reste_a_payer": str(payment_meta.get("reste_a_payer", "")),
        "devise": str(payment_meta.get("devise", "")),
        "statut": str(payment_meta.get("statut", "")),
        "statut_paiement": str(payment_meta.get("statut_paiement", "")),
        "statut_souscription": str(payment_meta.get("statut_souscription", "")),
    }


def compute_document_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def decode_signature_image(value: str) -> bytes:
    prefix = "data:image/png;base64,"
    if not value.startswith(prefix):
        raise ValueError("Signature invalide.")
    raw = base64.b64decode(value[len(prefix):], validate=True)
    if len(raw) < 100:
        raise ValueError("La signature est vide.")
    if len(raw) > MAX_SIGNATURE_BYTES:
        raise ValueError("La signature est trop volumineuse.")
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Le format de signature n'est pas PNG.")
    return raw


def save_signature(
    session: SignatureSession,
    signature_png: bytes,
    signer_ip: str,
    user_agent: str,
) -> None:
    payload = session.payload
    conn = obtenir_connexion()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO signatures_paiements (
                paiement_id, locataire_id, document_hash, consentement,
                signature_png, signataire_nom, signer_ip, user_agent
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                int(payload["paiement_id"]),
                int(payload["locataire_id"]),
                session.document_hash,
                1,
                signature_png,
                payload["signataire_nom"][:201],
                signer_ip[:45],
                user_agent[:255],
            ),
        )
        conn.commit()
        cursor.close()
    finally:
        if conn is not None and conn.is_connected():
            conn.close()


def get_lan_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"
    finally:
        sock.close()


def render_signature_page(token: str, session: SignatureSession) -> str:
    p = session.payload
    title = "Confirmation de paiement" if p.get("statut") == "En règle" else "Accord de paiement"
    rows = [
        ("Locataire", p.get("signataire_nom", "")),
        ("Mois", p.get("mois", "")),
        ("Montant total", f"{p.get('montant_total', '')} {p.get('devise', '')}".strip()),
        ("Montant paye", f"{p.get('montant_paye', '')} {p.get('devise', '')}".strip()),
        ("Reste a payer", f"{p.get('reste_a_payer', '')} {p.get('devise', '')}".strip()),
        ("Statut", p.get("statut", "")),
    ]
    rows_html = "".join(
        f"<div class='row'><span>{html.escape(label)}</span><strong>{html.escape(value)}</strong></div>"
        for label, value in rows
    )
    safe_title = html.escape(title)
    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_title}</title>
  <style>
    body {{ margin:0; font-family: Arial, sans-serif; background:#f6f1e8; color:#2b2118; }}
    main {{ max-width: 560px; margin: 0 auto; padding: 18px; }}
    .card {{ background:#fffaf1; border:1px solid #d7c3a4; border-radius:8px; padding:18px; box-shadow:0 8px 28px rgba(47,34,18,.12); }}
    h1 {{ font-size:22px; margin:0 0 8px; }}
    p {{ line-height:1.45; }}
    .row {{ display:flex; justify-content:space-between; gap:14px; padding:10px 0; border-bottom:1px solid #eadcc8; }}
    .row span {{ color:#6f604f; }}
    .row strong {{ text-align:right; }}
    canvas {{ width:100%; height:220px; border:2px dashed #b99057; border-radius:8px; background:#fff; touch-action:none; display:block; }}
    button {{ width:100%; border:0; border-radius:6px; padding:14px; margin-top:12px; font-weight:700; font-size:16px; }}
    #send {{ background:#b99057; color:#130d07; }}
    #clear {{ background:#eee1cf; color:#2b2118; }}
    label {{ display:flex; gap:10px; align-items:flex-start; margin:14px 0; }}
    #message {{ margin-top:12px; font-weight:700; }}
  </style>
</head>
<body>
<main>
  <div class="card">
    <h1>{safe_title}</h1>
    <p>Verifiez les informations, signez dans le cadre, puis validez.</p>
    {rows_html}
    <h2>Signature</h2>
    <canvas id="pad"></canvas>
    <button id="clear" type="button">Effacer</button>
    <label><input id="consent" type="checkbox"> Je confirme avoir lu ce recu ou cet accord et j'appose ma signature.</label>
    <button id="send" type="button">Signer et envoyer</button>
    <div id="message"></div>
  </div>
</main>
<script>
const canvas = document.getElementById('pad');
const ctx = canvas.getContext('2d');
let drawing = false, dirty = false;
function resize() {{
  const ratio = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = Math.round(rect.width * ratio);
  canvas.height = Math.round(rect.height * ratio);
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.lineWidth = 3;
  ctx.lineCap = 'round';
  ctx.strokeStyle = '#1d1710';
}}
function point(e) {{
  const r = canvas.getBoundingClientRect();
  return {{x: e.clientX - r.left, y: e.clientY - r.top}};
}}
canvas.addEventListener('pointerdown', e => {{ drawing = true; dirty = true; canvas.setPointerCapture(e.pointerId); const p = point(e); ctx.beginPath(); ctx.moveTo(p.x, p.y); }});
canvas.addEventListener('pointermove', e => {{ if (!drawing) return; const p = point(e); ctx.lineTo(p.x, p.y); ctx.stroke(); }});
canvas.addEventListener('pointerup', () => drawing = false);
canvas.addEventListener('pointercancel', () => drawing = false);
document.getElementById('clear').onclick = () => {{ ctx.clearRect(0, 0, canvas.width, canvas.height); dirty = false; }};
document.getElementById('send').onclick = async () => {{
  const message = document.getElementById('message');
  if (!dirty) {{ message.textContent = 'Veuillez signer dans le cadre.'; return; }}
  if (!document.getElementById('consent').checked) {{ message.textContent = 'Veuillez confirmer votre consentement.'; return; }}
  message.textContent = 'Envoi en cours...';
  const res = await fetch('/api/sign/{token}', {{
    method:'POST',
    headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{consent:true, signature: canvas.toDataURL('image/png')}})
  }});
  const data = await res.json();
  message.textContent = data.message || 'Termine.';
  if (data.status === 'signed') {{
    document.getElementById('send').disabled = true;
    window.location.href = data.receipt_url || '/receipt/{token}';
  }}
}};
resize();
window.addEventListener('resize', resize);
</script>
</body>
</html>"""


def get_litigious_payments_for_locataire(locataire_id: int) -> list[dict[str, Any]]:
    """Récupère tous les paiements litigieux d'un locataire."""
    conn = obtenir_connexion()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT mois, montant_total, montant_paye, reste_a_payer, devise, statut
            FROM paiements
            WHERE locataire_id = %s AND statut = 'Litigieux'
            ORDER BY mois DESC
            """,
            (locataire_id,)
        )
        result = cursor.fetchall()
        cursor.close()
        return result
    except Exception as e:
        print(f"Erreur lors de la récupération des paiements litigieux: {e}")
        return []
    finally:
        if conn is not None and conn.is_connected():
            conn.close()


def render_signed_receipt_page(session: SignatureSession) -> str:
    p = session.payload
    signed_at = session.signed_at or datetime.now(timezone.utc)
    signed_label = signed_at.astimezone().strftime("%d/%m/%Y à %H:%M")
    
    # Récupérer les paiements litigieux du locataire
    litigious_payments = get_litigious_payments_for_locataire(int(p.get("locataire_id", 0)))
    
    # Déterminer le type de document
    is_paid = p.get("statut", "") == "En règle"
    document_type = "REÇU DE PAIEMENT" if is_paid else "ACCORD DE PAIEMENT"
    document_color = "#2e7d32" if is_paid else "#d32f2f"
    
    rows = [
        ("Locataire", p.get("signataire_nom", "")),
        ("Mois concerné", p.get("mois", "")),
        ("Montant total du mois", f"{p.get('montant_total', '')} {p.get('devise', '')}".strip()),
        ("Montant payé", f"{p.get('montant_paye', '')} {p.get('devise', '')}".strip()),
        ("Reste à payer", f"{p.get('reste_a_payer', '')} {p.get('devise', '')}".strip()),
        ("Statut du paiement", p.get("statut", "")),
    ]
    rows_html = "".join(
        f"<div class='row'><span>{html.escape(label)}</span><strong>{html.escape(value)}</strong></div>"
        for label, value in rows
    )
    
    # Générer le tableau des paiements litigieux
    litigious_table_html = ""
    total_litigious_global = Decimal("0")
    total_paid_global = Decimal("0")
    total_remaining_global = Decimal("0")
    
    if litigious_payments:
        litigious_rows = ""
        
        for payment in litigious_payments:
            mois = payment.get("mois", "")
            montant_total = Decimal(str(payment.get("montant_total", "0")))
            montant_paye = Decimal(str(payment.get("montant_paye", "0")))
            reste_a_payer = Decimal(str(payment.get("reste_a_payer", "0")))
            
            total_litigious_global += montant_total
            total_paid_global += montant_paye
            total_remaining_global += reste_a_payer
            
            devise = payment.get("devise", p.get("devise", ""))
            # Calculer le pourcentage payé
            pourcentage = (montant_paye / montant_total * 100) if montant_total > 0 else 0
            status_class = "status-partial" if 0 < pourcentage < 100 else "status-unpaid" if pourcentage == 0 else "status-paid"
            status_label = "Partiel" if 0 < pourcentage < 100 else "Non payé" if pourcentage == 0 else "Payé"
            
            litigious_rows += f"""
                <tr class='{status_class}'>
                    <td>{html.escape(str(mois))}</td>
                    <td>{html.escape(str(montant_total))} {html.escape(devise)}</td>
                    <td>{html.escape(str(montant_paye))} {html.escape(devise)}</td>
                    <td>{html.escape(str(reste_a_payer))} {html.escape(devise)}</td>
                    <td><span class='status-badge'>{html.escape(status_label)}</span></td>
                </tr>
            """
        
        litigious_table_html = f"""
            <div class='litigious-section'>
                <div class='section-header'>
                    <h3>📋 Historique des Mois Litigieux</h3>
                    <span class='badge-count'>{len(litigious_payments)} mois</span>
                </div>
                <div class='summary-box'>
                    <div class='summary-item'>
                        <span class='summary-label'>Total dû</span>
                        <span class='summary-value total-due'>{html.escape(str(total_litigious_global))} {html.escape(p.get('devise', ''))}</span>
                    </div>
                    <div class='summary-item'>
                        <span class='summary-label'>Total payé</span>
                        <span class='summary-value total-paid'>{html.escape(str(total_paid_global))} {html.escape(p.get('devise', ''))}</span>
                    </div>
                    <div class='summary-item'>
                        <span class='summary-label'>Reste à payer</span>
                        <span class='summary-value total-remaining'>{html.escape(str(total_remaining_global))} {html.escape(p.get('devise', ''))}</span>
                    </div>
                </div>
                <table class='litigious-table'>
                    <thead>
                        <tr>
                            <th>Mois</th>
                            <th>Montant Total</th>
                            <th>Montant Payé</th>
                            <th>Reste à Payer</th>
                            <th>État</th>
                        </tr>
                    </thead>
                    <tbody>
                        {litigious_rows}
                    </tbody>
                </table>
            </div>
        """
    
    # Footer avec informations légales
    footer_info = f"""
        <div class='footer-info'>
            <div class='footer-item'>
                <span class='footer-label'>Date de signature:</span>
                <span class='footer-value'>{signed_label}</span>
            </div>
            <div class='footer-item'>
                <span class='footer-label'>Référence:</span>
                <span class='footer-value'>{session.document_hash[:16].upper()}</span>
            </div>
        </div>
    """
    signature_src = html.escape(session.signature_data_url, quote=True)
    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Recu signe</title>
  <style>
    body {{ margin:0; font-family:'Segoe UI',Arial,sans-serif; background:#f6f1e8; color:#2b2118; }}
    main {{ max-width:800px; margin:0 auto; padding:20px; }}
    .receipt {{ background:white; border:2px solid #d7c3a4; border-radius:12px; padding:32px; box-shadow:0 8px 32px rgba(47,34,18,.15); }}
    .header {{ text-align:center; margin-bottom:24px; padding-bottom:16px; border-bottom:3px solid {document_color}; }}
    .header h1 {{ margin:0 0 8px; font-size:28px; font-weight:700; color:{document_color}; text-transform:uppercase; letter-spacing:1px; }}
    .header .sub {{ color:#6f604f; margin:0; font-size:16px; }}
    .payment-details {{ background:#fffaf1; border:1px solid #eadcc8; border-radius:8px; padding:20px; margin-bottom:24px; }}
    .payment-details .section-title {{ margin:0 0 16px; font-size:18px; font-weight:600; color:#2b2118; }}
    .row {{ display:flex; justify-content:space-between; gap:20px; padding:12px 0; border-bottom:1px solid #eadcc8; }}
    .row:last-child {{ border-bottom:none; }}
    .row span {{ color:#6f604f; font-weight:500; }}
    .row strong {{ text-align:right; font-weight:600; color:#2b2118; }}
    .litigious-section {{ margin-top:24px; border:2px solid #d7c3a4; border-radius:12px; padding:20px; background:#fffaf1; }}
    .section-header {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; }}
    .section-header h3 {{ margin:0; font-size:20px; font-weight:600; color:#2b2118; }}
    .badge-count {{ background:#d32f2f; color:white; padding:4px 12px; border-radius:20px; font-size:14px; font-weight:600; }}
    .summary-box {{ display:grid; grid-template-columns:repeat(3, 1fr); gap:12px; margin-bottom:20px; padding:16px; background:white; border-radius:8px; border:1px solid #eadcc8; }}
    .summary-item {{ text-align:center; }}
    .summary-label {{ display:block; font-size:13px; color:#6f604f; margin-bottom:4px; }}
    .summary-value {{ display:block; font-size:18px; font-weight:700; }}
    .total-due {{ color:#d32f2f; }}
    .total-paid {{ color:#2e7d32; }}
    .total-remaining {{ color:#f57c00; }}
    .litigious-table {{ width:100%; border-collapse:collapse; margin-top:12px; }}
    .litigious-table th {{ text-align:left; padding:12px 8px; border-bottom:2px solid #d7c3a4; color:#6f604f; font-size:13px; font-weight:600; text-transform:uppercase; }}
    .litigious-table td {{ padding:12px 8px; border-bottom:1px solid #eadcc8; font-size:14px; }}
    .status-paid {{ background:#e8f5e9; }}
    .status-partial {{ background:#fff3e0; }}
    .status-unpaid {{ background:#ffebee; }}
    .status-badge {{ display:inline-block; padding:4px 10px; border-radius:12px; font-size:12px; font-weight:600; }}
    .status-paid .status-badge {{ background:#2e7d32; color:white; }}
    .status-partial .status-badge {{ background:#f57c00; color:white; }}
    .status-unpaid .status-badge {{ background:#d32f2f; color:white; }}
    .signature {{ margin-top:28px; border:2px solid #d7c3a4; border-radius:12px; padding:20px; background:#fffaf1; }}
    .signature-title {{ margin:0 0 12px; font-size:18px; font-weight:600; color:#2b2118; }}
    .signature img {{ width:100%; max-height:200px; object-fit:contain; background:white; border:1px solid #eadcc8; border-radius:8px; padding:8px; }}
    .footer-info {{ margin-top:24px; padding-top:20px; border-top:2px solid #eadcc8; display:grid; grid-template-columns:repeat(2, 1fr); gap:16px; }}
    .footer-item {{ display:flex; flex-direction:column; }}
    .footer-label {{ font-size:13px; color:#6f604f; margin-bottom:4px; }}
    .footer-value {{ font-size:15px; font-weight:600; color:#2b2118; }}
    button {{ width:100%; border:0; border-radius:8px; padding:16px; margin-top:24px; font-weight:700; font-size:16px; background:#b99057; color:#130d07; cursor:pointer; transition:background 0.2s; }}
    button:hover {{ background:#a07d4a; }}
    @media print {{
      body {{ background:white; }}
      main {{ padding:0; }}
      .receipt {{ box-shadow:none; border:2px solid #000; }}
      button {{ display:none; }}
    }}
  </style>
</head>
<body>
<main>
  <section class="receipt">
    <div class="header">
      <h1>{html.escape(document_type)}</h1>
      <p class="sub">Document officiel de signature numérique - TAP Gestion des Loyers</p>
    </div>
    
    <div class="payment-details">
      <h2 class="section-title">📄 Détails du Paiement</h2>
      {rows_html}
    </div>
    
    {litigious_table_html}
    
    <div class="signature">
      <h3 class="signature-title">✍️ Signature du Locataire</h3>
      <img src="{signature_src}" alt="Signature du locataire">
    </div>
    
    {footer_info}
    
    <button onclick="window.print()">🖨️ Imprimer / Enregistrer en PDF</button>
  </section>
</main>
</body>
</html>"""


def render_message_page(title: str, message: str) -> str:
    safe_title = html.escape(title)
    safe_message = html.escape(message)
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{safe_title}</title></head>
<body style="font-family:Arial,sans-serif;padding:24px;background:#f6f1e8;color:#2b2118">
<h1>{safe_title}</h1><p>{safe_message}</p></body></html>"""


_server = LocalSignatureServer()


def start_signature_session(payment_meta: dict[str, Any]) -> SignatureSession:
    return _server.create_session(payment_meta)


def get_signature_status(token: str) -> dict[str, str]:
    return _server.status(token)
