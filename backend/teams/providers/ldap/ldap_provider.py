"""
LDAP adapter for TeamDirectoryProvider.

Queries the corporate LDAP directory for user information.  No other
module should import from this package directly — only the composition
root (app_container) references it.
"""
import logging
from typing import List, Optional

import ldap3
from ldap3 import Server, ServerPool, Connection, SUBTREE, ROUND_ROBIN
from ldap3.core.exceptions import LDAPException

from teams.models import DirectoryUser
from teams.providers.provider import TeamDirectoryProvider
from teams.providers.ldap.config import LdapConfig

logger = logging.getLogger(__name__)

_USER_ATTRS = ["uid", "cn", "mail", "title"]


class LdapDirectoryProvider(TeamDirectoryProvider):
    def __init__(self, config: LdapConfig):
        self._cfg = config
        self._user_base = config.user_base_dn

        tls = None
        if config.url.startswith("ldaps"):
            tls = ldap3.Tls(validate=0 if config.skip_tls_verify else 2)

        urls = [u.strip() for u in config.url.split(",") if u.strip()]
        servers = [
            Server(u, use_ssl=u.startswith("ldaps"), tls=tls,
                   connect_timeout=config.timeout_seconds)
            for u in urls
        ]
        self._pool = ServerPool(servers, ROUND_ROBIN, active=True)

        self._bind_dn = config.bind_dn or None
        self._bind_pw = config.bind_password or None
        self._timeout = config.timeout_seconds
        self._pool_size = config.pool_size

        logger.info(
            "LDAP provider: %s, user_base=%s, bind=%s",
            config.url, self._user_base, self._bind_dn or "anonymous",
        )

    def _connect(self) -> Connection:
        return Connection(
            self._pool,
            user=self._bind_dn,
            password=self._bind_pw,
            auto_bind=True,
            read_only=True,
            receive_timeout=self._timeout,
            pool_size=self._pool_size,
        )

    def _search(self, base_dn: str, search_filter: str,
                attributes: list, limit: int = 0) -> list:
        try:
            conn = self._connect()
            try:
                conn.search(
                    search_base=base_dn,
                    search_filter=search_filter,
                    search_scope=SUBTREE,
                    attributes=attributes,
                    size_limit=limit,
                )
                return [
                    entry for entry in conn.entries
                    if str(entry.entry_dn) != base_dn
                ]
            finally:
                conn.unbind()
        except LDAPException:
            logger.exception("LDAP search failed: %s", search_filter)
            return []

    @staticmethod
    def _escape(value: str) -> str:
        return ldap3.utils.conv.escape_filter_chars(value)

    def _entry_to_user(self, entry) -> DirectoryUser:
        attrs = entry.entry_attributes_as_dict
        uid = _first(attrs.get(self._cfg.attr_uid, []))
        cn = _first(attrs.get(self._cfg.attr_cn, []))
        mail = _first(attrs.get(self._cfg.attr_mail, []))
        title = _first(attrs.get(self._cfg.attr_title, []))

        return DirectoryUser(
            user_id=uid or cn or "",
            username=uid or "",
            display_name=cn or uid or "",
            email=mail or "",
            title=title or "",
        )

    def search_users(self, query: str, limit: int = 20) -> List[DirectoryUser]:
        q = self._escape(query)
        search_filter = (
            f"(&(objectClass={self._cfg.user_object_class})"
            f"(|(uid=*{q}*)(cn=*{q}*)(mail=*{q}*)))"
        )
        entries = self._search(self._user_base, search_filter,
                               _USER_ATTRS, limit=limit)
        return [self._entry_to_user(e) for e in entries]

    def get_user(self, user_id: str) -> Optional[DirectoryUser]:
        q = self._escape(user_id)
        search_filter = (
            f"(&(objectClass={self._cfg.user_object_class})"
            f"(uid={q}))"
        )
        entries = self._search(self._user_base, search_filter,
                               _USER_ATTRS, limit=1)
        if not entries:
            return None
        return self._entry_to_user(entries[0])


def _first(values: list) -> str:
    if values:
        return str(values[0])
    return ""
