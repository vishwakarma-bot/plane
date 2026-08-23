# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("agent_infra", "0004_rename_agent_infra_workspa_5d0f8f_idx_agent_infra_workspa_7675d0_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="idempotencyrecord",
            name="fingerprint_hash",
            field=models.CharField(default="", max_length=64),
        ),
        migrations.AlterField(
            model_name="idempotencyrecord",
            name="idempotency_key",
            field=models.UUIDField(db_index=True, unique=True),
        ),
    ]
