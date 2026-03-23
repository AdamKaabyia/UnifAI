"""
Default IEM Messenger Implementation

Clean, generic packet handling with middleware support.
"""

from typing import Callable, Optional, Any, List
from datetime import timedelta, datetime, timezone
import uuid
from mas.graph.state.state_view import StateView
from mas.graph.state.graph_state import Channel
from mas.graph.models import StepContext
from .interfaces import InterMessenger, MessengerMiddleware
from .packets import BaseIEMPacket
from .models import ElementAddress, PacketType
from .exceptions import IEMException, IEMAdjacencyException, IEMValidationException


class DefaultInterMessenger(InterMessenger):
    """
    Default implementation of InterMessenger.
    
    Features:
    - Generic packet handling (any packet type)
    - Optional adjacency enforcement
    - Middleware support for cross-cutting concerns
    - Automatic packet filtering and TTL handling
    """

    def __init__(
            self,
            state: StateView,
            identity: ElementAddress,
            *,
            is_adjacent: Optional[Callable[[str], bool]] = None,
            middleware: List[MessengerMiddleware] = None,
            max_packet_age: timedelta = timedelta(hours=24),
            context: Optional[StepContext] = None
    ):
        """
        Initialize messenger.
        
        Args:
            state: StateView for reading/writing channels
            identity: Address of this element
            is_adjacent: Function to check if UID is adjacent (None = no enforcement)
            middleware: List of middleware to apply
            max_packet_age: Maximum age for packets before they're considered expired
            context: StepContext for adjacency info (used for broadcast)
        """
        self._state = state
        self._me = identity
        self._is_adjacent = is_adjacent
        self._middleware = middleware or []
        self._max_packet_age = max_packet_age
        self._ctx = context

    def _apply_middleware_send(self, packet: BaseIEMPacket) -> BaseIEMPacket:
        """Apply before_send middleware in order."""
        for mw in self._middleware:
            packet = mw.before_send(packet)
        return packet

    def _apply_middleware_receive(self, packet: BaseIEMPacket) -> BaseIEMPacket:
        """Apply after_receive middleware in order."""
        for mw in self._middleware:
            packet = mw.after_receive(packet)
        return packet

    def _validate_send(self, to_uid: str) -> None:
        """Validate that send is allowed to target UID."""
        if self._is_adjacent and not self._is_adjacent(to_uid):
            raise IEMAdjacencyException(f"Non-adjacent send denied: {to_uid}")

    def _append_packet(self, packet: BaseIEMPacket) -> None:
        """Apply middleware and append packet to state."""
        try:
            packet = self._apply_middleware_send(packet)
            # Get current packets and append new one
            current_packets = list(self._state.get(Channel.INTER_PACKETS, []))
            current_packets.append(packet)
            self._state[Channel.INTER_PACKETS] = current_packets
        except Exception as e:
            if isinstance(e, IEMException):
                raise
            raise IEMValidationException(f"Failed to send packet: {e}") from e

    def send_packet(self, packet: BaseIEMPacket) -> str:
        """
        Send any packet via IEM.
        
        Validates adjacency (if enforced) and applies middleware.
        """
        self._validate_send(packet.dst.uid)
        self._append_packet(packet)
        return packet.id

    def inbox_packets(self, packet_type: PacketType = None) -> List[BaseIEMPacket]:
        """
        Get unacknowledged packets addressed to this element.
        
        Filters by packet type and applies middleware.
        """
        packets = self._state.get(Channel.INTER_PACKETS, [])

        # Filter: addressed to me, right type, not acked, not expired
        filtered = []
        for p in packets:
            if (p.dst.uid == self._me.uid and
                    (packet_type is None or p.type == packet_type) and
                    not p.is_acknowledged_by(self._me.uid) and
                    not p.is_expired):
                try:
                    filtered_packet = self._apply_middleware_receive(p)
                    filtered.append(filtered_packet)
                except IEMException:
                    # Middleware rejected packet, skip it
                    continue

        return filtered

    def acknowledge(self, packet_id: str) -> bool:
        """Mark a packet as acknowledged."""
        packets = list(self._state.get(Channel.INTER_PACKETS, []))
        for p in packets:
            if p.id == packet_id:
                p.acknowledge(self._me.uid)
                self._state[Channel.INTER_PACKETS] = packets
                return True
        return False

    def purge(self, *, max_age: timedelta = None, acked_only: bool = True) -> int:
        """Remove old/acknowledged packets from the state."""
        packets = list(self._state.get(Channel.INTER_PACKETS, []))
        initial_count = len(packets)

        now = datetime.now(timezone.utc)
        max_age = max_age or self._max_packet_age

        filtered = []
        for p in packets:
            # Check if should be purged
            should_purge = False

            if acked_only and p.is_acknowledged_by(self._me.uid):
                should_purge = True
            elif not acked_only and (p.is_expired or
                                     (max_age and (now - p.ts) > max_age)):
                should_purge = True

            if not should_purge:
                filtered.append(p)

        if len(filtered) != initial_count:
            self._state[Channel.INTER_PACKETS] = filtered

        return initial_count - len(filtered)

    # === CONVENIENCE METHODS ===
    def get_adjacent_nodes(self) -> List[str]:
        """
        Get list of adjacent node UIDs.
        
        Returns:
            List of adjacent node UIDs, or empty list if no context
        """
        if not self._ctx or not self._ctx.adjacent_nodes:
            return []
        return list(self._ctx.adjacent_nodes.keys())

    def broadcast_packet(self, packet: BaseIEMPacket) -> List[str]:
        """
        Broadcast packet to all adjacent nodes.
        
        Args:
            packet: Packet to broadcast (dst will be overridden)
            
        Returns:
            List of packet IDs sent
        """
        return self.multicast_packet(packet, self.get_adjacent_nodes())

    def multicast_packet(self, packet: BaseIEMPacket, target_uids: List[str]) -> List[str]:
        """
        Send packet to multiple specific nodes.
        
        Args:
            packet: Packet to send (dst will be overridden for each target)
            target_uids: List of target node UIDs
            
        Returns:
            List of packet IDs sent
        """
        packet_ids = []

        for node_uid in target_uids:
            try:
                # Create copy with unique ID and set destination
                multicast_packet = packet.model_copy(deep=True)
                multicast_packet.id = str(uuid.uuid4())  # Generate new unique ID
                multicast_packet.dst = ElementAddress(uid=node_uid)
                packet_id = self.send_packet(multicast_packet)
                packet_ids.append(packet_id)
            except Exception:
                # Continue sending to other nodes even if one fails
                continue

        return packet_ids
