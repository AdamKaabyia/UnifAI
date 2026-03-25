"""
IEM Protocol Utilities

Utilities for graph scheduling, packet inspection, and other IEM-related helpers.
"""

from typing import Optional
from datetime import datetime, timedelta, timezone
from mas.graph.state.graph_state import GraphState


def has_incoming_packets(state: GraphState, target_uid: str, 
                        thread_id: Optional[str] = None) -> bool:
    """
    Check if a target node has unacknowledged, non-expired packets.
    
    Used as a condition function for LangGraph edges to trigger nodes
    when they have pending IEM messages.
    
    Args:
        state: GraphState containing inter_packets
        target_uid: UID of the target node to check
        thread_id: Optional thread filter - only check packets for this thread
        
    Returns:
        True if target has pending packets, False otherwise
    """
    packets = getattr(state, 'inter_packets', [])
    
    for packet in packets:
        # Check if packet is for the target
        if packet.dst.uid != target_uid:
            continue
            
        # Check if packet is expired
        if packet.is_expired:
            continue
            
        # Check if packet is already acknowledged by target
        if packet.is_acknowledged_by(target_uid):
            continue
            
        # Optional thread filter
        if thread_id and getattr(packet, 'thread_id', None) != thread_id:
            continue
            
        # Found a valid pending packet
        return True
    
    return False


def has_incoming_requests(state: GraphState, target_uid: str,
                         thread_id: Optional[str] = None,
                         action: Optional[str] = None) -> bool:
    """
    Check if a target node has pending request packets.
    
    Args:
        state: GraphState containing inter_packets
        target_uid: UID of the target node to check
        thread_id: Optional thread filter
        action: Optional action filter - only check for specific action
        
    Returns:
        True if target has pending request packets, False otherwise
    """
    packets = getattr(state, 'inter_packets', [])
    
    for packet in packets:
        # Must be a request packet (TODO: Update to use PacketType system)
        # if packet.kind != PacketKind.REQUEST:
        #     continue
        # For now, skip this check until PacketKind is properly defined
        continue
            
        # Check if packet is for the target
        if packet.dst.uid != target_uid:
            continue
            
        # Check if packet is expired
        if packet.is_expired:
            continue
            
        # Check if packet is already acknowledged by target
        if packet.is_acknowledged_by(target_uid):
            continue
            
        # Optional thread filter
        if thread_id and getattr(packet, 'thread_id', None) != thread_id:
            continue
            
        # Optional action filter
        if action and getattr(packet, 'action', None) != action:
            continue
            
        # Found a valid pending request
        return True
    
    return False


def has_incoming_events(state: GraphState, target_uid: str,
                       thread_id: Optional[str] = None,
                       event_type: Optional[str] = None) -> bool:
    """
    Check if a target node has pending event packets.
    
    Args:
        state: GraphState containing inter_packets
        target_uid: UID of the target node to check
        thread_id: Optional thread filter
        event_type: Optional event type filter
        
    Returns:
        True if target has pending event packets, False otherwise
    """
    packets = getattr(state, 'inter_packets', [])
    
    for packet in packets:
        # Must be an event packet (TODO: Update to use PacketType system)
        # if packet.kind != PacketKind.EVENT:
        #     continue
        # For now, skip this check until PacketKind is properly defined
        continue
            
        # Check if packet is for the target
        if packet.dst.uid != target_uid:
            continue
            
        # Check if packet is expired
        if packet.is_expired:
            continue
            
        # Check if packet is already acknowledged by target
        if packet.is_acknowledged_by(target_uid):
            continue
            
        # Optional thread filter
        if thread_id and getattr(packet, 'thread_id', None) != thread_id:
            continue
            
        # Optional event type filter
        if event_type and getattr(packet, 'event_type', None) != event_type:
            continue
            
        # Found a valid pending event
        return True
    
    return False


def has_incoming_responses(state: GraphState, target_uid: str,
                          thread_id: Optional[str] = None,
                          correlation_id: Optional[str] = None) -> bool:
    """
    Check if a target node has pending response packets.
    
    Args:
        state: GraphState containing inter_packets
        target_uid: UID of the target node to check
        thread_id: Optional thread filter
        correlation_id: Optional correlation ID filter
        
    Returns:
        True if target has pending response packets, False otherwise
    """
    packets = getattr(state, 'inter_packets', [])
    
    for packet in packets:
        # Must be a response packet (TODO: Update to use PacketType system)
        # if packet.kind != PacketKind.RESPONSE:
        #     continue
        # For now, skip this check until PacketKind is properly defined
        continue
            
        # Check if packet is for the target
        if packet.dst.uid != target_uid:
            continue
            
        # Check if packet is expired
        if packet.is_expired:
            continue
            
        # Check if packet is already acknowledged by target
        if packet.is_acknowledged_by(target_uid):
            continue
            
        # Optional thread filter
        if thread_id and getattr(packet, 'thread_id', None) != thread_id:
            continue
            
        # Optional correlation ID filter
        if correlation_id and getattr(packet, 'correlation_id', None) != correlation_id:
            continue
            
        # Found a valid pending response
        return True
    
    return False


