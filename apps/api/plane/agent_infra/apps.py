# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.apps import AppConfig


class AgentInfraConfig(AppConfig):
    name = "plane.agent_infra"

    def ready(self):
        import plane.agent_infra.signals  # noqa: F401
