# Data Extraction Methodology (Companion to Main Paper)

This document contains detailed data extraction methodology moved from Section 4.6 of the main paper to keep the manuscript concise. See also `data-collection-methodology.md` for the full data collection pipeline description.

## Conversation History File Structure

Claude Code stores each conversation as a JSONL file, with separate files for each agent invocation (including nested sub-agents spawned by orchestrator agents). The file structure is:

```
~/.claude/projects/{project-path}/
  {uuid}.jsonl                          # Main conversations (260 files)
  agent-{hash}.jsonl                    # Top-level agent conversations (773 files)
  {uuid}/subagents/agent-{hash}.jsonl   # Nested sub-agent conversations (424 files)
```

**Total: 1,457 JSONL files.**

## Extraction Approach

Human prompts were extracted from main conversation files (260 files), while agent metrics were derived from agent conversation files (1,197 files, including 424 nested sub-agent files created by agent-to-agent chains). Agent turn counts were computed by counting user-type messages within each agent JSONL file. Agent type classification was derived from `Task` tool call parameters (`subagent_type` field) found in parent conversation files.

## Data Quality Notes

- The extraction captures tool calls from only the *first* assistant response to each user message. If the assistant issues multiple responses (e.g., after tool results), only the first is parsed. This means tool counts and agent spawn counts may undercount the true values per prompt.
- "Turns" in agent files represent internal agentic loop iterations (tool call + result + next step), not human prompts.
- Agent type classification identified 757 of 1,197 invocations. The 440-invocation gap reflects agent files spawned by internal mechanisms without a parseable `Task` block, warmup files, and files whose parent conversation was lost.

The extraction scripts and full methodology are described in the companion repository's data collection methodology document.
