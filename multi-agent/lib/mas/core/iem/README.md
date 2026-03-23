# SOLID Communication Protocol

A clean, professional communication system with clear separation of concerns for the multi-agent framework.

## 🎯 Design Principles

- **SOLID Architecture**: Clean separation of responsibilities
- **Domain Separation**: Core protocol is domain-agnostic  
- **Clear Boundaries**: Public vs Private vs Structured communication
- **Professional APIs**: Predictable, type-safe interfaces

## 📋 Communication Channels

### 🌐 **PUBLIC CONVERSATION** (End-User Facing)
- **`messages`**: Final conversation visible to users
- **`output`**: Final results and answers
- **Purpose**: Content that should be seen by end users

### 🔄 **STRUCTURED COMMUNICATION** (Inter-Node Coordination)
- **`inter_packets`**: IEM protocol packets for node coordination
- **Purpose**: Request/response/event patterns between nodes
- **Features**: Acknowledgment, correlation, middleware support
- **Clean & Simple**: No visibility complexity - all packets are equal

### 🔒 **PRIVATE WORKSPACE** (Node Internal State)
- **`chat_contexts`**: LLM conversation contexts (LLM nodes only)
- **Purpose**: Internal LLM conversation context management

## 🎯 **Channel Declaration Pattern**

### **Hierarchical Pattern (DRY & Clean)**
Channels are automatically inherited through the class hierarchy:

```python
class UserQuestionNode(BaseNode):
    # Only declare node-specific channels - base channels automatic!
    READS = {Channel.USER_PROMPT}
    WRITES = {Channel.MESSAGES}
    # 🎯 Total: {INTER_PACKETS, USER_PROMPT} + {INTER_PACKETS, MESSAGES}

class CustomAgentNode(LlmCapableMixin, BaseNode):
    # Only declare node-specific channels - base + mixin channels automatic!
    READS = {Channel.USER_PROMPT, Channel.MESSAGES}
    WRITES = {Channel.NODES_OUTPUT}
    # 🎯 Total: {INTER_PACKETS, CHAT_CONTEXTS, USER_PROMPT, MESSAGES} + {INTER_PACKETS, CHAT_CONTEXTS, NODES_OUTPUT}

class OrchestrationNode(BaseNode):
    # No extra channels needed - just inherits base channels
    READS = set()
    WRITES = set()
    # 🎯 Total: {INTER_PACKETS} + {INTER_PACKETS}
```

### **How It Works**
- **BaseNode** declares `BASE_READS`/`BASE_WRITES` = `{INTER_PACKETS}`
- **LlmCapableMixin** declares `MIXIN_READS`/`MIXIN_WRITES` = `{CHAT_CONTEXTS}`
- **Node classes** declare only their specific `READS`/`WRITES`
- **`total_reads()`/`total_writes()`** automatically collect from entire MRO

### **Benefits**
- ✅ **DRY**: No repetition - common channels declared once
- ✅ **Automatic**: Base + mixin channels included automatically
- ✅ **Clean**: Nodes only declare what's unique to them
- ✅ **Type-safe**: Full channel collection available for validation
- ✅ **Maintainable**: Change base channels in one place

## ✅ Key Benefits

- **Clear Separation**: Each channel has one specific purpose
- **Domain Agnostic**: Core IEM protocol has no domain-specific types
- **SOLID Compliance**: Clean interfaces and dependency inversion
- **Type Safety**: Structured packets with Pydantic validation
- **Professional**: Predictable, clean APIs

## Architecture

### Core Components

```
core/iem/
├── interfaces.py          # InterMessenger protocol & middleware interface
├── models.py              # ElementAddress, IEMError
├── packets.py             # IEMPacket hierarchy (Request/Response/Event)
├── messenger.py           # DefaultInterMessenger implementation
├── factory.py             # Factory functions for DI
├── exceptions.py          # IEM-specific exceptions
├── middleware/            # Cross-cutting concerns
│   ├── validation.py      # Action & payload validation
│   └── observability.py   # Logging & metrics
└── examples.py            # Usage examples
```

## 🎭 Usage Examples

