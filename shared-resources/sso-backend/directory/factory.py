"""
Directory provider factory.

Selects the concrete directory adapter based on the application config.
New backends (Azure AD, etc.) are added here as additional branches.
"""
import logging
from typing import Optional

from directory.provider import DirectoryProvider

logger = logging.getLogger(__name__)

_SUPPORTED_PROVIDERS = {"ldap"}


def build_directory_provider(cfg) -> Optional[DirectoryProvider]:
    """Build the directory provider specified by *cfg.directory_provider*."""
    provider_name = cfg.directory_provider.strip().lower()
    if not provider_name:
        return None

    if provider_name not in _SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Unknown directory_provider: '{provider_name}'. "
            f"Supported: {', '.join(sorted(_SUPPORTED_PROVIDERS))}"
        )

    if provider_name == "ldap":
        return _build_ldap(cfg)

    return None


def _build_ldap(cfg) -> DirectoryProvider:
    from directory import LdapDirectoryProvider, LdapConfig

    if not cfg.directory_url:
        raise ValueError("directory_url is required when directory_provider='ldap'")
    if not cfg.directory_ldap_user_base_dn:
        raise ValueError(
            "directory_ldap_user_base_dn is required when directory_provider='ldap'"
        )

    ldap_cfg = LdapConfig(
        url=cfg.directory_url,
        user_base_dn=cfg.directory_ldap_user_base_dn,
        bind_dn=cfg.directory_ldap_bind_dn,
        bind_password=cfg.directory_ldap_bind_password,
        skip_tls_verify=not cfg.directory_verify_ssl,
        timeout_seconds=cfg.directory_timeout,
        group_base_dn=cfg.directory_ldap_group_base_dn,
        group_object_class=cfg.directory_ldap_group_object_class,
        attr_group_member=cfg.directory_ldap_group_member_attr,
    )
    logger.info("Directory provider: ldap (%s)", cfg.directory_url)
    return LdapDirectoryProvider(config=ldap_cfg)
