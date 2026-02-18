# Data Collection Methodology

This document describes the methodology for collecting, reconstructing, and analyzing interaction data reported in the manuscript "Codified Context as Infrastructure: A Layered Architecture for Agentic Software Engineering."

## Overview

Interaction data was collected from Claude Code's conversation history, which stores each conversation as a JSONL file on disk. The resulting dataset is a representative snapshot of ~3,600 interactions across ~2 months of development. It is not a complete record: some early conversation files were lost during a cache cleanup, and agent chain data is only available for the latter half of the development period. The data pipeline involved four stages:

1. **Direct extraction** from JSONL conversation files (primary source)
2. **Reconstruction** from indirect artifacts for a gap period where JSONL files were lost
3. **Unification** of multiple data sources into a single deduplicated dataset
4. **Agent counting** from file system analysis and tool call parsing

### Data Quality Tiers

The dataset has three quality tiers reflecting the availability of source data:

| Period | Days | Records | Human Prompts | Agent Data | Source Quality |
|--------|------|---------|---------------|------------|----------------|
| Dec 17--26, 2025 | 10 | 26 | Reconstructed only | None | Indirect artifacts (todos, git commits) |
| Dec 27 -- Jan 16, 2026 | 21 | 1,413 | Full extraction | None | Historical CSV snapshot; agent JSONL files lost |
| Jan 17 -- Feb 16, 2026 | 31 | 2,160 | Full extraction | Full (798 sub-prompts) | Complete JSONL files on disk |

Agent invocation counts, agent type breakdowns, and amplification statistics reported in the manuscript are derived exclusively from the Jan 17 -- Feb 16 period where complete agent chain data is available. Human prompt statistics (brevity, category distribution) use the full dataset.

## Data Sources

### Source 1: Claude Code JSONL Files (Primary)

Claude Code stores conversation history at `~/.claude/projects/{project-path}/`. The directory structure is:

```
~/.claude/projects/-Users-meivas-Documents-game-project/
  {uuid}.jsonl                          # Main conversations (260 files)
  agent-{hash}.jsonl                    # Top-level agent conversations (773 files)
  {uuid}/subagents/agent-{hash}.jsonl   # Nested sub-agent conversations (424 files)
```

**Total: 1,457 JSONL files.**

Each JSONL file contains a sequence of message objects with fields:
- `type`: "user", "assistant", or "system"
- `uuid`: Unique message identifier
- `parentUuid`: Links responses to their prompts
- `timestamp`: ISO 8601 datetime
- `sessionId`: Groups messages within a conversation session
- `gitBranch`: Git branch at time of message
- `message.content`: Message text (string or array of content blocks)
- `message.model`: Model identifier (for assistant messages)
- `message.usage`: Token counts (input, output, cache read, cache create)

**Extraction script:** `extract_prompts.py` iterates over all JSONL files, extracting user-type messages as prompts. For each prompt, it also locates the first assistant response (by `parentUuid`) to capture model, token usage, and tool calls. Tool calls are identified from `tool_use` content blocks in the assistant response, and `Task` tool calls are further parsed for the `subagent_type` parameter to identify which agent was invoked.

**Limitation:** The extraction captures tool calls from only the *first* assistant response to each user message. If the assistant issues multiple responses (e.g., after tool results), only the first is parsed. This means tool counts and agent spawn counts in the CSV may undercount the true values per prompt.

### Source 2: Reconstructed Prompts (Gap Period)

**Problem:** The project began on a Windows machine in December 2025. The JSONL conversation files from this machine (Dec 15, 2025 -- Jan 15, 2026) were purged during a Claude Code cache cleanup before the data collection effort began. This created a ~31-day gap in the primary data source.

**Reconstruction approach:** The script `reconstruct_sessions.py` recovered partial interaction data from three indirect sources that survived the purge:

1. **Todo files** (`~/.claude/todos/*.json`): Claude Code persists task lists as JSON files with file modification timestamps. Each todo file corresponds to one session and contains task descriptions and completion status. These were converted to synthetic prompt records with the format `[Reconstructed from todo session] Tasks (N completed, M pending): task1; task2; ...`.

2. **Git commits** (`git log`): Every commit during the gap period represents at least one development session. Commit messages, timestamps, and file change statistics (lines added/deleted, directories touched) were extracted and converted to synthetic prompt records with the format `[Reconstructed from git commit {hash}] {message} ({+N/-M lines in dir1, dir2})`.

3. **Shell snapshots** (`~/.claude/shell-snapshots/`): Bash command history snapshots with epoch timestamps in filenames. These were used for cross-validation of activity dates but not converted to individual records (too granular to represent meaningful prompts).

