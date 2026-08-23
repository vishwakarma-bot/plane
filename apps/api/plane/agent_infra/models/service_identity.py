# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.db import models

# Module imports
from plane.db.models.base import BaseModel
from plane.license.utils.encryption import decrypt_data, encrypt_data


class ServiceIdentity(BaseModel):
    name = models.CharField(max_length=255)
    service_id = models.CharField(max_length=255, unique=True, db_index=True)
    signing_secret = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    workspace = models.ForeignKey(
        "db.Workspace",
        on_delete=models.CASCADE,
        related_name="service_identities",
    )
    last_seen_at = models.DateTimeField(null=True, blank=True)
    permissions = models.JSONField(default=list)

    class Meta:
        verbose_name = "Service Identity"
        verbose_name_plural = "Service Identities"
        db_table = "agent_infra_service_identities"
        ordering = ("name",)

    def __str__(self):
        return f"{self.name} ({self.service_id})"

    def set_signing_secret(self, raw_secret: str) -> None:
        """Store a plaintext signing secret encrypted at rest."""
        self.signing_secret = encrypt_data(raw_secret)

    def get_raw_signing_secret(self) -> str:
        """Return the decrypted signing secret for HMAC verification."""
        return decrypt_data(self.signing_secret)

    def verify_signing_secret(self, raw_secret: str) -> bool:
        """Verify a plaintext signing secret against the stored value."""
        stored = self.get_raw_signing_secret()
        return bool(stored) and stored == raw_secret

    def save(self, *args, **kwargs):
        if self.signing_secret and not decrypt_data(self.signing_secret):
            self.signing_secret = encrypt_data(self.signing_secret)
        super().save(*args, **kwargs)
