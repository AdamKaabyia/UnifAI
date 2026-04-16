"""
Auth layer — protocol-agnostic authentication infrastructure.

Subpackages:
  credentials/   — token storage, retrieval, refresh, presentation
  discovery/     — detect what auth a server requires
  protocols/     — concrete protocol implementations (oauth2, ...)

Consumers depend only on :class:`credentials.AuthCredential`.
"""
