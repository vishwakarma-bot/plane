# Generated manually for P7 review fixes

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("db", "0001_initial"),
        ("agent_infra", "0012_authorization_policy_p7"),
    ]

    operations = [
        migrations.AddField(
            model_name="emergencydeny",
            name="project",
            field=models.ForeignKey(
                blank=True,
                help_text="Project scope. Null means workspace-wide (requires workspace admin).",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="emergency_denies",
                to="db.project",
            ),
        ),
        migrations.RemoveIndex(
            model_name="emergencydeny",
            name="agent_infra_ed_ws_active_idx",
        ),
        migrations.AddIndex(
            model_name="emergencydeny",
            index=models.Index(
                fields=["workspace", "project", "is_active"],
                name="ai_ed_ws_proj_active_idx",
            ),
        ),
    ]
