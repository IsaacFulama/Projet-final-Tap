"""Lance le serveur mobile TAP sur le réseau local."""

import os
import argparse

from tap.mobile.api import create_app
from tap.mobile.portal_service import create_portal_token


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--create-token", type=int, metavar="LOCATAIRE_ID")
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()
    if args.create_token:
        token, expires_at = create_portal_token(args.create_token, args.days)
        host = os.getenv("TAP_MOBILE_HOST_PUBLIC", "127.0.0.1")
        port = os.getenv("TAP_MOBILE_PORT", "8765")
        print(f"Lien portail : http://{host}:{port}/portal/{token}")
        print(f"Expire le : {expires_at.isoformat()}")
        raise SystemExit(0)
    app = create_app()
    app.run(
        host=os.getenv("TAP_MOBILE_HOST", "0.0.0.0"),
        port=int(os.getenv("TAP_MOBILE_PORT", "8765")),
        debug=False,
    )
