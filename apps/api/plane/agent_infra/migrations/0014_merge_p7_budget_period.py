# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("agent_infra", "0012_modelroutingconfig_budget_period_started_at"),
        ("agent_infra", "0013_emergencydeny_project_scope"),
    ]

    operations = []