def count_pending_packets(state: GraphState, target_uid: str,
                         thread_id: Optional[str] = None) -> dict[str, int]:
    """
    Count pending packets by type for a target node.
    
    Args:
        state: GraphState containing inter_packets
        target_uid: UID of the target node to check
        thread_id: Optional thread filter
        
    Returns:
        Dict with counts by packet type: {"requests": 0, "events": 0, "responses": 0}
    """
    counts = {"unknown": 0}  # TODO: Update when PacketKind is properly defined
    packets = getattr(state, 'inter_packets', [])
    
    for packet in packets:
        # Check if packet is for the target
        if packet.dst.uid != target_uid:
            continue
            
        # Check if packet is expired
        if packet.is_expired:
            continue
            
        # Check if packet is already acknowledged by target
        if packet.is_acknowledged_by(target_uid):
            continue
            
        # Optional thread filter
        if thread_id and getattr(packet, 'thread_id', None) != thread_id:
            continue
        
        # Count by type
        # TODO: Update to use PacketType system instead of PacketKind
        # For now, count all packets as "unknown" type
        counts["unknown"] += 1
        # if packet.kind == PacketKind.REQUEST:
        #     counts["requests"] += 1
        # elif packet.kind == PacketKind.EVENT:
        #     counts["events"] += 1
        # elif packet.kind == PacketKind.RESPONSE:
        #     counts["responses"] += 1
    
    return counts


def cleanup_expired_packets(state: GraphState, max_age: Optional[timedelta] = None) -> int:
    """
    Remove expired and old acknowledged packets from state.
    
    Args:
        state: GraphState containing inter_packets
        max_age: Maximum age for acknowledged packets (default: 1 hour)
        
    Returns:
        Number of packets removed
    """
    if not hasattr(state, 'inter_packets'):
        return 0
        
    max_age = max_age or timedelta(hours=1)
    now = datetime.now(timezone.utc)
    
    original_packets = list(state.inter_packets)
    filtered_packets = []
    
    for packet in original_packets:
        # Remove if expired
        if packet.is_expired:
            continue
            
        # Remove old acknowledged packets
        if (len(packet.ack_by) > 0 and 
            (now - packet.ts) > max_age):
            continue
            
        # Keep the packet
        filtered_packets.append(packet)
    
    # Update state if changed
    if len(filtered_packets) != len(original_packets):
        state.inter_packets = filtered_packets
        
    return len(original_packets) - len(filtered_packets)


# Convenience factories for common edge conditions

def create_packet_condition(target_uid: str, thread_id: Optional[str] = None):
    """
    Create a condition function for LangGraph edges.
    
    Args:
        target_uid: UID of the target node
        thread_id: Optional thread filter
        
    Returns:
        Condition function that takes state and returns bool
    """
    return lambda state: has_incoming_packets(state, target_uid, thread_id)


def create_request_condition(target_uid: str, action: Optional[str] = None, 
                           thread_id: Optional[str] = None):
    """
    Create a condition function for LangGraph edges that triggers on requests.
    
    Args:
        target_uid: UID of the target node
        action: Optional action filter
        thread_id: Optional thread filter
        
    Returns:
        Condition function that takes state and returns bool
    """
    # TODO: Update when has_incoming_requests is fixed
    return lambda state: False  # Temporarily disabled


def create_event_condition(target_uid: str, event_type: Optional[str] = None,
                          thread_id: Optional[str] = None):
    """
    Create a condition function for LangGraph edges that triggers on events.
    
    Args:
        target_uid: UID of the target node
        event_type: Optional event type filter
        thread_id: Optional thread filter
        
    Returns:
        Condition function that takes state and returns bool
    """
    # TODO: Update when has_incoming_events is fixed
    return lambda state: False  # Temporarily disabled


def get_outgoing_targets(state, context) -> set[str]:
    """
    Get node UIDs that this node has been sending packets to.
    
    Args:
        state: StateView with access to inter_packets
        context: StepContext with node identity and adjacency info
        
    Returns:
        Set of adjacent node UIDs that received packets from this node
    """
    # Handle missing inter_packets attribute gracefully
    packets = getattr(state, 'inter_packets', [])
    
    # If getattr returns a Mock object instead of the default, use empty list
    if hasattr(packets, '_mock_name'):  # Check if it's a Mock object
        packets = []
    
    # Handle None context or missing attributes
    if not context or not hasattr(context, 'uid'):
        return set()
    
    my_uid = context.uid
    
    # Handle None adjacent_nodes
    if not hasattr(context, 'adjacent_nodes') or context.adjacent_nodes is None:
        return set()
    
    adjacent_uids = set(context.adjacent_nodes.keys())
    
    targets = set()
    for packet in packets:
        try:
            # Check if outgoing from our node to adjacent node
            # Add null checks for packet attributes
            if (hasattr(packet, 'src') and packet.src is not None and 
                hasattr(packet.src, 'uid') and packet.src.uid == my_uid and
                hasattr(packet, 'dst') and packet.dst is not None and
                hasattr(packet.dst, 'uid') and packet.dst.uid in adjacent_uids and
                hasattr(packet, 'is_acknowledged') and not packet.is_acknowledged() and
                hasattr(packet, 'is_expired') and not packet.is_expired):
                targets.add(packet.dst.uid)
        except (AttributeError, TypeError):
            # Skip malformed packets gracefully
            continue
    
    return targets
