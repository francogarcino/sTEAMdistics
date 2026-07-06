import json
import re
import urllib.request
import urllib.error
from pathlib import Path
from utils.config import PACKAGES, GEMINI_MODELS, MAX_TOTAL_DIFF_CHARS

PROMPTS_DIR = Path(__file__).parent.parent / 'prompts'


def _load_prompt_template(mode):
    path = PROMPTS_DIR / f"{mode}.md"
    return path.read_text(encoding='utf-8')


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


def build_prompt(author, commits, diff_summaries, team_package_stats, mode='analisis', issues=None):
    template = _load_prompt_template(mode)
    combined_diffs = "\n---\n".join(diff_summaries)[:MAX_TOTAL_DIFF_CHARS]
    team_summary = build_team_summary(team_package_stats) if team_package_stats else ""
    return template.format(
        author=author,
        commits=commits,
        team_summary=team_summary,
        diffs=combined_diffs,
        issues=issues or "",
    )


def call_gemini_api(version, model, prompt, key):
    url = f"https://generativelanguage.googleapis.com/{version}/models/{model}:generateContent?key={key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 4096, "temperature": 0.1},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
        candidate = data['candidates'][0]
        text = candidate['content']['parts'][0]['text'].strip()
        if candidate.get('finishReason', 'STOP') == 'MAX_TOKENS':
            text += ' *(respuesta truncada — aumentar maxOutputTokens)*'
        return text


def analyze_participation_with_ai(author, commits, diff_summaries, api_key, team_package_stats=None, mode='analisis', issues=None):
    if not api_key:
        return "**[IA] Error: Sin API Key.**"

    key = re.sub(r'[^a-zA-Z0-9_\-]', '', api_key)
    prompt = build_prompt(author, commits, diff_summaries, team_package_stats, mode, issues=issues)

    last_error = None
    for ver, mod in GEMINI_MODELS:
        try:
            return call_gemini_api(ver, mod, prompt, key)
        except urllib.error.HTTPError as e:
            last_error = e
        except Exception as e:
            last_error = e

    return f"**[IA] Error persistente:** {last_error}. Verificá que la 'Generative Language API' esté habilitada en tu proyecto de Cloud Console."
