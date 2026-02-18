#!/usr/bin/env python3
"""
Extract user prompts from Claude Code conversation history to CSV.

Outputs three CSV files:
- prompts.csv: Main conversation prompts
- agent_prompts.csv: Agent/subagent prompts
- prompts_monthly.csv: Monthly usage summary

Usage:
    python extract_prompts.py                    # Extract all prompts
    python extract_prompts.py --force            # Rebuild from scratch
    python extract_prompts.py --stats            # Show summary statistics
    python extract_prompts.py --output DIR       # Custom output directory
"""

import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Pricing per million tokens (as of January 2025)
# Format: {model_pattern: (input_price, output_price, cache_read_multiplier, cache_write_multiplier)}
MODEL_PRICING = {
    'opus-4-5': (5.00, 25.00, 0.10, 1.25),      # Claude Opus 4.5
    'opus-4': (15.00, 75.00, 0.10, 1.25),        # Claude Opus 4/4.1
    'sonnet-4-5': (3.00, 15.00, 0.10, 1.25),    # Claude Sonnet 4.5
    'sonnet-4': (3.00, 15.00, 0.10, 1.25),      # Claude Sonnet 4
    'sonnet-3': (3.00, 15.00, 0.10, 1.25),      # Claude Sonnet 3.x
    'haiku-4': (1.00, 5.00, 0.10, 1.25),        # Claude Haiku 4.x
    'haiku-3': (0.25, 1.25, 0.10, 1.25),        # Claude Haiku 3.x
}

# Category definitions with keywords
CATEGORIES = {
    'physics': ['physics', 'collision', 'velocity', 'knockback', 'spatial', 'raycast', 'force', 'movement'],
    'networking': ['network', 'multiplayer', 'sync', 'lobby', 'host', 'client', 'interpolation', 'latency', 'packet', 'message', 'peer'],
    'rendering': ['render', 'sprite', 'animation', 'camera', 'texture', 'particle', 'visual', 'draw', 'effect', 'bloom', 'shader'],
    'ui': ['menu', 'button', 'ui', 'hud', 'interface', 'overlay', 'screen', 'panel', 'dialog', 'modal', 'tooltip'],
    'combat': ['damage', 'health', 'projectile', 'ability', 'attack', 'weapon', 'powerup', 'fireball', 'bullet'],
    'ai': ['ai', 'behavior', 'enemy', 'chase', 'wander', 'pathfind', 'aggro', 'target', 'flee'],
    'spawning': ['spawn', 'wave', 'spawner'],
    'dungeon': ['dungeon', 'procedural', 'bsp', 'room', 'corridor', 'generation', 'level', 'floor'],
    'input': ['input', 'keyboard', 'controller', 'gamepad', 'controls', 'keybind', 'mouse'],
    'ecs': ['entity', 'component', 'system', 'archetype', 'query', 'world'],
    'artwork': ['sprite', 'texture', 'asset', 'image', 'art', 'placeholder', 'atlas', 'png', 'blender', 'meshy'],
    'devtools': ['debug', 'preview', 'test', 'devtools', 'console', 'cli'],
    'audio': ['sound', 'audio', 'music', 'sfx', 'volume'],
    'content': ['content', 'definition', 'json', 'data', 'load', 'config'],
    'save': ['save', 'load', 'profile', 'slot', 'progress'],
    'hero': ['hero', 'player', 'character', 'class', 'drone'],
    'gamestate': ['state', 'transition', 'hub', 'survival', 'adventure', 'defense', 'payload', 'boss'],
    # Categories broken out from "other"
    'build': ['dotnet', 'build', 'compile', 'launch', 'run', 'terminal', 'install', 'homebrew', 'npm', 'nuget'],
    'tooling': ['agent', 'mcp', 'context7', 'claude', 'skill', 'hook'],
    'leveldesign': ['ldtk', 'tiled', 'tilemap', 'tileset', 'map editor', 'room template'],
    'refactor': ['refactor', 'cleanup', 'organize', 'rename', 'restructure'],
    'planning': ['plan', 'phase', 'implement', 'approach', 'what is next', 'begin with', 'what is task', 'what is step',
                 'vertical slice', 'conclude', 'scope', 'roadmap', 'milestone', 'prioritize', 'backlog'],
    'debugging': ['fix', 'bug', 'wrong', 'broken', 'doesn\'t work', 'not working', 'still not', 'why does',
                  'why is', 'issue', 'off by', 'offset', 'misalign', 'crash', 'exception', 'error', 'null ref'],
    'game_design': ['kirby', 'vamp survivor', 'noita', 'wizard with a gun', 'hades', 'diablo', 'design',
                    'mechanic', 'how many combo', 'how many abilit', 'compare to', 'what do you think',
                    'balance', 'feel', 'pacing', 'fun'],
    'documentation': ['document', 'context file', 'write up', 'write about', 'add notes', 'changelog',
                      'devlog', 'readme', 'whitepaper', 'update.*context'],
}

