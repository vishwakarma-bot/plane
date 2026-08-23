# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Test Settings"""

from .common import *  # noqa

DEBUG = True

# Send it in a dummy outbox
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Run Celery tasks synchronously in tests (no broker required)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Use in-memory cache for tests (no Redis required)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = ()  # noqa
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {}  # noqa

API_KEY_RATE_LIMIT = "10000/minute"

INSTALLED_APPS.append(  # noqa
    "plane.tests"
)
