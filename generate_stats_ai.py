#!/usr/bin/env python3
"""
EPERS Tag Statistics Generator - LOCAL TEACHER EDITION (V3.6)
Audit tool for instructors. Generates a PRIVATE local report with AI analysis.
"""

import subprocess
import os
import re
import json
import argparse
import urllib.request
import urllib.error
import random
from collections import defaultdict
from datetime import datetime

# --- Configuración de paquetes EXACTA ---
PACKAGES = [
    'model/modelo',
    'persistence/persistencia',
    'service/servicio',
    'test',
    'utils/otros',
    'controller',
]

PACKAGE_PATTERNS = [
    ('test',                     lambda p: 'src/test' in p),
    ('model/modelo',             lambda p: '/modelo/' in p or '/model/' in p),
    ('persistence/persistencia', lambda p: '/persistencia/' in p or '/persistence/' in p),
    ('service/servicio',         lambda p: '/servicios/' in p or '/service/' in p),
    ('controller',               lambda p: '/controller/' in p or '/controllers/' in p or '/webservice' in p),
    ('utils/otros',              lambda p: True),
]

GEMINI_MODELS = [
    ("v1beta", "gemini-2.5-flash"),
    ("v1beta", "gemini-2.0-flash"),
    ("v1beta", "gemini-2.0-flash-lite"),
]


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    return result.stdout.strip()

def map_file_to_package(filepath):
    for pkg, matches in PACKAGE_PATTERNS:
        if matches(filepath):
            return pkg
    return 'utils/otros'

def make_bar(percentage, width=10):
    filled = max(0, min(width, round(percentage / (100 / width))))
    return '▓' * filled + '░' * (width - filled)

def make_anchor(name):
    return re.sub(r'[^\w\s-]', '', name.lower()).strip().replace(' ', '-')

def empty_author_entry():
    return {
        'added': 0,
        'deleted': 0,
        'packages': {pkg: {'added': 0, 'deleted': 0} for pkg in PACKAGES},
        'commits': [],
        'diff_summary': [],
    }

def merge_stats(target, source):
    target['added'] += source['added']
    target['deleted'] += source['deleted']
    target['commits'].extend(source['commits'])
    target['diff_summary'].extend(source['diff_summary'])
    for p in PACKAGES:
        target['packages'][p]['added'] += source['packages'][p]['added']
        target['packages'][p]['deleted'] += source['packages'][p]['deleted']


# ---------------------------------------------------------------------------
# Recolección de datos Git
# ---------------------------------------------------------------------------

def get_sorted_tags():
    output = run("git tag --sort=creatordate")
    return [t for t in output.split('\n') if t.strip()]

def get_git_stats(commit_range, collect_diffs=False):
    by_email = {}
    name_counts = defaultdict(lambda: defaultdict(int))

    def ensure(email):
        if email not in by_email:
            by_email[email] = empty_author_entry()
        return by_email[email]

    # Recolectar commits y nombres
    log_cmd = f"git log --no-merges --format='%an|||%ae|||%s' {commit_range}"
    for line in run(log_cmd).split('\n'):
        parts = line.split('|||', 2)
        if len(parts) == 3:
            name, email, message = (p.strip() for p in parts)
            if email:
                name_counts[email][name] += 1
                if 'merge' not in message.lower():
                    ensure(email)['commits'].append(message)

    # Recolectar líneas modificadas (y opcionalmente diffs)
    numstat_cmd = f"git log --no-merges --numstat --format='COMMIT|||%ae|||%H' {commit_range}"
    current_email = None
    for line in run(numstat_cmd).split('\n'):
        if line.startswith('COMMIT|||'):
            parts = line.split('|||', 2)
            if len(parts) == 3:
                current_email, commit_hash = parts[1], parts[2]
                entry = ensure(current_email)
                if collect_diffs and len(entry['diff_summary']) < 15:
                    diff = run(f"git show --format='' --stat --patch {commit_hash}")
                    entry['diff_summary'].append(diff[:1500])
        elif line and current_email and '\t' in line:
            parts = line.split('\t', 2)
            if len(parts) == 3 and parts[0] != '-' and parts[1] != '-':
                try:
                    added, deleted, filepath = int(parts[0]), int(parts[1]), parts[2].strip()
                    s = ensure(current_email)
                    s['added'] += added
                    s['deleted'] += deleted
                    pkg = map_file_to_package(filepath)
                    s['packages'][pkg]['added'] += added
                    s['packages'][pkg]['deleted'] += deleted
                except ValueError:
                    pass

    # Unificar entradas del mismo autor por email
    raw_stats = {}
    for email, data in by_email.items():
        canonical = max(name_counts[email], key=lambda n: name_counts[email][n])
        if canonical not in raw_stats:
            raw_stats[canonical] = data
        else:
            merge_stats(raw_stats[canonical], data)

    # Unificar nombres parcialmente iguales (ej: "Juan" y "Juan Pérez")
    final_stats = {}
    for name in sorted(raw_stats.keys(), key=len, reverse=True):
        match = next(
            (t for t in final_stats if name.lower() in t.lower() or t.lower() in name.lower()),
            None
        )
        if match:
            merge_stats(final_stats[match], raw_stats[name])
        else:
            final_stats[name] = raw_stats[name]

    return final_stats


