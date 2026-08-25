# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("agent_infra", "0011_agentrun_progression_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="modelroutingconfig",
            name="budget_period_started_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
    ]
