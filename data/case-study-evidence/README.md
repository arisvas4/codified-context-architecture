# Case Study Evidence Files

JSONL conversation transcripts referenced in Section 4.8 of the manuscript.
Preserved here because the source directory (`.claude/projects/`) is periodically wiped.

Source: `/Users/meivas/.claude/projects/-Users-meivas-Documents-game-project/`

## CS1: CombatRng Determinism -- Agent as Domain Expert

**Session:** Jan 21, 2026 | 5 context exhaustions | 14 agent invocations | 84 edits across 12 files

| File | Size | Description |
|------|------|-------------|
| `66184afd-a544-4b7c-8eeb-347bf71628e2.jsonl` | 4.5M | Main session |
| `agent-a1116ad.jsonl` | 255K | network-protocol-designer agent review |

## CS2: UI Sync Routing -- Captured Experience

| File | Size | Description |
|------|------|-------------|
| `0e11fb73-d902-4d08-b856-8a86fcf1c3b6.jsonl` | 6.8M | Radial dial session (created ui-sync-patterns.md) |
| `05f77c4f-6fdf-49bf-bb8a-3c9fdea45ef5.jsonl` | 4.9M | Shop sync session (the "before" case) |

## CS3: Boss Fight Framework -- Architectural Inheritance

**Session:** Jan 24-25, 2026

| File | Size | Description |
|------|------|-------------|
| `ac79710a-2b66-4d67-b254-b73446060560.jsonl` | 9.3M | Main session |
| `agent-afc5682.jsonl` | 634K | systems-designer agent (read enemy-combat-system.md first) |
| `agent-aab8ca2.jsonl` | 269K | ecs-component-designer agent |

## CS4: Save System Documentation -- Coordination Document

**Session:** Jan 21, 2026 | 74 sessions reference save-system.md

| File | Size | Description |
|------|------|-------------|
| `3e8f6053-cc72-46dd-8e83-5ed4fbfe67ee.jsonl` | 1.3M | Main session |
| `agent-a4429ad.jsonl` | 483K | Agent that discovered save-system.md via globbing |

## CS5: Coordinate Wizard -- Instant Diagnosis

**Session:** Jan 25, 2026 | Read-only agent | 4 edits to fix

| File | Size | Description |
|------|------|-------------|
| `7e67b311-9770-40ae-b74d-57484c07e780.jsonl` | 2.7M | Main session |
| `agent-a0de774.jsonl` | 159K | coordinate-wizard agent (read-only diagnostic) |

## CS6: Drop System -- Gap Detection and Creation

**Session:** Jan 25, 2026 | 9 agent invocations | 2 context docs created

| File | Size | Description |
|------|------|-------------|
| `65c02083-c0bc-43a9-ab31-3314fefcca55.jsonl` | 7.1M | Main session |
| `agent-a355253.jsonl` | 145K | Sub-agent (from subagents/ dir) |
| `agent-a43a99f.jsonl` | 170K | Sub-agent (from subagents/ dir) |
| `agent-a5b49d4.jsonl` | 213K | Sub-agent (from subagents/ dir) |
| `agent-ac40064.jsonl` | 205K | Sub-agent (from subagents/ dir) |

## Supplementary Sessions

Referenced in prompting-case-studies.md (pre-agent era comparisons).

| File | Size | Description |
|------|------|-------------|
| `1f7e588f-55d3-4e44-b548-eed963619eeb.jsonl` | 106M | System registration bug (Jan 29) |
| `81f09553-93e7-4cd5-aec1-282a6e78b05e.jsonl` | 3.4M | Toast notification coordinates (Jan 22) |

## Total

18 JSONL files, ~149M
