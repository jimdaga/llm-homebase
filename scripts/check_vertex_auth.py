#!/usr/bin/env python3
"""
Diagnostic script for Vertex AI credential state.

Run from the host to check ADC validity:
    python3 scripts/check_vertex_auth.py

Run inside the container to verify the proactive refresh patch:
    podman exec llm-homebase_litellm_1 python3 /app/scripts/check_vertex_auth.py
"""

import sys

import google.auth
import google.auth._helpers
import google.auth.transport.requests
import google.oauth2.credentials


def main():
    patched = "expired" in google.oauth2.credentials.Credentials.__dict__
    print(f"Proactive refresh patch active: {patched}")

    try:
        creds, project = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
    except Exception as e:
        print(f"FAIL: could not load credentials: {e}", file=sys.stderr)
        return 1

    print(f"Credential type: {type(creds).__name__}")
    print(f"Project: {project}")
    print(f"Has refresh token: {bool(getattr(creds, 'refresh_token', None))}")

    if creds.token is None:
        print("No cached token — refreshing...")
        try:
            creds.refresh(google.auth.transport.requests.Request())
        except Exception as e:
            print(f"FAIL: refresh failed: {e}", file=sys.stderr)
            return 1

    now = google.auth._helpers.utcnow()
    print(f"Token valid: {creds.valid}")
    print(f"Token expiry: {creds.expiry}")

    if creds.expiry is not None:
        remaining = creds.expiry - now
        print(f"Time until actual expiry: {remaining}")
        if patched:
            from scripts.vertex_proactive_refresh import _BUFFER

            proactive_remaining = creds.expiry - _BUFFER - now
            if proactive_remaining.total_seconds() > 0:
                print(f"Time until proactive refresh: {proactive_remaining}")
            else:
                print("Proactive refresh: would trigger NOW")

    print(f"Token prefix: {creds.token[:20]}..." if creds.token else "Token: None")
    return 0


if __name__ == "__main__":
    sys.exit(main())