# Patterns that indicate system/meta messages (not real prompts)
SYSTEM_PATTERNS = [
    'request interrupted',
    '<local-command-',
    'compacted',
    'goodbye',
    'catch you later',
    'warmup',
]

# Short confirmation responses (tracked but low-value for analysis)
CONFIRMATION_WORDS = {
    'yes', 'no', 'yea', 'yeah', 'nope', 'sure', 'ok', 'okay', 'continue', 'proceed', 'both', 'neither',
    'yep', 'yup', 'looks good', 'go ahead', 'do it', 'sounds good', 'correct', 'right', 'exactly',
    'retry', 'redo', 'rewrite', 're-write', 'repeat', 'b', 'a',
}

CSV_COLUMNS = [
    'id', 'timestamp', 'date', 'time', 'prompt', 'prompt_full', 'word_count', 'char_count',
    'category', 'category_secondary', 'session_id', 'conversation_file', 'git_branch',
    'model', 'response_tokens_in', 'response_tokens_out', 'response_cache_read',
    'response_cache_create', 'tools_used', 'tool_count', 'agents_spawned', 'agent_types',
    'platform', 'prompt_hash',
    'cost_input_usd', 'cost_output_usd', 'cost_cache_read_usd', 'cost_cache_write_usd', 'cost_total_usd'
]


def compute_hash(timestamp: str, prompt: str) -> str:
    """Compute SHA256 hash for deduplication."""
    content = f"{timestamp}:{prompt}"
    return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]


def estimate_cost(model: str, tokens_in: int, tokens_out: int,
                  cache_read: int, cache_create: int) -> Dict[str, float]:
    """Estimate cost in USD based on model and token usage.

    Returns dict with individual cost components and total.
    """
    if not model:
        return {'input': 0.0, 'output': 0.0, 'cache_read': 0.0, 'cache_write': 0.0, 'total': 0.0}

    model_lower = model.lower()

    # Find matching pricing tier
    pricing = None
    for pattern, prices in MODEL_PRICING.items():
        if pattern in model_lower:
            pricing = prices
            break

    if not pricing:
        # Default to Sonnet pricing if unknown model
        pricing = MODEL_PRICING['sonnet-4']

    input_price, output_price, cache_read_mult, cache_write_mult = pricing

    # Calculate costs (prices are per million tokens)
    input_cost = (tokens_in / 1_000_000) * input_price
    output_cost = (tokens_out / 1_000_000) * output_price
    cache_read_cost = (cache_read / 1_000_000) * (input_price * cache_read_mult)
    cache_write_cost = (cache_create / 1_000_000) * (input_price * cache_write_mult)

    total = input_cost + output_cost + cache_read_cost + cache_write_cost

    return {
        'input': round(input_cost, 6),
        'output': round(output_cost, 6),
        'cache_read': round(cache_read_cost, 6),
        'cache_write': round(cache_write_cost, 6),
        'total': round(total, 6),
    }


def detect_platform(path_str: str) -> str:
    """Detect platform from path format."""
    if 'C-Users' in path_str or 'C:\\Users' in path_str or path_str.startswith('-C-'):
        return 'windows'
    return 'mac'


