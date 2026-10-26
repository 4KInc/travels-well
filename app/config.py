"""One place for the things that are named rather than computed.

The product name appears in the page titles, the wordmark, the nav and the
submission copy. It lived in five files and drifted twice. It lives here now,
so renaming is one line rather than a search.
"""
from __future__ import annotations

import os

# The product. The repository and the Cloud Run service keep the earlier name
# `travels-well`; the README explains that in one line rather than renaming
# infrastructure during judging.
PRODUCT_NAME = os.environ.get("PRODUCT_NAME", "Taste Atlas")

# The three screens, named in one place so the nav and the <title> agree.
VIEW_NAMES = {
    "pitch": "Pitch desk",
    "atlas": "Audience Map",
    "slate": "Slate view",
}

REPO_URL = "https://github.com/4KInc/travels-well"

# A customer quote is shown on /about only when one has actually been given,
# with permission. Empty means the block does not render. Nothing is invented
# to fill it.
CUSTOMER_QUOTE = os.environ.get("CUSTOMER_QUOTE", "").strip()
CUSTOMER_QUOTE_ATTRIBUTION = os.environ.get("CUSTOMER_QUOTE_ATTRIBUTION", "").strip()


def title(view_key):
    """Browser title for a view, e.g. 'Taste Atlas — Audience Map'."""
    name = VIEW_NAMES.get(view_key)
    return "%s — %s" % (PRODUCT_NAME, name) if name else PRODUCT_NAME


def render(html):
    """Substitute the naming placeholders in a template.

    Templates carry __PRODUCT_NAME__ and __VIEW_*__ rather than literals, so a
    rename cannot leave one screen behind. The customer quote is JSON-encoded
    rather than pasted: it arrives from an environment variable, and a stray
    quote mark in it would otherwise break the page it appears on.
    """
    import json as _json
    out = html.replace("__PRODUCT_NAME__", PRODUCT_NAME)
    out = out.replace("__CUSTOMER_QUOTE__", _json.dumps(CUSTOMER_QUOTE))
    out = out.replace("__CUSTOMER_QUOTE_ATTRIBUTION__",
                      _json.dumps(CUSTOMER_QUOTE_ATTRIBUTION))
    out = out.replace("__REPO_URL__", REPO_URL)
    for key, name in VIEW_NAMES.items():
        out = out.replace("__VIEW_%s__" % key.upper(), name)
    return out
