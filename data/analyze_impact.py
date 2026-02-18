#!/usr/bin/env python3
"""
Analyze prompt impact by correlating Claude sessions with git commits.

Identifies high-impact prompts by:
1. Matching session timestamps to git commit timestamps
2. Calculating lines added/removed per session
3. Identifying key prompts that led to major changes

Usage:
    python analyze_impact.py                    # Full analysis
    python analyze_impact.py --top 20           # Show top 20 high-impact prompts
    python analyze_impact.py --daily            # Daily summary
    python analyze_impact.py --sessions         # Session-level analysis
"""

import argparse
import csv
import json
import subprocess
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional


def get_git_commits(repo_path: Path) -> List[Dict]:
    """Get all git commits with stats."""
    result = subprocess.run(
        ['git', 'log', '--all', '--pretty=format:%H|%aI|%s', '--numstat'],
        cwd=repo_path,
        capture_output=True,
        text=True
    )

    commits = []
    current_commit = None

    for line in result.stdout.split('\n'):
        if '|' in line and len(line.split('|')) == 3:
            # New commit header
            if current_commit:
                commits.append(current_commit)

            parts = line.split('|')
            commit_hash = parts[0]
            timestamp = parts[1]
            message = parts[2]

            current_commit = {
                'hash': commit_hash[:8],
                'timestamp': timestamp,
                'message': message,
                'additions': 0,
                'deletions': 0,
                'files_changed': 0,
            }
        elif line.strip() and current_commit:
            # Stat line: additions\tdeletions\tfilename
            parts = line.split('\t')
            if len(parts) >= 2:
                try:
                    adds = int(parts[0]) if parts[0] != '-' else 0
                    dels = int(parts[1]) if parts[1] != '-' else 0
                    current_commit['additions'] += adds
                    current_commit['deletions'] += dels
                    current_commit['files_changed'] += 1
                except ValueError:
                    pass

    if current_commit:
        commits.append(current_commit)

    return commits