def classify_prompt(text: str) -> Tuple[str, str]:
    """Classify prompt into primary and secondary categories."""
    text_lower = text.lower()
    text_stripped = text.strip().lower()

    # Check for system/meta messages first
    for pattern in SYSTEM_PATTERNS:
        if pattern in text_lower:
            return 'system', ''

    # Check for short confirmation responses
    if text_stripped in CONFIRMATION_WORDS or (len(text_stripped) <= 30 and any(
        text_stripped.startswith(w) for w in CONFIRMATION_WORDS
    )):
        return 'confirmation', ''

    # Regular keyword-based classification
    scores = {}
    for category, keywords in CATEGORIES.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[category] = score

    if not scores:
        return 'other', ''

    sorted_cats = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    primary = sorted_cats[0][0]
    secondary = sorted_cats[1][0] if len(sorted_cats) > 1 else ''

    return primary, secondary


def get_claude_dirs() -> List[Path]:
    """Find all Claude Code project directories for game-project."""
    home = Path.home()
    claude_dir = home / ".claude" / "projects"

    if not claude_dir.exists():
        return []

    dirs = []
    for folder in claude_dir.iterdir():
        if folder.is_dir() and "game-project" in folder.name:
            dirs.append(folder)

    return dirs


def load_existing_hashes(csv_path: Path) -> Set[str]:
    """Load existing prompt hashes from CSV to avoid duplicates."""
    hashes = set()
    if csv_path.exists():
        try:
            with open(csv_path, 'r', encoding='utf-8', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if 'prompt_hash' in row:
                        hashes.add(row['prompt_hash'])
        except Exception as e:
            print(f"Warning: Could not read existing CSV: {e}")
    return hashes


def extract_from_jsonl(filepath: Path, existing_hashes: Set[str]) -> List[Dict]:
    """Extract prompts and response metadata from a JSONL file."""
    prompts = []
    messages_by_uuid = {}
    platform = detect_platform(str(filepath))

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    uuid = obj.get('uuid')

                    if uuid:
                        messages_by_uuid[uuid] = obj

                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return []

    # Process user messages and link to assistant responses
    for uuid, obj in messages_by_uuid.items():
        if obj.get('type') != 'user':
            continue

        msg = obj.get('message', {})
        content = msg.get('content', [])
        timestamp = obj.get('timestamp', '')
        session_id = obj.get('sessionId', '')
        git_branch = obj.get('gitBranch', '')

        # Extract text from content (can be string or list of content blocks)
        prompt_text = ''
        if isinstance(content, str):
            # Agent messages often have content as a plain string
            prompt_text = content
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get('type') == 'text':
                    text = item.get('text', '')
                    # Skip system/IDE messages
                    if text and not text.startswith('<ide_') and not text.startswith('<system'):
                        prompt_text = text
                        break

        if not prompt_text or prompt_text.startswith('<ide_') or prompt_text.startswith('<system'):
            continue

        # Skip warmup messages
        if prompt_text.strip().lower() == 'warmup':
            continue

        # Compute hash for deduplication
        prompt_hash = compute_hash(timestamp, prompt_text)
        if prompt_hash in existing_hashes:
            continue

        # Find the assistant response (look for message with parentUuid = this uuid)
        response_data = {
            'model': '',
            'tokens_in': 0,
            'tokens_out': 0,
            'cache_read': 0,
            'cache_create': 0,
            'tools': [],
            'agents': [],
        }

        for _, other_obj in messages_by_uuid.items():
            if other_obj.get('parentUuid') == uuid and other_obj.get('type') == 'assistant':
                resp_msg = other_obj.get('message', {})
                response_data['model'] = resp_msg.get('model', '')

                usage = resp_msg.get('usage', {})
                response_data['tokens_in'] = usage.get('input_tokens', 0)
                response_data['tokens_out'] = usage.get('output_tokens', 0)
                response_data['cache_read'] = usage.get('cache_read_input_tokens', 0)
                response_data['cache_create'] = usage.get('cache_creation_input_tokens', 0)

                # Extract tool usage
                resp_content = resp_msg.get('content', [])
                for item in resp_content:
                    if isinstance(item, dict) and item.get('type') == 'tool_use':
                        tool_name = item.get('name', '')
                        response_data['tools'].append(tool_name)

                        # Check for Task (agent) calls
                        if tool_name == 'Task':
                            agent_input = item.get('input', {})
                            agent_type = agent_input.get('subagent_type', 'unknown')
                            response_data['agents'].append(agent_type)
                break

        # Parse timestamp for date/time columns
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            date_str = dt.strftime('%Y-%m-%d')
            time_str = dt.strftime('%H:%M:%S')
        except:
            date_str = ''
            time_str = ''

        # Classify the prompt
        category, category_secondary = classify_prompt(prompt_text)

        # Build the record
        word_count = len(prompt_text.split())
        char_count = len(prompt_text)

        # Calculate estimated cost
        cost = estimate_cost(
            response_data['model'],
            response_data['tokens_in'],
            response_data['tokens_out'],
            response_data['cache_read'],
            response_data['cache_create']
        )

        record = {
            'id': 0,  # Will be assigned after sorting
            'timestamp': timestamp,
            'date': date_str,
            'time': time_str,
            'prompt': prompt_text[:500] if len(prompt_text) > 500 else prompt_text,
            'prompt_full': prompt_text if len(prompt_text) > 500 else '',
            'word_count': word_count,
            'char_count': char_count,
            'category': category,
            'category_secondary': category_secondary,
            'session_id': session_id,
            'conversation_file': filepath.name,
            'git_branch': git_branch,
            'model': response_data['model'],
            'response_tokens_in': response_data['tokens_in'],
            'response_tokens_out': response_data['tokens_out'],
            'response_cache_read': response_data['cache_read'],
            'response_cache_create': response_data['cache_create'],
            'tools_used': ','.join(response_data['tools']),
            'tool_count': len(response_data['tools']),
            'agents_spawned': len(response_data['agents']),
            'agent_types': ','.join(response_data['agents']),
            'platform': platform,
            'prompt_hash': prompt_hash,
            'cost_input_usd': cost['input'],
            'cost_output_usd': cost['output'],
            'cost_cache_read_usd': cost['cache_read'],
            'cost_cache_write_usd': cost['cache_write'],
            'cost_total_usd': cost['total'],
        }

        prompts.append(record)

    return prompts


def write_csv(prompts: List[Dict], output_path: Path):
    """Write prompts to CSV file."""
    # Sort by timestamp
    prompts.sort(key=lambda x: x['timestamp'])

    # Assign IDs
    for i, p in enumerate(prompts, 1):
        p['id'] = i

    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(prompts)


def generate_monthly_summary(prompts: List[Dict], agent_prompts: List[Dict], output_path: Path):
    """Generate monthly summary CSV from all prompts."""
    all_prompts = prompts + agent_prompts

    if not all_prompts:
        return

    # Group by month (YYYY-MM)
    monthly_data = defaultdict(lambda: {
        'prompt_count': 0,
        'agent_prompt_count': 0,
        'tokens_in': 0,
        'tokens_out': 0,
        'cache_read': 0,
        'cache_create': 0,
        'cost_input': 0.0,
        'cost_output': 0.0,
        'cost_cache_read': 0.0,
        'cost_cache_write': 0.0,
        'cost_total': 0.0,
        'tool_count': 0,
        'agents_spawned': 0,
        'categories': defaultdict(int),
        'sessions': set(),
        'models': defaultdict(int),
    })

    # Process main prompts
    for p in prompts:
        date = p.get('date', '')
        if not date:
            continue
        month = date[:7]  # YYYY-MM

        monthly_data[month]['prompt_count'] += 1
        monthly_data[month]['tokens_in'] += p.get('response_tokens_in', 0)
        monthly_data[month]['tokens_out'] += p.get('response_tokens_out', 0)
        monthly_data[month]['cache_read'] += p.get('response_cache_read', 0)
        monthly_data[month]['cache_create'] += p.get('response_cache_create', 0)
        monthly_data[month]['cost_input'] += p.get('cost_input_usd', 0)
        monthly_data[month]['cost_output'] += p.get('cost_output_usd', 0)
        monthly_data[month]['cost_cache_read'] += p.get('cost_cache_read_usd', 0)
        monthly_data[month]['cost_cache_write'] += p.get('cost_cache_write_usd', 0)
        monthly_data[month]['cost_total'] += p.get('cost_total_usd', 0)
        monthly_data[month]['tool_count'] += p.get('tool_count', 0)
        monthly_data[month]['agents_spawned'] += p.get('agents_spawned', 0)
        monthly_data[month]['categories'][p.get('category', 'other')] += 1
        monthly_data[month]['sessions'].add(p.get('session_id', ''))
        model = p.get('model', '')
        if model:
            monthly_data[month]['models'][model] += 1

    # Process agent prompts
    for p in agent_prompts:
        date = p.get('date', '')
        if not date:
            continue
        month = date[:7]

        monthly_data[month]['agent_prompt_count'] += 1
        monthly_data[month]['tokens_in'] += p.get('response_tokens_in', 0)
        monthly_data[month]['tokens_out'] += p.get('response_tokens_out', 0)
        monthly_data[month]['cache_read'] += p.get('response_cache_read', 0)
        monthly_data[month]['cache_create'] += p.get('response_cache_create', 0)
        monthly_data[month]['cost_input'] += p.get('cost_input_usd', 0)
        monthly_data[month]['cost_output'] += p.get('cost_output_usd', 0)
        monthly_data[month]['cost_cache_read'] += p.get('cost_cache_read_usd', 0)
        monthly_data[month]['cost_cache_write'] += p.get('cost_cache_write_usd', 0)
        monthly_data[month]['cost_total'] += p.get('cost_total_usd', 0)
        monthly_data[month]['tool_count'] += p.get('tool_count', 0)
        monthly_data[month]['categories'][p.get('category', 'other')] += 1

    # Build CSV rows
    # Dynamic columns: fixed columns + one column per category
    all_categories = set()
    for data in monthly_data.values():
        all_categories.update(data['categories'].keys())
    all_categories = sorted(all_categories)

    monthly_columns = [
        'month', 'prompt_count', 'agent_prompt_count', 'total_prompts',
        'session_count', 'tokens_in', 'tokens_out', 'cache_read', 'cache_create',
        'total_tokens', 'cost_input_usd', 'cost_output_usd', 'cost_cache_read_usd',
        'cost_cache_write_usd', 'cost_total_usd', 'tool_calls', 'agents_spawned',
        'primary_model'
    ] + [f'cat_{cat}' for cat in all_categories]

    rows = []
    for month in sorted(monthly_data.keys()):
        data = monthly_data[month]

        # Find primary model (most used)
        primary_model = ''
        if data['models']:
            primary_model = max(data['models'].items(), key=lambda x: x[1])[0]

        row = {
            'month': month,
            'prompt_count': data['prompt_count'],
            'agent_prompt_count': data['agent_prompt_count'],
            'total_prompts': data['prompt_count'] + data['agent_prompt_count'],
            'session_count': len(data['sessions']),
            'tokens_in': data['tokens_in'],
            'tokens_out': data['tokens_out'],
            'cache_read': data['cache_read'],
            'cache_create': data['cache_create'],
            'total_tokens': data['tokens_in'] + data['tokens_out'] + data['cache_read'] + data['cache_create'],
            'cost_input_usd': round(data['cost_input'], 2),
            'cost_output_usd': round(data['cost_output'], 2),
            'cost_cache_read_usd': round(data['cost_cache_read'], 2),
            'cost_cache_write_usd': round(data['cost_cache_write'], 2),
            'cost_total_usd': round(data['cost_total'], 2),
            'tool_calls': data['tool_count'],
            'agents_spawned': data['agents_spawned'],
            'primary_model': primary_model,
        }

        # Add category counts
        for cat in all_categories:
            row[f'cat_{cat}'] = data['categories'].get(cat, 0)

        rows.append(row)

    # Write CSV
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=monthly_columns, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} monthly summaries to {output_path}")