### Simple Node (IEM Communication Only)
```python
class ProcessorNode(BaseNode):
    """Simple node that only uses structured communication."""
    
    def run(self, state: StateView) -> StateView:
        # Check for incoming events
        for packet in self.messenger.inbox({PacketKind.EVENT}):
            if packet.event_type == StandardEvents.PROCESSING_STARTED:
                # Do processing...
                result = self._process(packet.data)
                
                # Send structured response
                self.messenger.send_event(
                    to_uid=packet.src.uid,
                    event_type=StandardEvents.PROCESSING_COMPLETE,
                    data={"result": result}
                )
                
                self.messenger.acknowledge(packet.id)
        
        return state
```

### LLM Node (Conversation Context)
```python
class AgentNode(LlmCapableMixin, BaseNode):
    """LLM node with clean conversation management."""
    
    def run(self, state: StateView) -> StateView:
        # Handle IEM events
        for packet in self.messenger.inbox():
            if packet.event_type == StandardEvents.PROCESSING_STARTED:
                query = packet.data.get("query", "")
                
                # Add to LLM conversation context
                user_msg = ChatMessage(role=Role.USER, content=query)
                self.add_to_chat_context(user_msg)
                
                # Process with LLM using conversation context
                conversation = self.get_chat_context()
                response = self._chat(conversation)
                
                # Add response to context
                self.add_to_chat_context(response)
                
                # Send structured notification
                self.messenger.send_event(
                    to_uid=packet.src.uid,
                    event_type=StandardEvents.PROCESSING_COMPLETE,
                    data={"content": response.content}
                )
                
                self.messenger.acknowledge(packet.id)
        
        return state
```

### Output Node (Public Promotion)
```python
class FinalAnswerNode(BaseNode):
    """Node that promotes results to public conversation."""
    
    def run(self, state: StateView) -> StateView:
        # Collect results from other nodes via IEM
        results = []
        for packet in self.messenger.inbox():
            if packet.event_type == StandardEvents.PROCESSING_COMPLETE:
                results.append(packet.data.get("content", ""))
                self.messenger.acknowledge(packet.id)
        
        if results:
            # Synthesize final answer
            final_answer = self._synthesize(results)
            
            # Promote to public conversation
            self.promote_to_messages(final_answer)
        
        return state
```

### BaseNode Integration

All nodes automatically get:
- `self.ms` / `self.messenger`: IEM messenger instance
- `BASE_READS/BASE_WRITES`: Automatic IEM channel permissions
- Combined channel validation (base + node-specific)

## Usage Patterns

### 1. Basic Request/Response

```python
class ProcessorNode(BaseNode):
    def run(self, state: StateView) -> StateView:
        # Send request to adjacent node
        req_id = self.ms.send_request(
            to_uid="analyzer_node",
            action="analyze_sentiment", 
            args={"text": "Hello world"}
        )
        
        # Process responses
        for packet in self.ms.inbox(kinds={"response"}):
            if packet.correlation_id == req_id:
                result = packet.result
                self.ms.acknowledge(packet.id)
        
        return state
```

### 2. Event Broadcasting

```python
class OrchestratorNode(BaseNode):
    def run(self, state: StateView) -> StateView:
        # Broadcast event to all adjacent nodes
        for adjacent_uid in self._ctx.adjacent_nodes.keys():
            self.ms.send_event(
                to_uid=adjacent_uid,
                event_type="workflow_started",
                data={"workflow_id": "abc123"}
            )
        return state
```

### 3. Private Conversations

```python
class AnalysisNode(BaseNode):
    def run(self, state: StateView) -> StateView:
        # Maintain private LLM conversation
        self.ms.post_private(ChatMessage(
            role=Role.USER, 
            content="Analyze this data"
        ))
        
        # ... do LLM processing ...
        
        self.ms.post_private(assistant_response)
        
        # Explicitly promote final result to public
        self.ms.promote_public("Analysis complete: High confidence result")
        
        return state
```

### 4. With Enums and Middleware

