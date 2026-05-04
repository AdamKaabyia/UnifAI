from directory.models import DirectoryUser, DirectoryGroup
from directory.provider import DirectoryProvider
from directory.config import LdapConfig


def __getattr__(name: str):
    """Lazy-load concrete adapters so that ``ldap3`` is only required
    by services that actually use them."""
    if name == "LdapDirectoryProvider":
        from directory.ldap_provider import LdapDirectoryProvider
        return LdapDirectoryProvider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "DirectoryUser",
    "DirectoryGroup",
    "DirectoryProvider",
    "LdapConfig",
    "LdapDirectoryProvider",
]
