#!/bin/bash
# Architecture Integrity Validator
# Checks that CLAUDE.md, MCP server.py, context docs, and agents all cross-reference correctly.
# Run: bash .claude/scripts/validate-architecture.sh

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CONTEXT_DIR="$ROOT/.claude/context"
AGENTS_DIR="$ROOT/.claude/agents"
CLAUDE_MD="$ROOT/CLAUDE.md"
MCP_SERVER="$ROOT/MCP/context7_mcp/server.py"

ERRORS=0
WARNINGS=0

red()    { printf "\033[31m%s\033[0m\n" "$1"; }
yellow() { printf "\033[33m%s\033[0m\n" "$1"; }
green()  { printf "\033[32m%s\033[0m\n" "$1"; }
bold()   { printf "\033[1m%s\033[0m\n" "$1"; }

# Use temp files to count errors from subshells
ERR_FILE=$(mktemp)
WARN_FILE=$(mktemp)
echo "0" > "$ERR_FILE"
echo "0" > "$WARN_FILE"
trap "rm -f '$ERR_FILE' '$WARN_FILE'" EXIT

inc_error() {
    red "  ERROR: $1"
    echo $(( $(cat "$ERR_FILE") + 1 )) > "$ERR_FILE"
}

inc_warn() {
    yellow "  WARN:  $1"
    echo $(( $(cat "$WARN_FILE") + 1 )) > "$WARN_FILE"
}

# ─── Check 1: CLAUDE.md context doc references ───────────────────────────────
bold "1. CLAUDE.md → context doc references"

# Extract .claude/context/*.md references
refs=$(grep -oE '\.claude/context/[a-zA-Z0-9_-]+\.md' "$CLAUDE_MD" 2>/dev/null | sort -u || true)
for doc in $refs; do
    if [ ! -f "$ROOT/$doc" ]; then
        inc_error "CLAUDE.md references '$doc' but file does not exist"
    fi
done

# Check backtick-quoted doc names that appear as context references
quoted_docs=$(grep -oE '`[a-zA-Z0-9_-]+\.md`' "$CLAUDE_MD" 2>/dev/null | tr -d '`' | sort -u || true)
for docname in $quoted_docs; do
    case "$docname" in
        CLAUDE.md|AGENT.md|CHANGELOG.md|DEVLOG.md|MEMORY.md|README.md|TODO.md) continue ;;
    esac
    if grep -qE "(context/$docname|See.*$docname)" "$CLAUDE_MD" 2>/dev/null; then
        if [ ! -f "$CONTEXT_DIR/$docname" ]; then
            inc_error "CLAUDE.md references context doc '$docname' but .claude/context/$docname does not exist"
        fi
    fi
done

green "  OK:    CLAUDE.md context references checked"

# ─── Check 2: CLAUDE.md agent references ─────────────────────────────────────
bold "2. CLAUDE.md → agent references"

KNOWN_AGENTS="code-simplifier coordinate-wizard ecs-component-designer sprite-2d-artist model-3d-artist audio-designer dungeon-tester network-protocol-designer ability-designer shader-wizard ldtk-validator ui-and-ux-agent level-designer game-design-brainstorm systems-designer code-reviewer-game-dev debugger manuscript-reviewer"

for name in $KNOWN_AGENTS; do
    if grep -q "\`$name\`" "$CLAUDE_MD" 2>/dev/null; then
        if [ ! -f "$AGENTS_DIR/$name/AGENT.md" ]; then
            inc_error "CLAUDE.md references agent '$name' but $AGENTS_DIR/$name/AGENT.md does not exist"
        fi
    fi
done

green "  OK:    CLAUDE.md agent references checked"

# ─── Check 3: MCP server.py context doc references ───────────────────────────
bold "3. MCP server.py → context doc references"

mcp_docs=$(grep -oE '"[a-zA-Z0-9_-]+\.md"' "$MCP_SERVER" 2>/dev/null | tr -d '"' | sort -u || true)
for docname in $mcp_docs; do
    case "$docname" in
        AGENT.md|CLAUDE.md|Plan.md|server.py) continue ;;
    esac
    if [ ! -f "$CONTEXT_DIR/$docname" ]; then
        inc_error "MCP server.py references '$docname' but .claude/context/$docname does not exist"
    fi
done

green "  OK:    MCP server.py context doc references checked"

# ─── Check 4: MCP server.py agent references ─────────────────────────────────
bold "4. MCP server.py → agent references"

# Extract agent names from the AGENTS dict only (after "AGENTS = {" line)
# Use sed to extract the AGENTS section, then grep for dict keys with "triggers"
agents_section=$(sed -n '/^AGENTS = {/,/^}/p' "$MCP_SERVER" 2>/dev/null || true)
mcp_agents=$(echo "$agents_section" | grep -oE '"[a-z][-a-z0-9]*"\s*:' | grep -oE '"[^"]*"' | tr -d '"' | sort -u || true)
for name in $mcp_agents; do
    # Skip keys that are sub-dict fields (description, model, triggers, name)
    case "$name" in
        name|description|model|triggers) continue ;;
    esac
    if [ ! -f "$AGENTS_DIR/$name/AGENT.md" ]; then
        inc_error "MCP server.py AGENTS dict has '$name' but $AGENTS_DIR/$name/AGENT.md does not exist"
    fi
done

green "  OK:    MCP server.py agent references checked"

# ─── Check 5: Context doc cross-references ────────────────────────────────────
bold "5. Context doc → context doc cross-references"

