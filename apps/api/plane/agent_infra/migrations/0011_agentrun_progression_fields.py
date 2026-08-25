# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("agent_infra", "0010_alter_knowledgeconflict_created_by_and_more"),
        ("agent_infra", "0008_catalogrevision_compatibilityrecord_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="agentrun",
            name="progression_outcome",
            field=models.CharField(
                blank=True,
                choices=[
                    ("auto_progress", "Auto Progress"),
                    ("awaiting_disposition", "Awaiting Disposition"),
                    ("blocked", "Blocked"),
                ],
                max_length=50,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="agentrun",
            name="progression_reason",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="agentrun",
            name="progression_evaluated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="agentrun",
            index=models.Index(
                fields=["workspace", "project", "progression_outcome"],
                name="agent_infra_workspa_prog_idx",
            ),
        ),
    ]
