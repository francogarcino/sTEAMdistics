import re
from utils.config import PACKAGES


def make_bar(percentage, width=10):
    filled = max(0, min(width, round(percentage * width / 100)))
    return '▓' * filled + '░' * (width - filled)


def make_anchor(name):
    return re.sub(r'[^\w\s-]', '', name.lower()).strip().replace(' ', '-')


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


def render_author_section(author, s, analysis=None):
    lines = [f"### {author}", "---"]

    if analysis:
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


def generate_markdown(repo_name, run_date, period, stats, analyses=None):
    authors = sorted(stats.keys())

    sections = [
        f"# Reporte de Participación: {repo_name}",
        f"Fecha: {run_date} | Periodo: {period}",
        "> **CONFIDENCIAL:** Auditoría técnica de contribuciones.\n",
        "---\n",
        render_summary_table(authors, stats),
        "\n## Detalle Individual\n",
    ]

    for author in authors:
        sections.append(render_author_section(
            author, stats[author], analysis=(analyses or {}).get(author)
        ))

    return "\n".join(sections)