def print_stats(prompts: List[Dict], agent_prompts: List[Dict]):
    """Print summary statistics."""
    print("\n" + "="*60)
    print("PROMPT EXTRACTION STATISTICS")
    print("="*60)

    print(f"\nMain conversation prompts: {len(prompts)}")
    print(f"Agent prompts: {len(agent_prompts)}")
    print(f"Total prompts: {len(prompts) + len(agent_prompts)}")

    if prompts:
        # Category breakdown
        categories = defaultdict(int)
        for p in prompts:
            categories[p['category']] += 1

        print("\nCategory breakdown (main prompts):")
        for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
            pct = (count / len(prompts)) * 100
            print(f"  {cat:15} {count:4} ({pct:5.1f}%)")

        # Token usage and cost
        total_in = sum(p['response_tokens_in'] for p in prompts)
        total_out = sum(p['response_tokens_out'] for p in prompts)
        total_cache_read = sum(p['response_cache_read'] for p in prompts)
        total_cache_create = sum(p['response_cache_create'] for p in prompts)

        cost_input = sum(p.get('cost_input_usd', 0) for p in prompts)
        cost_output = sum(p.get('cost_output_usd', 0) for p in prompts)
        cost_cache_read = sum(p.get('cost_cache_read_usd', 0) for p in prompts)
        cost_cache_write = sum(p.get('cost_cache_write_usd', 0) for p in prompts)
        cost_total = sum(p.get('cost_total_usd', 0) for p in prompts)

        print(f"\nToken usage:")
        print(f"  Input tokens:       {total_in:>12,}")
        print(f"  Output tokens:      {total_out:>12,}")
        print(f"  Cache read tokens:  {total_cache_read:>12,}")
        print(f"  Cache write tokens: {total_cache_create:>12,}")

        print(f"\nCost breakdown:")
        print(f"  Input cost:         ${cost_input:>10.2f}")
        print(f"  Output cost:        ${cost_output:>10.2f}")
        print(f"  Cache read cost:    ${cost_cache_read:>10.2f}")
        print(f"  Cache write cost:   ${cost_cache_write:>10.2f}")
        print(f"  -------------------------------")
        print(f"  Total cost:         ${cost_total:>10.2f}")

        # Tool usage
        all_tools = []
        for p in prompts:
            if p['tools_used']:
                all_tools.extend(p['tools_used'].split(','))

        tool_counts = defaultdict(int)
        for tool in all_tools:
            tool_counts[tool] += 1

        print("\nTop 10 tools used:")
        for tool, count in sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {tool:20} {count:4}")

        # Date range
        dates = [p['date'] for p in prompts if p['date']]
        if dates:
            print(f"\nDate range: {min(dates)} to {max(dates)}")

    print("\n" + "="*60)


