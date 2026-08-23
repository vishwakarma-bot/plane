# Generated manually

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("agent_infra", "0008_knowledge_index_record"),
        ("db", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="KnowledgeConflict",
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
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Last Modified At")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="Deleted At")),
                (
                    "conflict_type",
                    models.CharField(
                        choices=[
                            ("authority", "Authority Conflict (multiple approved versions)"),
                            ("semantic", "Semantic Conflict (contradictory content across sources)"),
                            ("staleness", "Staleness Conflict (expired source still referenced)"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("open", "Open"),
                            ("acknowledged", "Acknowledged"),
                            ("resolved", "Resolved"),
                            ("superseded", "Superseded"),
                        ],
                        default="open",
                        max_length=20,
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text="Auto-generated or human-provided conflict description",
                    ),
                ),
                (
                    "resolution_summary",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text="How the conflict was resolved",
                    ),
                ),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                (
                    "blocks_execution",
                    models.BooleanField(
                        default=True,
                        help_text="Whether this conflict blocks assignment execution",
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="knowledge_conflicts",
                        to="db.workspace",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="knowledge_conflicts",
                        to="db.project",
                    ),
                ),
                (
                    "version_a",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="conflicts_as_a",
                        to="agent_infra.knowledgeversion",
                    ),
                ),
                (
                    "version_b",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="conflicts_as_b",
                        to="agent_infra.knowledgeversion",
                    ),
                ),
                (
                    "resolved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="resolved_knowledge_conflicts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "winning_version",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="conflict_wins",
                        to="agent_infra.knowledgeversion",
                        help_text="The version that prevails after resolution",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="knowledgeconflict_created_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Created By",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="knowledgeconflict_updated_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Updated By",
                    ),
                ),
            ],
            options={
                "db_table": "agent_infra_knowledge_conflicts",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="knowledgeconflict",
            index=models.Index(
                fields=["workspace", "project", "status"],
                name="idx_kc_ws_proj_status",
            ),
        ),
        migrations.AddConstraint(
            model_name="knowledgeconflict",
            constraint=models.CheckConstraint(
                check=~models.Q(version_a=models.F("version_b")),
                name="conflict_versions_differ",
            ),
        ),
    ]