# ---------------------------------------------------------------------------
# API de IA
# ---------------------------------------------------------------------------

def call_gemini_api(version, model, prompt, key):
    url = f"https://generativelanguage.googleapis.com/{version}/models/{model}:generateContent?key={key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 4096, "temperature": 0.1},
    }
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
            candidate = data['candidates'][0]
            text = candidate['content']['parts'][0]['text'].strip()
            if candidate.get('finishReason', 'STOP') == 'MAX_TOKENS':
                text += ' *(respuesta truncada — aumentar maxOutputTokens)*'
            return text
    except urllib.error.HTTPError as e:
        return f"ERROR_HTTP_{e.code}"
    except Exception as e:
        return f"ERROR_{str(e)}"

def build_team_summary(team_package_stats):
    lines = []
    for mate, pkgs in team_package_stats.items():
        total = sum(pkgs[p]['added'] + pkgs[p]['deleted'] for p in PACKAGES) or 1
        dist = ", ".join(
            f"{p}={round((pkgs[p]['added'] + pkgs[p]['deleted']) / total * 100)}%"
            for p in PACKAGES
        )
        lines.append(f"  - {mate}: {dist}")
    return "Distribución por capas del equipo (para comparar):\n" + "\n".join(lines)

def build_prompt(author, commits, diff_summaries, team_package_stats):
    combined_diffs = "\n---\n".join(diff_summaries)[:10000]
    team_summary = build_team_summary(team_package_stats) if team_package_stats else ""
    return (
        f"Eres un profesor universitario auditando la participación de '{author}' en un proyecto Java en equipo. "
        f"Respondé en español con exactamente 4 oraciones completas, en prosa corrida, sin listas ni subtítulos.\n\n"
        f"Las 4 oraciones deben cubrir, en orden:\n"
        f"1. Qué clases y capas tocó realmente.\n"
        f"2. Si los mensajes de commit son descriptivos o genéricos — ¿hay señales de deshonestidad?\n"
        f"3. Si participó en todas las capas o se especializó; comparalo con sus compañeros e indicá si hay desequilibrio preocupante.\n"
        f"4. Si hay commits repetidos sobre lo mismo: ¿se trabó con una implementación o infló su actividad artificialmente?\n\n"
        f"Commits de '{author}': {commits[:20]}\n\n"
        f"{team_summary}\n\n"
        f"Diffs:\n{combined_diffs}"
    )

def analyze_participation_with_ai(author, commits, diff_summaries, api_keys, team_package_stats=None):
    if not api_keys:
        return "**[IA] Error: Sin API Key.**"

    key = re.sub(r'[^a-zA-Z0-9_\-]', '', random.choice(api_keys))
    prompt = build_prompt(author, commits, diff_summaries, team_package_stats)

    for ver, mod in GEMINI_MODELS:
        res = call_gemini_api(ver, mod, prompt, key)
        if "ERROR_HTTP" not in res and "ERROR_" not in res:
            return res

    return "**[IA] Error 404 persistente:** Google no encuentra el modelo en tu región. Verifica que la 'Generative Language API' esté habilitada en tu proyecto de Cloud Console."