for doc in "$CONTEXT_DIR"/*.md; do
    docbase=$(basename "$doc")
    cross_refs=$(grep -oE '[a-zA-Z0-9_-]+\.md' "$doc" 2>/dev/null | sort -u || true)
    for ref in $cross_refs; do
        [ "$ref" = "$docbase" ] && continue
        case "$ref" in
            CLAUDE.md|AGENT.md|CHANGELOG.md|DEVLOG.md|MEMORY.md|README.md|TODO.md|Plan.md|server.py) continue ;;
        esac
        if [ ! -f "$CONTEXT_DIR/$ref" ]; then
            inc_warn "$docbase references '$ref' but .claude/context/$ref does not exist"
        fi
    done
done

green "  OK:    Context doc cross-references checked"

# ─── Check 6: Orphan detection ────────────────────────────────────────────────
bold "6. Orphaned context docs (not referenced by CLAUDE.md or MCP server.py)"

for doc in "$CONTEXT_DIR"/*.md; do
    docname=$(basename "$doc")
    in_claude=$(grep -c "$docname" "$CLAUDE_MD" 2>/dev/null | head -1 || echo "0")
    in_mcp=$(grep -c "$docname" "$MCP_SERVER" 2>/dev/null | head -1 || echo "0")
    if [ "$in_claude" -eq 0 ] && [ "$in_mcp" -eq 0 ]; then
        inc_warn "Context doc '$docname' is not referenced by CLAUDE.md or MCP server.py"
    fi
done

green "  OK:    Orphan detection checked"

# ─── Check 7: Version headers ────────────────────────────────────────────────
bold "7. Context doc version headers"

for doc in "$CONTEXT_DIR"/*.md; do
    docname=$(basename "$doc")
    if ! head -1 "$doc" | grep -qE '<!-- v[0-9]+ \| last-verified:'; then
        inc_warn "$docname missing version header (<!-- v1 | last-verified: YYYY-MM-DD -->)"
    fi
done

green "  OK:    Version headers checked"

# ─── Check 8: References footer validation ──────────────────────────────────
bold "8. Context doc References footer"

ENGINE_DIR="$ROOT/GameProject/src/GameProject.Engine"

for doc in "$CONTEXT_DIR"/*.md; do
    docname=$(basename "$doc")

    # Skip changelog (historical log, no references needed)
    case "$docname" in
        changelog-devlog.md) continue ;;
    esac

    # Check References section exists
    if ! grep -q "^## References" "$doc" 2>/dev/null; then
        inc_warn "$docname missing ## References footer"
        continue
    fi

    # Extract source file paths from References section (backtick paths ending in .cs)
    refs_section=$(sed -n '/^## References/,$p' "$doc")
    source_files=$(echo "$refs_section" | grep -oE '`[^`]+\.cs`' 2>/dev/null | tr -d '`' || true)
    for ref in $source_files; do
        if [ ! -f "$ENGINE_DIR/$ref" ]; then
            inc_warn "$docname References lists '$ref' but file not found"
        fi
    done

    # Extract context doc links from References section (markdown links to .md)
    cross_refs=$(echo "$refs_section" | grep -oE '\([a-zA-Z0-9_-]+\.md\)' 2>/dev/null | tr -d '()' || true)
    for ref in $cross_refs; do
        if [ ! -f "$CONTEXT_DIR/$ref" ]; then
            inc_error "$docname References links to '$ref' but .claude/context/$ref does not exist"
        fi
    done
done

green "  OK:    References footer checked"

# ─── Check 9: CLAUDE.md Key Files Reference paths ───────────────────────────
bold "9. CLAUDE.md Key Files Reference → source file existence"

MONO_ROOT="$ROOT/GameProject"
MONO_SRC="$MONO_ROOT/src"

# Extract the Key Files Reference table (between "## Key Files Reference" and next "##")
key_files_section=$(sed -n '/^## Key Files Reference/,/^## /{/^## Key Files Reference/d;/^## /d;p;}' "$CLAUDE_MD")

# Extract backtick-quoted .cs file paths
cs_paths=$(echo "$key_files_section" | grep -oE '`[A-Za-z0-9_/.*]+\.cs`' | tr -d '`' | sort -u)

for ref in $cs_paths; do
    # Skip glob patterns
    case "$ref" in
        *\**) continue ;;
    esac

    # Try Engine path, then MonoGame src path, then Desktop path
    if [ -f "$ENGINE_DIR/$ref" ]; then
        continue
    elif [ -f "$MONO_SRC/$ref" ]; then
        continue
    elif [ -f "$MONO_SRC/GameProject.Engine/$ref" ]; then
        continue
    elif [ -f "$MONO_SRC/GameProject.Desktop/$ref" ]; then
        continue
    else
        inc_warn "CLAUDE.md Key Files Reference lists '$ref' but file not found"
    fi
done

green "  OK:    Key Files Reference paths checked"

# ─── Summary ──────────────────────────────────────────────────────────────────
ERRORS=$(cat "$ERR_FILE")
WARNINGS=$(cat "$WARN_FILE")

echo ""
bold "━━━ Summary ━━━"
echo "  Context docs: $(ls "$CONTEXT_DIR"/*.md 2>/dev/null | wc -l | tr -d ' ')"
echo "  Agents:       $(ls -d "$AGENTS_DIR"/*/AGENT.md 2>/dev/null | wc -l | tr -d ' ')"
echo "  CLAUDE.md:    $(wc -l < "$CLAUDE_MD" | tr -d ' ') lines"

if [ "$ERRORS" -gt 0 ]; then
    red "  $ERRORS error(s), $WARNINGS warning(s)"
    exit 1
elif [ "$WARNINGS" -gt 0 ]; then
    yellow "  0 errors, $WARNINGS warning(s)"
    exit 0
else
    green "  All checks passed!"
    exit 0
fi
