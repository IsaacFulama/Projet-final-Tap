from __future__ import annotations

import hmac
import csv
import io
import os
from decimal import Decimal, InvalidOperation
from html import escape

from flask import Flask, Response, jsonify, request
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from urllib.parse import quote

from tap.mobile.offline_sync import apply_sync_events
from tap.mobile.portal_service import get_portal_data, get_portal_payments, sign_portal_payment
from tap.mobile.payment_links import get_payment_link, submit_payment_proof
from tap.infrastructure.database.repository import ajouter_paiement_complementaire
from tap.mobile.qr import png_data_uri
from tap.mobile.runtime import receipt_url


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 3 * 1024 * 1024

    @app.get("/api/mobile/health")
    def health():
        return jsonify({"status": "ok", "service": "tap-mobile", "offline_sync": True})

    @app.get("/api/portal/<token>/data")
    def portal_data(token: str):
        data = get_portal_data(token)
        if data is None:
            return jsonify({"error": "Lien invalide ou expiré."}), 404
        return jsonify(data)

    @app.get("/api/portal/<token>/payments")
    def portal_payments(token: str):
        data = get_portal_payments(token, **{
            key: request.args.get(key, "")
            for key in ("search", "status", "date_from", "date_to", "amount_min", "amount_max")
        })
        if data is None:
            return jsonify({"error": "Lien invalide ou expiré."}), 404
        return jsonify(data)

    @app.get("/api/portal/<token>/payments/<int:payment_id>")
    def portal_payment_detail(token: str, payment_id: int):
        data = get_portal_payments(token, payment_id=payment_id)
        if data is None or not data["payments"]:
            return jsonify({"error": "Paiement introuvable."}), 404
        return jsonify({"tenant": data["tenant"], "payment": data["payments"][0]})

    @app.get("/api/portal/<token>/payments.csv")
    def portal_payments_csv(token: str):
        data = get_portal_payments(token)
        if data is None:
            return jsonify({"error": "Lien invalide ou expiré."}), 404
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Date", "Montant", "Devise", "Methode", "Reference", "Statut", "Prestation"])
        for payment in data["payments"]:
            writer.writerow([
                payment["mois"], payment["montant_total"], payment["devise"],
                payment["methode_paiement"], payment["reference"],
                payment["statut_affiche"], payment["prestation"],
            ])
        return Response(
            "\ufeff" + output.getvalue(), mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=mes_paiements.csv"},
        )

    @app.get("/api/portal/<token>/payments/<int:payment_id>/invoice.pdf")
    def portal_payment_invoice(token: str, payment_id: int):
        data = get_portal_payments(token, payment_id=payment_id)
        if data is None or not data["payments"]:
            return jsonify({"error": "Paiement introuvable."}), 404
        payment = data["payments"][0]
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 18)
        pdf.cell(0, 12, "Justificatif de paiement TAP", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 11)
        for label, value in (("Locataire", f"{data['tenant']['prenom']} {data['tenant']['nom']}"),
                             ("Reference", payment["reference"]),
                             ("Prestation", payment["prestation"]),
                             ("Montant", f"{payment['montant_total']} {payment['devise']}"),
                             ("Paye", f"{payment['montant_paye']} {payment['devise']}"),
                             ("Reste", f"{payment['reste_a_payer']} {payment['devise']}"),
                             ("Statut", payment["statut_affiche"])):
            pdf.cell(45, 9, label)
            pdf.cell(0, 9, str(value), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        return Response(bytes(pdf.output()), mimetype="application/pdf", headers={
            "Content-Disposition": f"attachment; filename=facture_{payment_id}.pdf"
        })

    @app.post("/api/portal/<token>/payments/<int:payment_id>/sign")
    def portal_sign(token: str, payment_id: int):
        body = request.get_json(silent=True) or {}
        ok, message = sign_portal_payment(
            token, payment_id, body.get("signature", ""), bool(body.get("consent")),
            request.remote_addr or "", request.headers.get("User-Agent", ""),
        )
        return jsonify({"status": "signed" if ok else "error", "message": message}), 200 if ok else 400

    @app.post("/api/pay/<token>/proof")
    def payment_proof(token: str):
        body = request.get_json(silent=True) or {}
        try:
            ok, message = submit_payment_proof(
                token,
                body.get("proof", ""),
                body.get("note", ""),
            )
        except ValueError as exc:
            return jsonify({"status": "error", "message": str(exc)}), 400
        return jsonify({"status": "submitted" if ok else "error", "message": message}), 200 if ok else 400

    @app.post("/api/mobile/sync")
    def sync():
        expected = os.getenv("TAP_MOBILE_API_KEY", "").strip()
        provided = request.headers.get("X-TAP-Mobile-Key", "")
        if not expected or not hmac.compare_digest(expected, provided):
            return jsonify({"error": "Authentification mobile requise."}), 401
        body = request.get_json(silent=True) or {}
        events = body.get("events", [])
        if not isinstance(events, list) or len(events) > 100:
            return jsonify({"error": "Lot d'événements invalide."}), 400
        return jsonify({"results": apply_sync_events(events)})

    @app.post("/api/mobile/payments/<int:payment_id>/record")
    def record_payment(payment_id: int):
        expected = os.getenv("TAP_MOBILE_API_KEY", "").strip()
        provided = request.headers.get("X-TAP-Mobile-Key", "")
        if not expected or not hmac.compare_digest(expected, provided):
            return jsonify({"error": "Authentification mobile requise."}), 401
        body = request.get_json(silent=True) or {}
        try:
            amount = Decimal(str(body.get("amount", "0")))
            if amount <= 0 or amount.as_tuple().exponent < -2:
                raise ValueError
        except (TypeError, ValueError, InvalidOperation):
            return jsonify({"error": "Le montant doit être positif."}), 400
        ok, message = ajouter_paiement_complementaire(payment_id, amount)
        return jsonify({"status": "ok" if ok else "error", "message": message}), 200 if ok else 400

    @app.get("/portal/<token>")
    def portal_page(token: str):
        return _portal_html(token)

    @app.get("/pay/<token>")
    def payment_page(token: str):
        data = get_payment_link(token)
        if not data:
            return "Lien de paiement invalide, expiré ou déjà traité.", 404
        return _payment_link_html(token, data)

    @app.get("/portal/<token>/payments/<int:payment_id>/receipt")
    def portal_receipt(token: str, payment_id: int):
        data = get_portal_data(token)
        if not data:
            return "Lien invalide ou expiré.", 404
        payment = next((p for p in data["payments"] if int(p["id"]) == payment_id), None)
        if not payment:
            return "Paiement introuvable.", 404
        url = receipt_url(
            quote(token, safe=""),
            payment_id,
            base_url=request.url_root.rstrip("/"),
        )
        return _receipt_html(data["tenant"], payment, url)

    return app


def _portal_html(token: str) -> str:
    safe_token = escape(token, quote=True)
    page = """<!doctype html>
<html lang='fr'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Portail locataire TAP</title><style>
*{{box-sizing:border-box}}html{{overflow-x:hidden}}body{{margin:0;min-width:280px;background:#f6f1e8;color:#2b2118;font-family:Arial,sans-serif}}main{{width:min(100%,760px);margin:auto;padding:clamp(12px,3vw,24px)}}.card{{width:100%;background:#fffaf1;border:1px solid #d7c3a4;border-radius:14px;padding:clamp(14px,3vw,24px);box-shadow:0 6px 20px #2f22181c}}h1{{font-size:clamp(21px,5vw,30px);line-height:1.15;overflow-wrap:anywhere}}.filters{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}}label{{display:grid;gap:4px;font-weight:700}}input,select{{width:100%;min-height:42px;padding:8px;border:1px solid #b9a486;border-radius:6px;background:#fff;color:#2b2118}}.table-wrap{{width:100%;overflow-x:auto}}table{{width:100%;min-width:700px;border-collapse:collapse;background:#fff}}th,td{{padding:10px 8px;border-bottom:1px solid #eadcc8;text-align:left;vertical-align:top;overflow-wrap:anywhere}}th{{background:#efe3d0}}td a{{color:#125c83;font-weight:700}}.payment{{background:white;border:1px solid #eadcc8;border-radius:10px;margin:10px 0;padding:clamp(12px,2.5vw,18px);overflow:hidden}}.row{{display:grid;grid-template-columns:minmax(90px,38%) minmax(0,1fr);align-items:start;gap:12px;padding:8px 0;border-bottom:1px solid #eadcc8}}.row strong{{min-width:0;overflow-wrap:anywhere;text-align:right}}.muted{{color:#6f604f}}.ok{{color:#2e7d32}}.warn{{color:#8f2d2d;font-weight:700}}button{{width:100%;min-height:46px;border:0;border-radius:8px;padding:13px;margin-top:10px;background:#b99057;color:#130d07;font-weight:700;font-size:15px;cursor:pointer}}#signBox{{display:none;background:white;border:1px solid #d7c3a4;border-radius:10px;padding:12px;margin-top:14px}}canvas{{display:block;width:100%;height:min(190px,45vw);min-height:140px;background:#fff;border:2px dashed #b99057;border-radius:8px;touch-action:none}}#message{{font-weight:700;margin-top:8px;overflow-wrap:anywhere}}@media(max-width:520px){{main{{padding:10px}}.filters{{grid-template-columns:1fr}}.row{{grid-template-columns:1fr;gap:4px}}.row strong{{text-align:left}}}}@media(orientation:landscape) and (max-height:520px){{main{{padding:10px}}h1{{margin:8px 0}}}}
</style></head><body><main><section class='card'><h1>Portail locataire TAP</h1><nav aria-label='Navigation du portail'><a href='#payments'>Mes paiements</a></nav><div id='notifications' role='status' aria-live='polite'></div><section id='payments' aria-labelledby='payments-title'><h2 id='payments-title'>Mes paiements</h2><form id='filters' class='filters'><label>Recherche<input id='search' type='search' placeholder='Référence, devise ou statut'></label><label>Statut<select id='status'><option value=''>Tous</option><option>Complet</option><option>Partiel</option><option>En attente</option></select></label><label>Du<input id='date_from' type='date'></label><label>Au<input id='date_to' type='date'></label><button type='submit'>Filtrer</button><button type='button' id='reset'>Réinitialiser</button></form><p><a id='csv' download href='#'>Exporter CSV</a></p><div class='table-wrap'><table><thead><tr><th>Date</th><th>Montant</th><th>Méthode</th><th>Référence</th><th>Statut</th><th>Prestation</th><th>Actions</th></tr></thead><tbody id='payments-body'><tr><td colspan='7'>Chargement...</td></tr></tbody></table></div></section><div id='app' hidden></div></section></main><script>
const token='__TOKEN__';let selected=null,dirty=false;const app=document.getElementById('app');const body=document.getElementById('payments-body');const filters=document.getElementById('filters');
function text(tag,value,cls=''){{const e=document.createElement(tag);e.textContent=value;if(cls)e.className=cls;return e;}}
function query(){{const params=new URLSearchParams();['search','status','date_from','date_to'].forEach(id=>{{const value=document.getElementById(id).value;if(value)params.set(id,value);}});return params.toString();}}
function load(){{const suffix=query();fetch('/api/portal/'+token+'/payments'+(suffix?'?'+suffix:'')).then(r=>r.json().then(data=>{{if(!r.ok||data.error)throw Error(data.error||'Le portail est temporairement indisponible.');return data;}})).then(data=>{{body.replaceChildren();data.payments.forEach(p=>{{const row=document.createElement('tr');[p.mois,p.montant_total+' '+p.devise,p.methode_paiement,p.reference,p.statut_affiche,p.prestation].forEach((value,index)=>{{const cell=text('td',value,index===4?(p.statut_affiche==='Complet'?'ok':'warn'):'');row.append(cell);}});const actions=text('td');const detail=document.createElement('a');detail.href='/api/portal/'+token+'/payments/'+p.id;detail.textContent='Détail';detail.target='_blank';actions.append(detail,' | ');const invoice=document.createElement('a');invoice.href='/api/portal/'+token+'/payments/'+p.id+'/invoice.pdf';invoice.textContent='Facture PDF';invoice.download='';actions.append(invoice);row.append(actions);body.append(row);}});document.getElementById('csv').href='/api/portal/'+token+'/payments.csv';const pending=data.payments.filter(p=>p.statut_affiche==='En attente').length;document.getElementById('notifications').textContent=pending?pending+' paiement(s) en attente.':'Vos paiements sont à jour.';}}).catch(e=>body.replaceChildren(text('tr',e.message||'Connexion impossible. Vérifiez que TAP est démarré et que le téléphone est sur le même Wi-Fi.','warn')));}}
filters.onsubmit=e=>{{e.preventDefault();load();}};document.getElementById('reset').onclick=()=>{{filters.reset();load();}};
function openSign(id){{selected=id;dirty=false;document.getElementById('signBox').style.display='block';document.getElementById('message').textContent='';resize();window.scrollTo(0,document.body.scrollHeight);}}
const box=document.createElement('div');box.id='signBox';box.innerHTML='<h3>Signature tactile</h3><canvas id="pad"></canvas><button id="clear" type="button">Effacer</button><label><input id="consent" type="checkbox"> Je confirme ce reçu.</label><button id="send" type="button">Signer et envoyer</button><div id="message"></div>';app.append(box);const canvas=document.getElementById('pad'),ctx=canvas.getContext('2d');let drawing=false;
function resize(){{const r=canvas.getBoundingClientRect(),ratio=devicePixelRatio||1;canvas.width=r.width*ratio;canvas.height=r.height*ratio;ctx.setTransform(ratio,0,0,ratio,0,0);ctx.lineWidth=3;ctx.lineCap='round';ctx.strokeStyle='#1d1710';}}
function point(e){{const r=canvas.getBoundingClientRect();return [e.clientX-r.left,e.clientY-r.top];}}canvas.onpointerdown=e=>{{drawing=true;dirty=true;canvas.setPointerCapture(e.pointerId);const p=point(e);ctx.beginPath();ctx.moveTo(...p);}};canvas.onpointermove=e=>{{if(drawing){{const p=point(e);ctx.lineTo(...p);ctx.stroke();}}}};canvas.onpointerup=()=>drawing=false;canvas.onpointercancel=()=>drawing=false;document.getElementById('clear').onclick=()=>{{ctx.clearRect(0,0,canvas.width,canvas.height);dirty=false;}};document.getElementById('send').onclick=()=>{{const m=document.getElementById('message');if(!selected||!dirty||!document.getElementById('consent').checked){{m.textContent='Signez et confirmez votre consentement.';return;}}m.textContent='Envoi...';fetch('/api/portal/'+token+'/payments/'+selected+'/sign',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{consent:true,signature:canvas.toDataURL('image/png')}})}}).then(r=>r.json()).then(d=>{{m.textContent=d.message;if(d.status==='signed')load();}}).catch(()=>m.textContent='Connexion impossible. Réessayez lorsque le réseau revient.');}};window.onresize=resize;load();
</script></body></html>"""
    # Le HTML est écrit comme un modèle lisible ; les doubles accolades ne
    # sont utiles que dans une f-string. Ici la page est remplacée directement
    # et elles doivent redevenir des accolades JavaScript/CSS normales.
    return page.replace("__TOKEN__", safe_token).replace("{{", "{").replace("}}", "}")


def _payment_link_html(token: str, data: dict) -> str:
    safe_token = escape(token, quote=True)
    tenant = escape(f"{data.get('prenom', '')} {data.get('nom', '')}".strip())
    amount = escape(str(data.get("montant_demande", "")))
    currency = escape(str(data.get("devise", "")))
    month = escape(str(data.get("mois", "")))
    page = """<!doctype html><html lang='fr'><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'><title>Paiement TAP</title>
<style>body{margin:0;background:#f6f1e8;color:#2b2118;font-family:Arial,sans-serif}main{max-width:560px;margin:auto;padding:16px}.card{background:#fffaf1;border:1px solid #d7c3a4;border-radius:14px;padding:20px;box-shadow:0 6px 20px #2f22181c}h1{font-size:23px}.row{display:flex;justify-content:space-between;border-bottom:1px solid #eadcc8;padding:10px 0}.muted{color:#6f604f}input,textarea,button{box-sizing:border-box;width:100%;padding:13px;margin-top:12px;border-radius:8px;border:1px solid #d7c3a4;font-size:15px}button{border:0;background:#b99057;color:#130d07;font-weight:700}#message{font-weight:700;margin-top:14px}.ok{color:#2e7d32}.warn{color:#c45b12}</style></head><body><main><section class='card'><h1>Paiement sécurisé TAP</h1><p>Demande pour <strong>__TENANT__</strong></p><div class='row'><span class='muted'>Mois</span><strong>__MONTH__</strong></div><div class='row'><span class='muted'>Montant à régler</span><strong>__AMOUNT__ __CURRENCY__</strong></div><p class='muted'>Effectuez le paiement avec votre moyen habituel, puis joignez la preuve de paiement. Le gestionnaire la vérifiera avant validation.</p><label>Preuve (PNG, JPEG ou PDF, 2 Mo maximum)<input id='proof' type='file' accept='image/png,image/jpeg,application/pdf'></label><textarea id='note' rows='3' placeholder='Référence ou remarque (facultatif)'></textarea><button id='send'>Envoyer la preuve</button><div id='message'></div></section></main><script>const token='__TOKEN__';const message=document.getElementById('message');document.getElementById('send').onclick=()=>{const file=document.getElementById('proof').files[0];if(!file){message.textContent='Sélectionnez une preuve de paiement.';message.className='warn';return;}if(file.size>2*1024*1024){message.textContent='La preuve dépasse 2 Mo.';message.className='warn';return;}const reader=new FileReader();reader.onload=()=>{message.textContent='Envoi...';message.className='';fetch('/api/pay/'+token+'/proof',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({proof:reader.result,note:document.getElementById('note').value})}).then(r=>r.json()).then(data=>{message.textContent=data.message;message.className=data.status==='submitted'?'ok':'warn';if(data.status==='submitted')document.getElementById('send').disabled=true;}).catch(()=>{message.textContent='Connexion impossible. Réessayez lorsque le réseau revient.';message.className='warn';});};reader.readAsDataURL(file);};</script></body></html>"""
    return (
        page.replace("__TOKEN__", safe_token)
        .replace("__TENANT__", tenant)
        .replace("__MONTH__", month)
        .replace("__AMOUNT__", amount)
        .replace("__CURRENCY__", currency)
    )


def _receipt_html(tenant: dict, payment: dict, verification_url: str = "") -> str:
    values = {
        "nom": f"{tenant.get('prenom', '')} {tenant.get('nom', '')}".strip(),
        "mois": payment.get("mois", ""),
        "total": f"{payment.get('montant_total', '')} {payment.get('devise', '')}",
        "paye": f"{payment.get('montant_paye', '')} {payment.get('devise', '')}",
        "reste": f"{payment.get('reste_a_payer', '')} {payment.get('devise', '')}",
        "statut": payment.get("statut", ""),
    }
    safe = {key: escape(str(value)) for key, value in values.items()}
    try:
        qr_uri = png_data_uri(verification_url) if verification_url else ""
    except Exception:
        qr_uri = ""
    qr_block = (
        f"<div class='qr'><img src='{escape(qr_uri, quote=True)}' alt='QR de vérification'>"
        "<small>Scanner pour rouvrir ce reçu</small></div>"
        if qr_uri
        else "<p class='muted'>QR indisponible : conservez ce lien pour vérifier le reçu.</p>"
    )
    return f"""<!doctype html><html lang='fr'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Reçu TAP</title><style>body{{font-family:Arial;max-width:680px;margin:auto;padding:20px;color:#2b2118}}.receipt{{border:2px solid #d7c3a4;padding:24px;border-radius:12px}}.row{{display:flex;justify-content:space-between;padding:12px 0;border-bottom:1px solid #eadcc8}}.qr{{text-align:center;margin:24px 0 8px}}.qr img{{width:170px;height:170px;display:block;margin:auto}}.qr small,.muted{{color:#6f604f}}button{{width:100%;padding:14px;margin-top:20px}}@media print{{button{{display:none}}}}</style></head><body><section class='receipt'><h1>Reçu de paiement</h1><div class='row'><span>Locataire</span><strong>{safe['nom']}</strong></div><div class='row'><span>Mois</span><strong>{safe['mois']}</strong></div><div class='row'><span>Total</span><strong>{safe['total']}</strong></div><div class='row'><span>Payé</span><strong>{safe['paye']}</strong></div><div class='row'><span>Reste</span><strong>{safe['reste']}</strong></div><div class='row'><span>Statut</span><strong>{safe['statut']}</strong></div>{qr_block}<button onclick='window.print()'>Imprimer / enregistrer en PDF</button></section></body></html>"""
