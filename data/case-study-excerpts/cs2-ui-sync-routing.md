# Case Study 2: UI Sync Routing -- Captured Experience as Reusable Knowledge

This excerpt demonstrates the creation of `ui-sync-patterns.md`, a Tier 3 knowledge document that codifies routing topology decisions for networked UI synchronization. The document distills implementation experience into a reusable decision framework with three routing topologies, delivery mode guidance, and concrete message examples.

**Architectural tiers demonstrated**: Tier 3 (knowledge base creation and reuse)

**Session context**: January-February 2026. The "Before" session involved ad-hoc implementation of shop UI sync. The "After" session created `ui-sync-patterns.md` during radial dial implementation, capturing the routing topology patterns for future reuse.

## Key Interaction 1: Human Questions the Architecture's Novelty

> **Human**:
> are you serious that nobody has done context-as-infrastructure? To me it seems like common sense that this is how you should build agentic coding frameworks for large projects

> **Assistant**:
> You're right to push back. Let me be more precise.
>
> **What IS common/documented already:**
> - RAG (retrieval-augmented generation) -- well-established pattern
> - CLAUDE.md / .cursorrules / system prompts -- everyone does this now
> - Multi-agent frameworks (CrewAI, AutoGen, LangGraph) -- lots of papers
> [...]
>
> **What's in the gray zone (practitioners doing it, not formalized):**
> - People building large CLAUDE.md files -- increasingly common as of early 2026
> - People creating context documents for AI consumption -- happening but undocumented
> [...]

## Key Interaction 2: The Case Study in the Whitepaper

> **Human** (provides selected text from whitepaper draft):
> Case Study 3: Cross-Cutting Feature with Multi-Tier Support
>
> **Context:** Adding networked UI synchronization for a radial dial interface (used for item management) required modifications across four subsystems: Entity Component System (new components), networking (new message types with dual delivery modes), UI rendering (overlay management), and input handling (controller support).
>
> **Architecture tiers involved:**
> - *Constitution (Tier 1):* The three-branch network code pattern (offline/host/client) ensured all three play modes were handled
> - *Agents (Tier 2):* `network-protocol-designer` reviewed the message type design; `ui-and-ux-agent` reviewed the overlay implementation
> - *Knowledge base (Tier 3):* A specification document (`ui-sync-patterns.md`) documented three routing topologies (hub-relay, direct-broadcast, client-to-host-only) with guidance on when to use each
>
> **Interpretation:** This case illustrates the architecture functioning as a whole: the constitution ensured the standard network branching pattern was followed, the knowledge base provided the specific routing topology guidance needed for this feature class, and specialized agents reviewed domain-specific correctness.

## Key Interaction 3: The Document Itself (ui-sync-patterns.md, excerpt)

The captured experience document provides a decision framework, not just reference tables:

> ```markdown
> # UI Sync Patterns
>
> How UI state is synchronized across networked clients. Use this guide when
> adding new menus, overlays, or interactive UI that needs to be visible to
> remote players.
>
> ## Three Routing Topologies
>
> ### 1. Hub-Relay (Client -> Host -> BroadcastToAll)
> Host validates and relays. Used when the state transition has gameplay implications.
>
> | Message | ID | Description |
> | HeroSelectedMessage | 23 | Hero class selection in lobby |
> | PlayerReadyMessage | 24 | Ready toggle in lobby |
> [...]
>
> ### 2. Direct-Broadcast (Any Peer -> BroadcastToAll)
> No host validation. Used for cosmetic-only UI state.
>
> | Message | ID | Delivery | Description |
> | ShopFocusChanged | 45 | UnreliableSequenced | Cursor position in shop |
> | RadialDialSyncMessage | 39 | Dual (see below) | Radial dial open/select/close |
> [...]
>
> ## Delivery Mode Decision Tree
> Is it a critical state transition (open/close/confirm/purchase)?
>   YES -> ReliableOrdered
>   NO -> Is it a frequent cursor/selection update?
>     YES -> UnreliableSequenced (only latest matters)
>     NO -> ReliableOrdered (default safe choice)
> ```

## Annotation

This case study illustrates "captured experience" -- a development pattern where knowledge gained from implementing one feature is codified into a reusable document for future features. The `ui-sync-patterns.md` document was created after the radial dial UI sync was implemented, distilling the routing topology decisions, delivery mode choices, and the three-branch code pattern into a reference that any future session could consult without re-deriving these decisions.

The document's structure is notable: it provides a decision tree (not just reference tables) that guides the AI through the routing topology selection process. The three topologies (hub-relay, direct-broadcast, client-to-host-only) represent recurring architectural patterns that apply to any new networked UI feature. By encoding the "when to use each" guidance alongside concrete message examples, the document serves as both specification and tutorial. Without this document, each new networked UI feature would require the developer to re-explain the routing topology options and their tradeoffs -- knowledge that would otherwise exist only in prior conversation history that may have been context-compressed or lost between sessions.
