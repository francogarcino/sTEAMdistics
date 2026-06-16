#!/usr/bin/env python3
import os
import argparse
from datetime import datetime
from utils.git import run, get_sorted_tags, get_git_stats
from utils.gemini import analyze_participation_with_ai
from utils.report import generate_markdown


def pick_range_interactively(tags):
    options = tags + ['HEAD']
    print("Tags disponibles:")
    for i, t in enumerate(options):
        print(f"  [{i}] {t}")
    print()

    max_idx = len(options) - 1

    def ask(label):
        while True:
            raw = input(f"{label} [0-{max_idx}]: ").strip()
            if raw.isdigit() and 0 <= int(raw) <= max_idx:
                return int(raw)
            print(f"  Ingresá un número entre 0 y {max_idx}.")

    start_idx = ask("Desde")
    end_idx   = ask("Hasta ")

    if options[start_idx] == 'HEAD':
        raise SystemExit("Error: el rango no puede comenzar desde HEAD.")
    if start_idx >= end_idx:
        raise SystemExit("Error: 'Desde' debe ser anterior a 'Hasta'.")

    start_ref = options[start_idx]
    end_ref   = options[end_idx]
    commit_range = f"{start_ref}..{end_ref}"
    period       = f"{start_ref} → {end_ref}"
    return commit_range, period


def resolve_range(args, tags):
    if args.tag_to_head:
        if not tags:
            raise SystemExit("Error: no se encontraron tags en este repositorio.")
        return f"{tags[-1]}..HEAD", f"{tags[-1]} → HEAD", 'analisis'

    if args.tag_to_tag:
        if len(tags) < 2:
            raise SystemExit("Error: se necesitan al menos dos tags para -T.")
        return f"{tags[-2]}..{tags[-1]}", f"{tags[-2]} → {tags[-1]}", 'analisis'

    if args.reentrega:
        if len(tags) < 2:
            raise SystemExit("Error: se necesitan al menos dos tags para -R.")
        return f"{tags[-2]}..{tags[-1]}", f"{tags[-2]} → {tags[-1]}", 'reentrega'

    if not tags:
        raise SystemExit("Error: no se encontraron tags en este repositorio.")
    commit_range, period = pick_range_interactively(tags)
    return commit_range, period, 'analisis'


def main():
    parser = argparse.ArgumentParser(
        description='Auditoría de participación Git con análisis de IA.',
        epilog='Sin modificador: lista los tags y permite elegir el rango de forma interactiva.',
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-H', '--tag-to-head', action='store_true',
                       help='Último tag → HEAD.')
    group.add_argument('-T', '--tag-to-tag', action='store_true',
                       help='Penúltimo tag → último tag.')
    group.add_argument('-R', '--reentrega', action='store_true',
                       help='Penúltimo tag → último tag, con prompt de reentrega.')
    parser.add_argument('--ai', action='store_true',
                        help='Activa el análisis con Gemini (requiere API Key configurada).')
    args = parser.parse_args()

    api_key = None
    if args.ai:
        try:
            api_key = os.environ.get('STEAMDISTICS_AI_KEY', '') or run(["git", "config", "--get", "sTEAMdistics.ai-key"])
        except RuntimeError:
            api_key = ''
        if not api_key:
            raise SystemExit(
                "Error: --ai requiere una API Key de Gemini.\n"
                "Configurala con: git config --global sTEAMdistics.ai-key \"TU_CLAVE\"\n"
                "O definí la variable de entorno: STEAMDISTICS_AI_KEY=\"TU_CLAVE\""
            )

    tags = get_sorted_tags()
    commit_range, period, mode = resolve_range(args, tags)

    print(f"Analizando {period}...")
    stats = get_git_stats(commit_range, collect_diffs=bool(api_key))

    analyses = {}
    if api_key:
        team_package_stats = {a: stats[a]['packages'] for a in stats}
        for author in sorted(stats.keys()):
            print(f"  → Analizando {author}...")
            s = stats[author]
            analyses[author] = analyze_participation_with_ai(
                author, s['commits'], s['diff_summary'], api_key, team_package_stats, mode
            )

    repo_name = os.path.basename(run(["git", "rev-parse", "--show-toplevel"]))
    run_date = datetime.now().strftime('%Y-%m-%d')
    md = generate_markdown(repo_name, run_date, period, stats, analyses=analyses)

    filename = f"{repo_name}-stats-{run_date}.md"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(md)
    print(f"[OK] Reporte generado: {filename}")


if __name__ == '__main__':
    main()
