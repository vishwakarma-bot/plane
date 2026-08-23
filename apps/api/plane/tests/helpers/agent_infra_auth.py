# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import hashlib
import hmac
import json
import uuid

from django.utils import timezone

from plane.agent_infra.models import ServiceIdentity


def create_service_identity(
    workspace,
    *,
    service_id="dev-center-test",
    signing_secret="test-signing-secret",
    permissions=None,
):
    identity = ServiceIdentity(
        name="Test Dev Center",
        service_id=service_id,
        workspace=workspace,
        permissions=permissions or [],
        is_active=True,
    )
    identity.set_signing_secret(signing_secret)
    identity.save()
    return identity


def sign_request(
    service_identity: ServiceIdentity,
    method: str,
    path: str,
    body_bytes: bytes,
    timestamp: str | None = None,
    request_id: str | None = None,
):
    """Build HMAC headers using the canonical signature format."""
    timestamp = timestamp or timezone.now().isoformat()
    request_id = request_id or str(uuid.uuid4())
    raw_secret = service_identity.get_raw_signing_secret()
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    canonical = "\n".join([
        method.upper(),
        path.split("?")[0],
        body_hash,
        service_identity.service_id,
        timestamp,
        request_id,
    ])
    signature = hmac.new(
        raw_secret.encode("utf-8"),
        canonical.encode("utf-8"),
        digestmod="sha256",
    ).hexdigest()
    return {
        "HTTP_X_SERVICE_ID": service_identity.service_id,
        "HTTP_X_SIGNATURE": signature,
        "HTTP_X_TIMESTAMP": timestamp,
        "HTTP_X_REQUEST_ID": request_id,
    }


def signed_json_post(client, url, payload, service_identity, **extra_headers):
    safe_payload = json.loads(json.dumps(payload, default=str))
    body_bytes = json.dumps(safe_payload).encode("utf-8")
    headers = sign_request(service_identity, "POST", url, body_bytes)
    headers.update(extra_headers)
    return client.post(url, data=body_bytes, content_type="application/json", **headers)
