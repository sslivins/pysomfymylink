"""pysomfymylink — async client for the Somfy MyLink Synergy socket API.

A clean-room rewrite of the transport layer of the original, unmaintained
``somfy-mylink-synergy`` library by Ben Dews. See the README for details and
credit.
"""

from .client import SomfyMyLink
from .const import ALL_TARGETS, DEFAULT_PORT, DEFAULT_TIMEOUT
from .errors import (
    SomfyMyLinkApiError,
    SomfyMyLinkConnectionError,
    SomfyMyLinkError,
    SomfyMyLinkTimeoutError,
)
from .models import Shade

__version__ = "1.0.0"

__all__ = [
    "SomfyMyLink",
    "Shade",
    "SomfyMyLinkError",
    "SomfyMyLinkConnectionError",
    "SomfyMyLinkTimeoutError",
    "SomfyMyLinkApiError",
    "ALL_TARGETS",
    "DEFAULT_PORT",
    "DEFAULT_TIMEOUT",
    "__version__",
]
