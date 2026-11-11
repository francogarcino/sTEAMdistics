import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock
from steamdistics import orchestrator
from steamdistics.gemini import AiResult
from tests.helpers import COURSE_CONFIG, RepoBuilder, utc

NOW = utc('2026-05-20T12:00:00+00:00')
REPO = 'catedra/equipo1-TP'


class FakeGitHub:
    def __init__(self, token):
        self.token = token

    def commit_logins(self, owner, name, head, base=None):
        return {}

    def team_members(self, org, slug):
        return ['anag', 'beto']

    def issues(self, owner, name):
        return []

    def issue_closer(self, owner, name, number):
        return None


def ai_answer(prompt, api_key, config):
    return AiResult({'integrantes': [{'alias': 'Integrante A', 'capas': 'Integrante A trabajó en persistencia.',
                                      'integridad': 'ok', 'gitflow': 'ok'}],
                     'issues': [], 'observaciones_equipo': 'Equipo desparejo.'}, 'modelo-1', None)


class ValidateInputsTest(unittest.TestCase):
    def test_rechaza_entradas_invalidas(self):
        for repo, tag in (('catedra/otro-repo', 'v1'), ('otra-org/equipo1-TP', 'v1'),
                          ('catedra/equipo1-TP', '-v1'), ('catedra/equipo1-TP', 'v1;rm -rf'),
                          ('catedra/equipo1-TP', '../v1'), ('catedra/../x-TP', 'v1')):
            with self.assertRaises(orchestrator.Ignored, msg=f'{repo} {tag}'):
                orchestrator.validate_inputs(repo, tag, 'catedra', COURSE_CONFIG)

    def test_acepta_repo_de_equipo(self):
        self.assertEqual(orchestrator.validate_inputs(REPO, 'entrega/1.0', 'catedra', COURSE_CONFIG),
                         ('catedra', 'equipo1-TP', 'equipo1'))


class AnalyzeLatestTagTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.team_repo = RepoBuilder(base / 'equipo')
        self.reports = base / 'reportes'
        self.reports.mkdir()
        self.team_repo.commit({'src/main/java/dao/A.java': 'class A {}\n'}, 'agrega dao',
                              author=('Ana Gomez', '1+anag@users.noreply.github.com'),
                              date='2026-05-01T10:00:00+00:00')
        self.team_repo.tag('entrega-1', date='2026-05-01T11:00:00+00:00')
        self.team_repo.commit({'src/main/java/service/S.java': 'class S {}\n'}, 'agrega servicio',
                              author=('Ana Gomez', '1+anag@users.noreply.github.com'),
                              date='2026-05-10T10:00:00+00:00')
        self.team_repo.tag('entrega-2', date='2026-05-10T11:00:00+00:00')
        patches = [
            mock.patch.object(orchestrator, 'clone_bare', self.local_clone),
            mock.patch.object(orchestrator, 'GitHubClient', FakeGitHub),
            mock.patch('steamdistics.pipeline.gemini.analyze', side_effect=ai_answer),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def local_clone(self, repo, token, dest):
        subprocess.run(['git', 'clone', '-q', '--bare', str(self.team_repo.path), str(dest)], check=True)

    def analyze(self, tag):
        with tempfile.TemporaryDirectory() as workdir:
            return orchestrator.analyze_latest_tag(REPO, tag, self.reports, 'token', 'key', 'catedra', NOW, workdir)

    def report_file(self, tag):
        return self.reports / str(COURSE_CONFIG.year) / COURSE_CONFIG.name / 'equipo1' / f'{tag}.md'

    def test_genera_reporte_del_ultimo_tag_contra_el_anterior(self):
        self.assertTrue(self.analyze('entrega-2'))
        report = self.report_file('entrega-2').read_text()
        self.assertIn('**Rango:** entrega-1 → entrega-2', report)
        self.assertIn('Ana Gomez trabajó en persistencia.', report)
        self.assertIn('Sin actividad en el período: beto', report)
        self.assertNotIn('agrega dao', report)
        state = json.loads((self.reports / 'state' / 'catedra__equipo1-TP.json').read_text())
        self.assertTrue(state['entrega-2']['ia_completa'])

    def test_tag_anterior_al_ultimo_se_ignora(self):
        with self.assertRaisesRegex(orchestrator.Ignored, 'no es el último'):
            self.analyze('entrega-1')

    def test_tag_inexistente_se_ignora(self):
        with self.assertRaisesRegex(orchestrator.Ignored, 'no existe'):
            self.analyze('entrega-9')

    def test_mismo_tag_y_mismo_commit_no_se_reanaliza(self):
        self.analyze('entrega-2')
        with self.assertRaisesRegex(orchestrator.Ignored, 'ya fue analizado'):
            self.analyze('entrega-2')

    def test_tag_movido_se_reanaliza_con_aviso(self):
        self.analyze('entrega-2')
        self.team_repo.commit({'README.md': 'x\n'}, 'otro', date='2026-05-11T10:00:00+00:00')
        self.team_repo.tag('entrega-2', force=True, date='2026-05-11T11:00:00+00:00')
        self.analyze('entrega-2')
        self.assertIn('Tag movido', self.report_file('entrega-2').read_text())

    def test_sin_ia_se_puede_completar_despues(self):
        failed_ai = AiResult(None, None, 'modelo-1: cuota diaria agotada')
        with mock.patch('steamdistics.pipeline.gemini.analyze', return_value=failed_ai):
            self.assertFalse(self.analyze('entrega-2'))
        self.assertIn('Análisis IA no disponible', self.report_file('entrega-2').read_text())
        self.assertTrue(self.analyze('entrega-2'))


class FakeGitHubWithIssues(FakeGitHub):
    def issues(self, owner, name):
        return [{'number': 7, 'title': 'DAO sin transacción', 'body': 'falta', 'state': 'closed',
                 'labels': [{'name': 'Grave'}], 'user': {'login': 'profe'},
                 'created_at': '2026-05-02T00:00:00Z', 'closed_at': '2026-05-09T00:00:00Z'}]

    def issue_closer(self, owner, name, number):
        return 'anag'


class ReentregaFlowTest(AnalyzeLatestTagTest):
    def setUp(self):
        super().setUp()
        patch = mock.patch.object(orchestrator, 'GitHubClient', FakeGitHubWithIssues)
        patch.start()
        self.addCleanup(patch.stop)

    def test_issue_cerrado_por_alumno_aparece_con_quien_lo_cerro(self):
        self.analyze('entrega-2')
        report = self.report_file('entrega-2').read_text()
        self.assertIn('## Reentrega', report)
        self.assertIn('| #7 DAO sin transacción | Grave | cerrado | anag |', report)
        self.assertIn('La lista de docentes está vacía', report)


class MainTest(unittest.TestCase):
    def test_error_inesperado_no_se_imprime_y_queda_en_reportes(self):
        with tempfile.TemporaryDirectory() as reports, \
                mock.patch.dict('os.environ', {'GH_TOKEN': 't', 'GEMINI_API_KEY': 'k',
                                               'GITHUB_REPOSITORY_OWNER': 'catedra'}), \
                mock.patch.object(orchestrator, 'clone_bare', side_effect=RuntimeError('detalle secreto')):
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = orchestrator.main(['--repo', REPO, '--tag', 'v1', '--reportes', reports])
            self.assertEqual(exit_code, 1)
            self.assertNotIn('detalle secreto', output.getvalue())
            [log] = (Path(reports) / 'errores').rglob('*.log')
            self.assertIn('detalle secreto', log.read_text())

    def test_entrada_ignorada_termina_sin_error(self):
        with tempfile.TemporaryDirectory() as reports, \
                mock.patch.dict('os.environ', {'GH_TOKEN': 't', 'GEMINI_API_KEY': 'k',
                                               'GITHUB_REPOSITORY_OWNER': 'catedra'}):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(orchestrator.main(['--repo', 'catedra/otro', '--tag', 'v1', '--reportes', reports]), 0)


if __name__ == '__main__':
    unittest.main()
