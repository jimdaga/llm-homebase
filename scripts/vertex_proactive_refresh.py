"""
LiteLLM callback module: proactive Vertex AI token refresh.

Patches google.oauth2.credentials.Credentials.expired to report expiry
5 minutes before the token actually expires. This makes LiteLLM's sync
get_access_token() path refresh proactively — the same behaviour the
async path already has via TokenState.STALE handling.

Only affects authorized_user credentials (from gcloud auth
application-default login). Service account and compute engine
credentials inherit expired from the base class and are unaffected.

Usage in config.yaml:
    litellm_settings:
        callbacks:
            - scripts.vertex_proactive_refresh.proxy_handler_instance
"""

import datetime
import logging

import google.auth._helpers
import google.oauth2.credentials
from litellm.integrations.custom_logger import CustomLogger

logger = logging.getLogger("litellm.proxy")

PROACTIVE_REFRESH_MINUTES = 5
_BUFFER = datetime.timedelta(minutes=PROACTIVE_REFRESH_MINUTES)


def _proactive_expired(self):
    if self.expiry is None:
        return False
    return google.auth._helpers.utcnow() >= (self.expiry - _BUFFER)


google.oauth2.credentials.Credentials.expired = property(_proactive_expired)

logger.info(
    "Vertex AI proactive token refresh enabled — "
    "credentials will refresh %d minutes before expiry",
    PROACTIVE_REFRESH_MINUTES,
)


class VertexProactiveRefreshCallback(CustomLogger):
    """No-op callback; the module-level import applies the patch."""

    pass


proxy_handler_instance = VertexProactiveRefreshCallback()