**Correlation:** Git commits were correlated to todo sessions by date proximity (+/- 1 day) and annotated with the matching session ID when found.

**Characteristics of reconstructed data:**
- Platform: all marked as `windows`
- `conversation_file`: set to `reconstructed` (identifiable for filtering)
- Token/cost fields: all zero (no usage data available)
- Agent spawn data: all zero (no agent metadata available)
- Category: assigned by keyword matching on commit messages/task descriptions

**Result:** 126 reconstructed records covering Dec 17, 2025 -- Jan 16, 2026.

**Impact on reported statistics:** Reconstructed records contribute to total prompt counts and date range but do NOT contribute to token usage, cost estimates, agent invocation counts, or tool usage statistics. All agent-related statistics in the manuscript are derived exclusively from directly-extracted JSONL data.

### Source 3: Historical Git Versions

The extraction script was run multiple times during development, producing successive versions of `prompts.csv`. An earlier version (git commit `4197ac4`) contained data from Dec 27, 2025 -- Jan 25, 2026 (2,092 rows) that partially overlapped with but extended beyond the current extraction.

The `build_unified_csv.py` script merges these versions:
1. Extract `prompts.csv` from git commit `4197ac4`
2. Load current `prompts.csv` (with reconstructed records)
3. Optionally load additional CSV exports (e.g., from Windows machine)
4. Deduplicate by `prompt_hash` (SHA-256 of timestamp + prompt text, truncated to 16 hex chars)
5. When duplicates exist, prefer the row with richer metadata (longer `prompt_full`, more tool calls, model information)

## Unified Dataset

The final dataset (`prompts_unified.csv`) contains 3,599 rows:

| Source | Rows | Date Range |
|--------|------|------------|
| Main conversation prompts | 2,675 | Dec 27, 2025 -- Feb 16, 2026 |
| Agent sub-prompts | 798 | Jan 17 -- Feb 16, 2026 |
| Reconstructed (Windows gap) | 126 | Dec 17 -- Jan 16, 2026 |

Platform breakdown: 3,461 macOS, 138 Windows.

### Column Schema

All CSV files share 29 columns:

| Group | Columns |
|-------|---------|
| Identification | `id`, `timestamp`, `date`, `time`, `prompt_hash` |
| Content | `prompt` (max 500 chars), `prompt_full` (if >500), `word_count`, `char_count` |
| Categorization | `category`, `category_secondary` |
| Session context | `session_id`, `conversation_file`, `git_branch`, `platform` |
| Response metrics | `model`, `response_tokens_in`, `response_tokens_out`, `response_cache_read`, `response_cache_create` |
| Tool/agent usage | `tools_used`, `tool_count`, `agents_spawned`, `agent_types` |
| Cost estimation | `cost_input_usd`, `cost_output_usd`, `cost_cache_read_usd`, `cost_cache_write_usd`, `cost_total_usd` |

### Prompt Classification

Prompts are classified into 25 categories by keyword matching (see `extract_prompts.py` CATEGORIES dict). Classification is:
- **Primary category:** Highest keyword match count
- **Secondary category:** Second-highest match count (if any)
- **Special categories:** `system` (tool-generated messages), `confirmation` (short affirmative responses like "yes", "proceed", "ok")

This is a simple heuristic classifier. Prompts containing keywords from multiple categories are assigned to the category with the most keyword matches. No manual validation was performed on category assignments.

## Agent Invocation Counting

Agent statistics were derived from two complementary methods:

### Method 1: JSONL File Counting (Invocations and Turns)

Each agent invocation produces a separate JSONL file. The total number of agent JSONL files (1,197 = 773 top-level + 424 nested sub-agents) equals the total number of agent invocations. "Agent turns" were counted as the number of user-type messages within each agent JSONL file.

| Metric | Value |
|--------|-------|
| Agent JSONL files (top-level) | 773 |
| Agent JSONL files (nested sub-agents) | 424 |
| Total agent invocations | 1,197 |
| Total agent turns (user messages across all files) | 16,522 |
| Average turns per invocation | 13.8 |

**Note:** "Turns" in agent files represent internal agentic loop iterations (tool call + result + next step), not human prompts. Each turn corresponds to one user-type message in the JSONL, which is typically a tool result being fed back to the agent.

### Method 2: Task Tool Call Parsing (Agent Type Classification)

To classify agents by type (project-specific vs. built-in), all JSONL files were scanned for `Task` tool call blocks in assistant messages. The `Task` tool's `input.subagent_type` field identifies the agent type. This method found 757 classifiable Task invocations (fewer than 1,197 because some agent files were spawned by mechanisms other than the Task tool, or the parent conversation was not available).

