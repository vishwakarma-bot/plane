# Generated manually for A2A outbox event types

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("agent_infra", "0014_merge_p7_budget_period"),
    ]

    operations = [
        migrations.AlterField(
            model_name="agentinfraoutbox",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("assignment_created", "Assignment Created"),
                    ("assignment_cancelled", "Assignment Cancelled"),
                    ("disposition_created", "Disposition Created"),
                    ("agent_handoff", "Agent Handoff"),
                    ("agent_result", "Agent Result"),
                    ("agent_request", "Agent Request"),
                    ("agent_message", "Agent Message"),
                ],
                max_length=50,
            ),
        ),
    ]
