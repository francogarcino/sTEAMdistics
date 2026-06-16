#!/usr/bin/env python3
import os
import argparse
from datetime import datetime
from utils.git import run, get_sorted_tags, get_git_stats
from utils.gemini import analyze_participation_with_ai
from utils.report import generate_markdown


def main():
    parser = argparse.ArgumentParser(description='Auditoría de participación Git con análisis de IA.')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-H', '--tag-to-head', action='store_true',
                       help='Analiza desde el último tag hasta HEAD. Ideal para entregas parciales.')
    group.add_argument('-T', '--tag-to-tag', action='store_true',
                       help='Analiza entre los últimos dos tags. Ideal para entregas finales.')
    parser.add_argument('--ai', action='store_true',
                        help='Activa el análisis de integridad con Gemini (requiere API Key configurada).')
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
    if args.tag_to_head:
        if not tags:
            raise SystemExit("Error: no se encontraron tags en este repositorio.")
        commit_range, period = f"{tags[-1]}..HEAD", f"{tags[-1]} → HEAD"
    else:
        if len(tags) < 2:
            raise SystemExit("Error: se necesitan al menos dos tags para el modo tag-to-tag.")
        commit_range, period = f"{tags[-2]}..{tags[-1]}", f"{tags[-2]} → {tags[-1]}"

    print(f"Analizando {period}...")
    stats = get_git_stats(commit_range, collect_diffs=bool(api_key))

    analyses = {}
    if api_key:
        team_package_stats = {a: stats[a]['packages'] for a in stats}
        for author in sorted(stats.keys()):
            print(f"  → Analizando {author}...")
            s = stats[author]
            analyses[author] = analyze_participation_with_ai(
                author, s['commits'], s['diff_summary'], api_key, team_package_stats
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