| Category | Invocations | % |
|----------|-------------|---|
| Project-specific agents | 432 | 57% |
| Built-in agents (Explore, general-purpose, Bash) | 325 | 43% |
| **Total classified** | **757** | **100%** |

Top project-specific agents by invocation count:
1. `code-reviewer-game-dev`: 154
2. `network-protocol-designer`: 85
3. `Plan` (orchestrator): 47
4. `ecs-component-designer`: 41
5. `systems-designer`: 29

Top built-in agents:
1. `Explore` (codebase search): 308
2. `general-purpose`: 12
3. `Bash`: 4

The high `Explore` count reflects agent-to-agent chains: project-specific agents (especially `Plan`) frequently invoke `Explore` as a sub-agent for codebase search before implementing changes.

### Discrepancy Between Methods

Method 1 counts 1,197 invocations; Method 2 classifies 757. The 440-invocation gap has several causes:
- Agent files spawned before the `Task` tool existed or by internal mechanisms without a parseable `Task` block
- "Warmup" agent files (containing only a single "Warmup" message with no real work)
- Agent files whose parent conversation was in the gap period (no JSONL available to parse for Task calls)

The manuscript reports Method 1's count (1,197 invocations, 16,522 turns) for total agent activity, and Method 2's breakdown for the project-specific vs. built-in split.

## Cost Estimation

API costs were estimated using published per-million-token pricing:

| Model | Input | Output | Cache Read | Cache Write |
|-------|-------|--------|------------|-------------|
| Claude Opus 4/4.1 | $15.00 | $75.00 | 10% of input | 125% of input |
| Claude Sonnet 4.5 | $3.00 | $15.00 | 10% of input | 125% of input |
| Claude Haiku 4.5 | $1.00 | $5.00 | 10% of input | 125% of input |

Costs are estimated from token usage fields in the JSONL data. Reconstructed records have zero cost (no token data). The reported total (~$693) is therefore a lower bound that excludes the Windows gap period.

## Reproducibility

All scripts and data files are in the companion repository:

| File | Purpose |
|------|---------|
| `extract_prompts.py` | Extract prompts from JSONL → `prompts.csv`, `agent_prompts.csv` |
| `reconstruct_sessions.py` | Reconstruct gap period from todos/git/shell → merge into `prompts.csv` |
| `build_unified_csv.py` | Merge git historical versions + current → `prompts_unified.csv` |
| `analyze_impact.py` | Pre/post agent comparison analysis |
| `compare_pre_post_agents.py` | Detailed pre/post comparison with breakdowns |
| `correlate_plans.py` | Correlate planning sessions to outcomes |
| `find_key_plans.py` | Identify high-impact planning sessions |

To reproduce from raw JSONL files:
```bash
cd .claude/conversation-history

# Step 1: Extract from JSONL (requires ~/.claude/projects/ to exist)
python extract_prompts.py --force --stats

# Step 2: Reconstruct gap period (requires git repo + ~/.claude/todos/)
python reconstruct_sessions.py --merge --stats

# Step 3: Build unified dataset
python build_unified_csv.py --stats
```

**Note:** Raw JSONL files contain full conversation content (prompts, responses, tool calls) and are not included in the companion repository for privacy reasons. The extracted CSV files contain only prompt text (truncated to 500 characters) and metadata.

## Known Limitations

1. **Gap period undercount:** The Dec 15 -- Jan 15 period has only 126 reconstructed records vs. an estimated 500+ actual prompts based on git commit frequency. The reconstruction captures session-level activity but not individual prompt-level interactions.

2. **Agent sub-prompt extraction:** The `agent_prompts.csv` (798 rows) counts user-type messages within agent JSONL files, which represent tool result feed-back turns, not semantically distinct "prompts." The true prompt count is better captured by agent invocations (1,197) or agent turns (16,522).

3. **Tool call undercounting:** The extraction captures tool calls from only the first assistant response per prompt. Multi-turn tool usage within a single prompt-response cycle is undercounted.

4. **Category classification accuracy:** Keyword-based classification has known issues: "system" as a game design term (ECS systems) triggers the `ecs` category, and prompts with generic terms may be miscategorized. No manual validation was performed.

5. **Cost estimation precision:** Costs are estimated from token counts and published pricing. Actual billed amounts may differ due to rounding, pricing tier changes, or promotional credits.

6. **Cross-platform data loss:** Windows JSONL files were lost; only macOS JSONL files survive. The 138 Windows rows in the unified dataset are a mix of reconstructed records and manually transcribed prompts from memory.
