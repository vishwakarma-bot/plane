# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.


def requires_service_identity(permission: str):
    """Mark a view class as requiring a validated service identity for POST requests."""

    def decorator(view_class):
        view_class.requires_service_identity = permission
        return view_class

    return decorator