def main():
    parser = argparse.ArgumentParser(description='Extract Claude Code prompts to CSV')
    parser.add_argument('--output', '-o', type=Path, help='Output directory (default: script directory)')
    parser.add_argument('--force', '-f', action='store_true', help='Rebuild from scratch (ignore existing)')
    parser.add_argument('--stats', '-s', action='store_true', help='Show statistics after extraction')
    args = parser.parse_args()

    # Determine output directory
    script_dir = Path(__file__).parent
    output_dir = args.output or script_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    main_csv = output_dir / 'prompts.csv'
    agent_csv = output_dir / 'agent_prompts.csv'
    monthly_csv = output_dir / 'prompts_monthly.csv'

    # Load existing hashes (unless force rebuild)
    main_hashes = set() if args.force else load_existing_hashes(main_csv)
    agent_hashes = set() if args.force else load_existing_hashes(agent_csv)

    # Find all Claude project directories
    claude_dirs = get_claude_dirs()
    if not claude_dirs:
        print("No Claude Code project directories found for game-project")
        sys.exit(1)

    print(f"Found {len(claude_dirs)} project director{'y' if len(claude_dirs) == 1 else 'ies'}")

    all_main_prompts = []
    all_agent_prompts = []

    for claude_dir in claude_dirs:
        print(f"Processing: {claude_dir.name}")

        # Process main conversation files
        main_files = [f for f in claude_dir.glob("*.jsonl") if not f.name.startswith("agent-")]
        for filepath in main_files:
            prompts = extract_from_jsonl(filepath, main_hashes)
            all_main_prompts.extend(prompts)
            # Add new hashes
            for p in prompts:
                main_hashes.add(p['prompt_hash'])

        # Process agent files (top-level and nested subagents)
        agent_files = list(claude_dir.glob("agent-*.jsonl"))
        agent_files += list(claude_dir.glob("*/subagents/agent-*.jsonl"))
        for filepath in agent_files:
            prompts = extract_from_jsonl(filepath, agent_hashes)
            all_agent_prompts.extend(prompts)
            for p in prompts:
                agent_hashes.add(p['prompt_hash'])

    # Merge with existing data if not force rebuild
    if not args.force:
        if main_csv.exists():
            with open(main_csv, 'r', encoding='utf-8', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Convert numeric fields
                    row['id'] = int(row.get('id', 0))
                    row['word_count'] = int(row.get('word_count', 0))
                    row['char_count'] = int(row.get('char_count', 0))
                    row['response_tokens_in'] = int(row.get('response_tokens_in', 0))
                    row['response_tokens_out'] = int(row.get('response_tokens_out', 0))
                    row['response_cache_read'] = int(row.get('response_cache_read', 0))
                    row['response_cache_create'] = int(row.get('response_cache_create', 0))
                    row['tool_count'] = int(row.get('tool_count', 0))
                    row['agents_spawned'] = int(row.get('agents_spawned', 0))
                    row['cost_input_usd'] = float(row.get('cost_input_usd', 0))
                    row['cost_output_usd'] = float(row.get('cost_output_usd', 0))
                    row['cost_cache_read_usd'] = float(row.get('cost_cache_read_usd', 0))
                    row['cost_cache_write_usd'] = float(row.get('cost_cache_write_usd', 0))
                    row['cost_total_usd'] = float(row.get('cost_total_usd', 0))
                    all_main_prompts.append(row)

        if agent_csv.exists():
            with open(agent_csv, 'r', encoding='utf-8', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    row['id'] = int(row.get('id', 0))
                    row['word_count'] = int(row.get('word_count', 0))
                    row['char_count'] = int(row.get('char_count', 0))
                    row['response_tokens_in'] = int(row.get('response_tokens_in', 0))
                    row['response_tokens_out'] = int(row.get('response_tokens_out', 0))
                    row['response_cache_read'] = int(row.get('response_cache_read', 0))
                    row['response_cache_create'] = int(row.get('response_cache_create', 0))
                    row['tool_count'] = int(row.get('tool_count', 0))
                    row['agents_spawned'] = int(row.get('agents_spawned', 0))
                    row['cost_input_usd'] = float(row.get('cost_input_usd', 0))
                    row['cost_output_usd'] = float(row.get('cost_output_usd', 0))
                    row['cost_cache_read_usd'] = float(row.get('cost_cache_read_usd', 0))
                    row['cost_cache_write_usd'] = float(row.get('cost_cache_write_usd', 0))
                    row['cost_total_usd'] = float(row.get('cost_total_usd', 0))
                    all_agent_prompts.append(row)

    # Write CSVs
    if all_main_prompts:
        write_csv(all_main_prompts, main_csv)
        print(f"Wrote {len(all_main_prompts)} prompts to {main_csv}")

    if all_agent_prompts:
        write_csv(all_agent_prompts, agent_csv)
        print(f"Wrote {len(all_agent_prompts)} agent prompts to {agent_csv}")

    # Generate monthly summary
    if all_main_prompts or all_agent_prompts:
        generate_monthly_summary(all_main_prompts, all_agent_prompts, monthly_csv)

    # Show stats if requested
    if args.stats:
        print_stats(all_main_prompts, all_agent_prompts)


if __name__ == '__main__':
    main()