```python
from core.iem import (
    LoggingMiddleware, ActionValidationMiddleware,
    PacketKind, PacketVisibility, StandardActions, StandardEvents
)

# Use type-safe enums for consistency
messenger.send_request(
    to_uid="analyzer",
    action=StandardActions.ANALYZE_TEXT,
    args={"text": "content"},
    visibility=PacketVisibility.PRIVATE
)

# Process with enum filtering
for packet in messenger.inbox(kinds={PacketKind.REQUEST, PacketKind.EVENT}):
    if packet.event_type == StandardEvents.PROCESSING_COMPLETE:
        # Handle completion
        pass

# Middleware setup
middleware = [
    LoggingMiddleware(),
    ActionValidationMiddleware({
        "analyzer": {StandardActions.ANALYZE_TEXT, StandardActions.SUMMARIZE},
        "retriever": {StandardActions.SEARCH, StandardActions.EMBED}
    })
]

messenger = create_messenger(
    state=state,
    identity=ElementAddress(uid="my_node"),
    middleware=middleware
)
```

## Type System

### Enums for Type Safety

```python
# Packet types
class PacketKind(str, Enum):
    REQUEST = "request"
    RESPONSE = "response" 
    EVENT = "event"

# Visibility levels
class PacketVisibility(str, Enum):
    PRIVATE = "private"
    PUBLIC = "public"

# Standard error codes
class ErrorCode(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    NOT_FOUND = "NOT_FOUND"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    ADJACENCY_ERROR = "ADJACENCY_ERROR"
    PROTOCOL_ERROR = "PROTOCOL_ERROR"

# Common actions for consistency
class StandardActions(str, Enum):
    PROCESS_USER_INPUT = "process_user_input"
    ANALYZE_TEXT = "analyze_text"
    SUMMARIZE = "summarize"
    SEARCH = "search"
    RETRIEVE = "retrieve"
    # ... more actions

# Common events for consistency  
class StandardEvents(str, Enum):
    PROCESSING_COMPLETE = "processing_complete"
    TASK_ASSIGNED = "task_assigned"
    TASK_COMPLETED = "task_completed"
    WORKFLOW_STARTED = "workflow_started"
    # ... more events
```

## Packet Types

### RequestPacket
- `kind`: PacketKind.REQUEST
- `action`: String action to invoke (use StandardActions when possible)
- `args`: Dict of action arguments  
- `timeout`: Optional request timeout
- `visibility`: PacketVisibility enum

### ResponsePacket
- `kind`: PacketKind.RESPONSE
- `correlation_id`: Links to original request
- `result`: Success result dict (XOR with error)
- `error`: IEMError object (XOR with result)
- `visibility`: PacketVisibility enum

### EventPacket
- `kind`: PacketKind.EVENT
- `event_type`: Type of event (use StandardEvents when possible)
- `data`: Event payload dict
- `visibility`: PacketVisibility enum
- No correlation - fire-and-forget

## Channel Merge Strategies

### `append_iem_packets`
- Appends new packets while avoiding duplicates by packet ID
- Maintains insertion order
- Handles both single packets and lists

### `merge_private_threads`  
- Merges thread dictionaries by element UID
- Appends messages to existing threads
- Creates new threads as needed
- Converts strings/dicts to ChatMessage objects

## Migration from nodes_output

The IEM protocol **eliminates the need for `nodes_output`**:

**Before:**
```python
state[Channel.NODES_OUTPUT] = {self.uid: result}
```

**After:**
```python
# Send to specific adjacent nodes
self.ms.send_event(to_uid, "processing_complete", {"content": result})

# Or promote to public conversation
self.ms.promote_public(result)
```

## Benefits

- **SOLID Compliance**: Clean separation of concerns, dependency inversion
- **Type Safety**: Structured packets with Pydantic v2 field validation
- **Observability**: Built-in correlation tracking and middleware hooks  
- **Flexibility**: Support for both sync (request/response) and async (events) patterns
- **Privacy**: Private conversations separate from public channel
- **Scalability**: Middleware for cross-cutting concerns without node coupling

## Examples

See `examples.py` for complete usage examples including:
- Basic messaging patterns
- Private conversation management  
- Middleware integration
- Event broadcasting
- Error handling
