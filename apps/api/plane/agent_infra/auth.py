# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.


def requires_service_identity(permission: str, methods=None):
    """Mark a view class as requiring a validated service identity.

    Args:
        permission: The permission string to check against the service identity.
        methods: HTTP methods to enforce (defaults to ["POST"] for backward compat).
    """

    def decorator(view_class):
        view_class.requires_service_identity = permission
        if methods:
            view_class.service_identity_methods = [m.upper() for m in methods]
        return view_class

    return decorator