# ---------------------------------------------------------------------------
# Generación del reporte Markdown
# ---------------------------------------------------------------------------

def render_summary_table(authors, stats):
    total_activity = sum(stats[a]['added'] + stats[a]['deleted'] for a in authors)
    lines = [
        "## Tabla Comparativa (Actividad Total)\n",
        "| Usuario | Added | Deleted | Balance | Actividad (%) |",
        "|---------|-------|---------|---------|---------------|",
    ]
    for author in authors:
        a, d = stats[author]['added'], stats[author]['deleted']
        act = a + d
        pct = round((act / total_activity * 100)) if total_activity > 0 else 0
        link = f"[{author}](#{make_anchor(author)})"
        balance = f"{'+' if a - d >= 0 else ''}{a - d}"
        lines.append(f"| {link} | {a} | {d} | {balance} | {pct}% {make_bar(pct)} |")
    return "\n".join(lines)

def render_author_section(author, s, ai_enabled, ai_keys, team_package_stats):
    lines = [f"### {author}", "---"]

    if ai_enabled and ai_keys:
        analysis = analyze_participation_with_ai(
            author, s['commits'], s['diff_summary'], ai_keys, team_package_stats
        )
        lines.append(analysis)
        lines.append("")

    lines.append("**Distribución por Package:**\n")
    total_p = s['added'] + s['deleted']
    for pkg in PACKAGES:
        pa, pd = s['packages'][pkg]['added'], s['packages'][pkg]['deleted']
        p_act = pa + pd
        pct = round(p_act / total_p * 100) if total_p > 0 else 0
        lines.append(f"- `{pkg}`: {pct}% {make_bar(pct)} (A: {pa} / D: {pd})")
    lines.append("")
    return "\n".join(lines)

def generate_markdown(repo_name, run_date, period, stats, ai_enabled=False, ai_keys=None):
    authors = sorted(stats.keys())
    team_package_stats = {a: stats[a]['packages'] for a in authors}

    sections = [
        f"# [EPERS] Reporte Docente: {repo_name}",
        f"Fecha: {run_date} | Periodo: {period}",
        "> **CONFIDENCIAL:** Auditoría interna de cátedra.\n",
        "---\n",
        render_summary_table(authors, stats),
        "\n## Detalle Individual\n",
    ]

    for author in authors:
        if ai_enabled and ai_keys:
            print(f"  → Analizando {author}...")
        sections.append(render_author_section(
            author, stats[author], ai_enabled, ai_keys, team_package_stats
        ))

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(add_help=False)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-h', '--head', action='store_true')
    group.add_argument('-t', '--tag', action='store_true')
    parser.add_argument('--ai', action='store_true')
    args = parser.parse_args()

    raw = os.environ.get('EPERS_STATS_AI_KEYS', '') or run("git config --get epers.ai-keys")
    api_keys = [k.strip() for k in raw.split(',') if k.strip()]

    tags = get_sorted_tags()
    if args.head:
        if not tags:
            raise SystemExit("No hay tags.")
        commit_range, period = f"{tags[-1]}..HEAD", f"{tags[-1]} → HEAD"
    else:
        if len(tags) < 2:
            raise SystemExit("Faltan tags.")
        commit_range, period = f"{tags[-2]}..{tags[-1]}", f"{tags[-2]} → {tags[-1]}"

    print(f"Analizando {period}...")
    stats = get_git_stats(commit_range, collect_diffs=args.ai)

    repo_name = run("basename $(git rev-parse --show-toplevel)")
    run_date = datetime.now().strftime('%Y-%m-%d')
    md = generate_markdown(repo_name, run_date, period, stats, ai_enabled=args.ai, ai_keys=api_keys)

    filename = f"{repo_name}-stats-{run_date}.md"
    with open(filename, 'w') as f:
        f.write(md)
    print(f"[OK] Reporte generado: {filename}")


if __name__ == '__main__':
    main()
