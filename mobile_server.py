"""Lance le serveur mobile TAP sur le réseau local."""

import os
import argparse

from tap.mobile.api import create_app
from tap.mobile.portal_service import create_portal_token
from tap.mobile.runtime import configure_mobile_environment


if __name__ == "__main__":
    mobile_config = configure_mobile_environment()
    parser = argparse.ArgumentParser()
    parser.add_argument("--create-token", type=int, metavar="LOCATAIRE_ID")
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()
    if args.create_token:
        token, expires_at = create_portal_token(args.create_token, args.days)
        host = mobile_config["public_host"]
        port = mobile_config["port"]
        print(f"Lien portail : http://{host}:{port}/portal/{token}")
        print(f"Expire le : {expires_at.isoformat()}")
        raise SystemExit(0)
    app = create_app()
    app.run(
        host=str(mobile_config["host"]),
        port=int(mobile_config["port"]),
        debug=False,
    )
