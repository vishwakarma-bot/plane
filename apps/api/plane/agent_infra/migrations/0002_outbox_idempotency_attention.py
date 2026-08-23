# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("agent_infra", "0001_initial"),
        ("db", "0123_project_is_agent_infra_enabled"),
    ]

    operations = [
        migrations.CreateModel(
            name="AgentInfraOutbox",
            fields=[
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Created At"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="Last Modified At"),
                ),
                (
                    "deleted_at",
                    models.DateTimeField(blank=True, null=True, verbose_name="Deleted At"),
                ),
                (
                    "id",
                    models.UUIDField(
                        db_index=True,
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        unique=True,
                    ),
                ),
                (
                    "event_type",
                    models.CharField(
                        choices=[
                            ("assignment_created", "Assignment Created"),
                            ("assignment_cancelled", "Assignment Cancelled"),
                            ("disposition_created", "Disposition Created"),
                        ],
                        max_length=50,
                    ),
                ),
                ("payload", models.JSONField()),
                ("idempotency_key", models.UUIDField(default=uuid.uuid4, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("sent", "Sent"),
                            ("failed", "Failed"),
                            ("expired", "Expired"),
                        ],
                        default="pending",
                        max_length=50,
                    ),
                ),
                ("attempts", models.IntegerField(default=0)),
                ("max_attempts", models.IntegerField(default=5)),
                ("last_attempted_at", models.DateTimeField(blank=True, null=True)),
                ("next_attempt_at", models.DateTimeField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True, default="")),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Created By",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="agent_infra_outbox_events",
                        to="db.project",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_updated_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Last Modified By",
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="agent_infra_outbox_events",
                        to="db.workspace",
                    ),
                ),
            ],
            options={
                "verbose_name": "Agent Infra Outbox Event",
                "verbose_name_plural": "Agent Infra Outbox Events",
                "db_table": "agent_infra_outbox",
                "ordering": ("next_attempt_at",),
            },
        ),
        migrations.CreateModel(
            name="IdempotencyRecord",
            fields=[
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Created At"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="Last Modified At"),
                ),
                (
                    "deleted_at",
                    models.DateTimeField(blank=True, null=True, verbose_name="Deleted At"),
                ),
                (
                    "id",
                    models.UUIDField(
                        db_index=True,
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        unique=True,
                    ),
                ),
                ("idempotency_key", models.UUIDField(unique=True)),
                ("response_status", models.IntegerField()),
                ("response_body", models.JSONField()),
                ("expires_at", models.DateTimeField()),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Created By",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_updated_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Last Modified By",
                    ),
                ),
            ],
            options={
                "verbose_name": "Idempotency Record",
                "verbose_name_plural": "Idempotency Records",
                "db_table": "agent_infra_idempotency",
            },
        ),
        migrations.CreateModel(
            name="AgentInfraAttentionItem",
            fields=[
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Created At"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="Last Modified At"),
                ),
                (
                    "deleted_at",
                    models.DateTimeField(blank=True, null=True, verbose_name="Deleted At"),
                ),
                (
                    "id",
                    models.UUIDField(
                        db_index=True,
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        unique=True,
                    ),
                ),
                ("entity_type", models.CharField(max_length=50)),
                ("entity_id", models.UUIDField()),
                ("drift_type", models.CharField(max_length=100)),
                ("details", models.JSONField(default=dict)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Created By",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="agent_infra_attention_items",
                        to="db.project",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_updated_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Last Modified By",
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="agent_infra_attention_items",
                        to="db.workspace",
                    ),
                ),
            ],
            options={
                "verbose_name": "Agent Infra Attention Item",
                "verbose_name_plural": "Agent Infra Attention Items",
                "db_table": "agent_infra_attention_items",
                "ordering": ("-created_at",),
            },
        ),
        migrations.AddIndex(
            model_name="agentinfraoutbox",
            index=models.Index(fields=["status", "next_attempt_at"], name="agent_infra_status_8f0d0d_idx"),
        ),
        migrations.AddIndex(
            model_name="idempotencyrecord",
            index=models.Index(fields=["expires_at"], name="agent_infra_expires_0d8f8a_idx"),
        ),
        migrations.AddIndex(
            model_name="agentinfraattentionitem",
            index=models.Index(
                fields=["workspace", "project", "resolved_at"],
                name="agent_infra_workspa_5d0f8f_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="agentinfraattentionitem",
            index=models.Index(
                fields=["entity_type", "entity_id", "drift_type"],
                name="agent_infra_entity__f8f8f8_idx",
            ),
        ),
    ]
