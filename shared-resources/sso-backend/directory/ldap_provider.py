"""
LDAP adapter for DirectoryProvider.

Queries the corporate LDAP directory for user and group information.
Requires the ``ldap3`` package.
"""
import logging
from typing import List, Optional

import ldap3
from ldap3 import Server, ServerPool, Connection, SUBTREE, ROUND_ROBIN
from ldap3.core.exceptions import LDAPException

from directory.models import DirectoryUser, DirectoryGroup
from directory.provider import DirectoryProvider
from directory.config import LdapConfig

logger = logging.getLogger(__name__)


class LdapDirectoryProvider(DirectoryProvider):
    def __init__(self, config: LdapConfig):
        self._cfg = config
        self._user_base = config.user_base_dn
        self._user_attrs = [
            config.attr_uid, config.attr_cn, config.attr_mail, config.attr_title,
        ]

        self._group_base = config.group_base_dn or None
        self._group_attrs = [
            config.attr_group_cn,
            config.attr_group_description,
            config.attr_group_member,
        ]

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

        logger.info(
            "LDAP provider: %s, user_base=%s, group_base=%s, bind=%s",
            config.url, self._user_base,
            self._group_base or "(disabled)",
            self._bind_dn or "anonymous",
        )

    def _connect(self) -> Connection:
        return Connection(
            self._pool,
            user=self._bind_dn,
            password=self._bind_pw,
            auto_bind=True,
            read_only=True,
            receive_timeout=self._timeout,
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
                results = [
                    entry for entry in conn.entries
                    if str(entry.entry_dn) != base_dn
                ]
                logger.debug(
                    "LDAP search base=%s filter=%s → %d result(s)",
                    base_dn, search_filter, len(results),
                )
                return results
            finally:
                conn.unbind()
        except LDAPException:
            logger.exception(
                "LDAP search failed: base=%s filter=%s", base_dn, search_filter,
            )
            return []

    @staticmethod
    def _escape(value: str) -> str:
        return ldap3.utils.conv.escape_filter_chars(value)

    # ── user helpers ───────────────────────────────────────────────────

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
        uid, cn, mail = self._cfg.attr_uid, self._cfg.attr_cn, self._cfg.attr_mail
        search_filter = (
            f"(&(objectClass={self._cfg.user_object_class})"
            f"(|({uid}=*{q}*)({cn}=*{q}*)({mail}=*{q}*)))"
        )
        entries = self._search(self._user_base, search_filter,
                               self._user_attrs, limit=limit)
        return [self._entry_to_user(e) for e in entries]

    def get_user(self, user_id: str) -> Optional[DirectoryUser]:
        q = self._escape(user_id)
        search_filter = (
            f"(&(objectClass={self._cfg.user_object_class})"
            f"({self._cfg.attr_uid}={q}))"
        )
        entries = self._search(self._user_base, search_filter,
                               self._user_attrs, limit=1)
        if not entries:
            return None
        return self._entry_to_user(entries[0])

    # ── group helpers ──────────────────────────────────────────────────

    def _entry_to_group(self, entry) -> DirectoryGroup:
        attrs = entry.entry_attributes_as_dict
        cn = _first(attrs.get(self._cfg.attr_group_cn, []))
        description = _first(attrs.get(self._cfg.attr_group_description, []))
        raw_members = attrs.get(self._cfg.attr_group_member, [])
        members = [_dn_to_uid(str(m)) for m in raw_members if m]

        return DirectoryGroup(
            group_id=cn or "",
            name=cn or "",
            description=description or "",
            members=members,
        )

    def _object_class_filter(self) -> str:
        """Build objectClass filter supporting comma-separated values."""
        classes = [c.strip() for c in self._cfg.group_object_class.split(",") if c.strip()]
        if len(classes) == 1:
            return f"(objectClass={classes[0]})"
        return "(|" + "".join(f"(objectClass={c})" for c in classes) + ")"

    def search_groups(self, query: str, limit: int = 20) -> List[DirectoryGroup]:
        if not self._group_base:
            return []
        q = self._escape(query)
        cn = self._cfg.attr_group_cn
        oc_filter = self._object_class_filter()
        search_filter = f"(&{oc_filter}({cn}=*{q}*))"
        logger.info(
            "LDAP group search: base=%s filter=%s",
            self._group_base, search_filter,
        )
        entries = self._search(self._group_base, search_filter,
                               self._group_attrs, limit=limit)
        return [self._entry_to_group(e) for e in entries]

    def get_group(self, group_id: str) -> Optional[DirectoryGroup]:
        if not self._group_base:
            return None
        q = self._escape(group_id)
        oc_filter = self._object_class_filter()
        search_filter = f"(&{oc_filter}({self._cfg.attr_group_cn}={q}))"
        entries = self._search(self._group_base, search_filter,
                               self._group_attrs, limit=1)
        if not entries:
            return None
        return self._entry_to_group(entries[0])


def _first(values: list) -> str:
    if values:
        return str(values[0])
    return ""


def _dn_to_uid(dn: str) -> str:
    """Extract the first RDN value from a DN, e.g. 'uid=jdoe,ou=users,...' -> 'jdoe'."""
    if "=" not in dn:
        return dn
    return dn.split(",")[0].split("=", 1)[1]
