# Generated manually

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("agent_infra", "0007_knowledge_source_version_manifest"),
        ("db", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="KnowledgeIndexRecord",
            fields=[
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("index", "Index"),
                            ("reindex", "Reindex"),
                            ("delete", "Delete"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("acknowledged", "Acknowledged"),
                            ("in_progress", "In Progress"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("requested_at", models.DateTimeField(auto_now_add=True)),
                ("acknowledged_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("failed_at", models.DateTimeField(blank=True, null=True)),
                ("failure_reason", models.TextField(blank=True, default="")),
                ("retry_count", models.PositiveIntegerField(default=0)),
                ("max_retries", models.PositiveIntegerField(default=3)),
                (
                    "external_ref",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Reference ID in the downstream index/vector store",
                        max_length=255,
                    ),
                ),
                (
                    "last_observed_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="Last time the index state was verified",
                        null=True,
                    ),
                ),
                (
                    "is_verified",
                    models.BooleanField(
                        default=False,
                        help_text="Whether the action has been verified in the downstream system",
                    ),
                ),
                (
                    "knowledge_version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="index_records",
                        to="agent_infra.knowledgeversion",
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="knowledge_index_records",
                        to="db.workspace",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="knowledge_index_records",
                        to="db.project",
                    ),
                ),
            ],
            options={
                "db_table": "agent_infra_knowledge_index_records",
                "ordering": ["-requested_at"],
            },
        ),
        migrations.AddIndex(
            model_name="knowledgeindexrecord",
            index=models.Index(
                fields=["workspace", "project", "status"],
                name="idx_kir_ws_proj_status",
            ),
        ),
        migrations.AddIndex(
            model_name="knowledgeindexrecord",
            index=models.Index(
                fields=["knowledge_version", "action"],
                name="idx_kir_version_action",
            ),
        ),
    ]
