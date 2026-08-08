"""xscreen -- on-premise U.S. export-control restricted-party screening.

Deterministic extraction and matching, model-assisted adjudication, and an
independent critic loop before anything is called clear.

Public surface:

    from xscreen import pipeline, fetch, match, rules, report

Everything runs on the Python standard library. There is no network call
outside `fetch`, and no data leaves the host unless a remote model backend is
explicitly configured.
"""

from .models import SCHEMA_VERSION

__version__ = SCHEMA_VERSION
__all__ = ["SCHEMA_VERSION", "__version__"]