def load_prompts(csv_path: Path) -> List[Dict]:
    """Load prompts from CSV."""
    prompts = []
    if not csv_path.exists():
        return prompts

    with open(csv_path, 'r', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Parse timestamp
            try:
                ts = row.get('timestamp', '')
                if ts:
                    row['datetime'] = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                else:
                    row['datetime'] = None
            except:
                row['datetime'] = None
            prompts.append(row)

    return prompts


def correlate_sessions_to_commits(prompts: List[Dict], commits: List[Dict]) -> Dict[str, Dict]:
    """
    Correlate Claude sessions to git commits.

    A session is associated with commits that occurred:
    - After the session started
    - Before the next session started (or within 2 hours if last session)
    """
    # Group prompts by session
    sessions = defaultdict(lambda: {'prompts': [], 'start': None, 'end': None})

    for p in prompts:
        session_id = p.get('session_id', '')
        if not session_id or not p['datetime']:
            continue

        sessions[session_id]['prompts'].append(p)

        if sessions[session_id]['start'] is None or p['datetime'] < sessions[session_id]['start']:
            sessions[session_id]['start'] = p['datetime']
        if sessions[session_id]['end'] is None or p['datetime'] > sessions[session_id]['end']:
            sessions[session_id]['end'] = p['datetime']

    # Sort sessions by start time
    sorted_sessions = sorted(
        [(sid, data) for sid, data in sessions.items() if data['start']],
        key=lambda x: x[1]['start']
    )

    # Parse commit timestamps
    for c in commits:
        try:
            c['datetime'] = datetime.fromisoformat(c['timestamp'])
        except:
            c['datetime'] = None

    # Associate commits with sessions
    session_commits = {}

    for i, (session_id, session_data) in enumerate(sorted_sessions):
        session_start = session_data['start']

        # Session end is either next session start or 2 hours after last prompt
        if i + 1 < len(sorted_sessions):
            session_end = sorted_sessions[i + 1][1]['start']
        else:
            session_end = session_data['end'] + timedelta(hours=2)

        # Find commits in this window
        associated_commits = []
        for c in commits:
            if c['datetime'] and session_start <= c['datetime'] < session_end:
                associated_commits.append(c)

        session_commits[session_id] = {
            'session_data': session_data,
            'commits': associated_commits,
            'total_additions': sum(c['additions'] for c in associated_commits),
            'total_deletions': sum(c['deletions'] for c in associated_commits),
            'total_files': sum(c['files_changed'] for c in associated_commits),
        }

    return session_commits


def identify_high_impact_prompts(prompts: List[Dict], session_commits: Dict[str, Dict]) -> List[Dict]:
    """
    Identify prompts that likely led to significant code changes.

    Heuristics:
    - First prompt in a high-impact session
    - Prompts with planning/implementation keywords
    - Prompts that spawned agents
    """
    high_impact = []

    # Keywords that suggest implementation work
    implementation_keywords = [
        'implement', 'add', 'create', 'build', 'fix', 'refactor', 'update',
        'system', 'component', 'service', 'feature', 'boss', 'ability',
        'network', 'damage', 'spawn', 'state', 'ui', 'menu'
    ]

    for session_id, session_data in session_commits.items():
        if not session_data['commits']:
            continue

        impact_score = (
            session_data['total_additions'] +
            session_data['total_deletions'] * 0.5 +
            session_data['total_files'] * 10
        )

        session_prompts = session_data['session_data']['prompts']

        for i, p in enumerate(session_prompts):
            prompt_text = p.get('prompt', '').lower()

            # Calculate prompt-level impact score
            prompt_score = 0

            # First prompt in session gets base score
            if i == 0:
                prompt_score += impact_score * 0.5

            # Implementation keywords boost score
            keyword_matches = sum(1 for kw in implementation_keywords if kw in prompt_text)
            prompt_score += keyword_matches * (impact_score * 0.1)

            # Agent spawns indicate complex work
            agents_spawned = int(p.get('agents_spawned', 0))
            prompt_score += agents_spawned * (impact_score * 0.2)

            # Tool usage indicates active work
            tool_count = int(p.get('tool_count', 0))
            prompt_score += tool_count * (impact_score * 0.05)

            if prompt_score > 0:
                high_impact.append({
                    'prompt': p,
                    'session_id': session_id,
                    'impact_score': prompt_score,
                    'session_additions': session_data['total_additions'],
                    'session_deletions': session_data['total_deletions'],
                    'session_files': session_data['total_files'],
                    'commit_count': len(session_data['commits']),
                    'commit_messages': [c['message'][:60] for c in session_data['commits'][:3]],
                })

    # Sort by impact score
    high_impact.sort(key=lambda x: x['impact_score'], reverse=True)

    return high_impact


def generate_daily_summary(prompts: List[Dict], commits: List[Dict]) -> Dict[str, Dict]:
    """Generate daily summary of prompts and commits."""
    daily = defaultdict(lambda: {
        'prompts': 0,
        'sessions': set(),
        'additions': 0,
        'deletions': 0,
        'commits': 0,
        'commit_messages': [],
        'categories': defaultdict(int),
        'top_prompts': [],
    })

    for p in prompts:
        date = p.get('date', '')
        if not date:
            continue

        daily[date]['prompts'] += 1
        daily[date]['sessions'].add(p.get('session_id', ''))
        daily[date]['categories'][p.get('category', 'other')] += 1

        # Track interesting prompts (non-confirmation, non-system)
        cat = p.get('category', '')
        if cat not in ('confirmation', 'system') and len(p.get('prompt', '')) > 20:
            daily[date]['top_prompts'].append(p.get('prompt', '')[:100])

    for c in commits:
        try:
            dt = datetime.fromisoformat(c['timestamp'])
            date = dt.strftime('%Y-%m-%d')
            daily[date]['additions'] += c['additions']
            daily[date]['deletions'] += c['deletions']
            daily[date]['commits'] += 1
            daily[date]['commit_messages'].append(c['message'][:50])
        except:
            pass

    # Convert sets to counts
    for date in daily:
        daily[date]['session_count'] = len(daily[date]['sessions'])
        del daily[date]['sessions']

    return dict(daily)


def print_high_impact_report(high_impact: List[Dict], top_n: int = 25):
    """Print high-impact prompts report."""
    print("\n" + "="*80)
    print("HIGH-IMPACT PROMPTS REPORT")
    print("="*80)
    print(f"\nShowing top {min(top_n, len(high_impact))} prompts by estimated code impact\n")

    for i, item in enumerate(high_impact[:top_n], 1):
        p = item['prompt']
        prompt_text = p.get('prompt', '')[:80]
        date = p.get('date', 'unknown')
        category = p.get('category', 'other')

        print(f"\n{i}. [{date}] {category.upper()}")
        print(f"   Prompt: \"{prompt_text}...\"" if len(p.get('prompt', '')) > 80 else f"   Prompt: \"{prompt_text}\"")
        print(f"   Impact: {item['impact_score']:.0f} | +{item['session_additions']} -{item['session_deletions']} lines | {item['session_files']} files | {item['commit_count']} commits")

        if item['commit_messages']:
            print(f"   Commits: {', '.join(item['commit_messages'][:2])}")

    print("\n" + "="*80)


def print_daily_summary(daily: Dict[str, Dict]):
    """Print daily summary."""
    print("\n" + "="*80)
    print("DAILY DEVELOPMENT SUMMARY")
    print("="*80)

    print(f"\n{'Date':<12} {'Prompts':>8} {'Sessions':>9} {'Commits':>8} {'Lines+':>10} {'Lines-':>10} {'Top Category':<15}")
    print("-" * 80)

    for date in sorted(daily.keys()):
        d = daily[date]

        # Find top category
        cats = d['categories']
        top_cat = max(cats.items(), key=lambda x: x[1])[0] if cats else 'none'

        lines_added = f"+{d['additions']:,}" if d['additions'] else "-"
        lines_removed = f"-{d['deletions']:,}" if d['deletions'] else "-"

        print(f"{date:<12} {d['prompts']:>8} {d['session_count']:>9} {d['commits']:>8} {lines_added:>10} {lines_removed:>10} {top_cat:<15}")

    # Totals
    print("-" * 80)
    total_prompts = sum(d['prompts'] for d in daily.values())
    total_sessions = sum(d['session_count'] for d in daily.values())
    total_commits = sum(d['commits'] for d in daily.values())
    total_additions = sum(d['additions'] for d in daily.values())
    total_deletions = sum(d['deletions'] for d in daily.values())

    print(f"{'TOTAL':<12} {total_prompts:>8} {total_sessions:>9} {total_commits:>8} {'+' + f'{total_additions:,}':>10} {'-' + f'{total_deletions:,}':>10}")
    print("\n" + "="*80)


def print_session_analysis(session_commits: Dict[str, Dict], top_n: int = 15):
    """Print session-level analysis."""
    print("\n" + "="*80)
    print("TOP CODING SESSIONS BY IMPACT")
    print("="*80)

    # Sort sessions by total changes
    sorted_sessions = sorted(
        session_commits.items(),
        key=lambda x: x[1]['total_additions'] + x[1]['total_deletions'],
        reverse=True
    )

    for i, (session_id, data) in enumerate(sorted_sessions[:top_n], 1):
        if not data['commits']:
            continue

        session_data = data['session_data']
        start = session_data['start'].strftime('%Y-%m-%d %H:%M') if session_data['start'] else 'unknown'
        prompt_count = len(session_data['prompts'])

        # Get first meaningful prompt
        first_prompt = ""
        for p in session_data['prompts']:
            if p.get('category') not in ('confirmation', 'system'):
                first_prompt = p.get('prompt', '')[:60]
                break

        print(f"\n{i}. Session started {start}")
        print(f"   First prompt: \"{first_prompt}...\"" if len(first_prompt) >= 60 else f"   First prompt: \"{first_prompt}\"")
        print(f"   {prompt_count} prompts | {len(data['commits'])} commits | +{data['total_additions']:,} -{data['total_deletions']:,} lines")

        # Show commit messages
        if data['commits']:
            print(f"   Commits: {', '.join(c['message'][:40] for c in data['commits'][:3])}")

    print("\n" + "="*80)


def write_impact_csv(high_impact: List[Dict], output_path: Path):
    """Write high-impact prompts to CSV."""
    columns = [
        'rank', 'date', 'category', 'prompt', 'impact_score',
        'session_additions', 'session_deletions', 'session_files',
        'commit_count', 'commits'
    ]

    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()

        for i, item in enumerate(high_impact, 1):
            p = item['prompt']
            writer.writerow({
                'rank': i,
                'date': p.get('date', ''),
                'category': p.get('category', ''),
                'prompt': p.get('prompt', ''),
                'impact_score': round(item['impact_score'], 1),
                'session_additions': item['session_additions'],
                'session_deletions': item['session_deletions'],
                'session_files': item['session_files'],
                'commit_count': item['commit_count'],
                'commits': '; '.join(item['commit_messages']),
            })

    print(f"\nWrote {len(high_impact)} high-impact prompts to {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Analyze prompt impact via git correlation')
    parser.add_argument('--top', '-t', type=int, default=25, help='Number of top prompts to show')
    parser.add_argument('--daily', '-d', action='store_true', help='Show daily summary')
    parser.add_argument('--sessions', '-s', action='store_true', help='Show session analysis')
    parser.add_argument('--export', '-e', action='store_true', help='Export to CSV')
    args = parser.parse_args()

    script_dir = Path(__file__).parent
    repo_path = script_dir.parent.parent  # Up to repo root (.claude/conversation-history -> .claude -> repo)

    prompts_csv = script_dir / 'prompts.csv'

    print("Loading prompts...")
    prompts = load_prompts(prompts_csv)
    print(f"Loaded {len(prompts)} prompts")

    print("Loading git history...")
    commits = get_git_commits(repo_path)
    print(f"Loaded {len(commits)} commits")

    print("Correlating sessions to commits...")
    session_commits = correlate_sessions_to_commits(prompts, commits)
    sessions_with_commits = sum(1 for s in session_commits.values() if s['commits'])
    print(f"Found {sessions_with_commits} sessions with associated commits")

    if args.daily:
        daily = generate_daily_summary(prompts, commits)
        print_daily_summary(daily)
    elif args.sessions:
        print_session_analysis(session_commits, args.top)
    else:
        print("Identifying high-impact prompts...")
        high_impact = identify_high_impact_prompts(prompts, session_commits)
        print_high_impact_report(high_impact, args.top)

        if args.export:
            output_path = script_dir / 'high_impact_prompts.csv'
            write_impact_csv(high_impact, output_path)


if __name__ == '__main__':
    main()
