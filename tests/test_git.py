import tempfile
import unittest
from steamdistics.gitlog import read_commits, read_merges, parse_patch
from steamdistics.gitrepo import latest_tag_range, tags_by_creation
from tests.helpers import ANALYSIS_CONFIG, RepoBuilder

DAO = 'src/main/java/ar/unq/dao/PersonajeDAO.java'
SERVICE = 'src/main/java/ar/unq/service/PersonajeService.java'


class LatestTagRangeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = RepoBuilder(self.tmp.name)
        self.repo.commit({'a.txt': 'uno\n'}, 'inicial', date='2026-04-01T10:00:00+00:00')
        self.repo.tag('entrega-1', date='2026-04-01T11:00:00+00:00')
        self.repo.commit({'a.txt': 'uno\ndos\n'}, 'segunda', date='2026-04-10T10:00:00+00:00')
        self.repo.tag('entrega-2', date='2026-04-10T11:00:00+00:00')

    def tearDown(self):
        self.tmp.cleanup()

    def test_ultimo_tag_se_analiza_contra_el_anterior(self):
        tag_range = latest_tag_range(self.repo.path, 'entrega-2')
        self.assertEqual(tag_range.previous, 'entrega-1')
        self.assertEqual(tag_range.rev_range, f"{tag_range.previous_sha}..{tag_range.tag_sha}")

    def test_tag_que_no_es_el_ultimo_no_se_analiza(self):
        self.assertIsNone(latest_tag_range(self.repo.path, 'entrega-1'))

    def test_orden_por_fecha_de_creacion_y_no_por_nombre(self):
        self.repo.tag('a-reentrega', date='2026-04-20T11:00:00+00:00')
        self.assertEqual(tags_by_creation(self.repo.path)[-1], 'a-reentrega')

    def test_primer_tag_se_analiza_desde_la_raiz(self):
        fresh_dir = tempfile.TemporaryDirectory()
        self.addCleanup(fresh_dir.cleanup)
        single_tag_repo = RepoBuilder(fresh_dir.name)
        single_tag_repo.commit({'a.txt': 'x\n'}, 'inicial')
        single_tag_repo.tag('v1')
        tag_range = latest_tag_range(single_tag_repo.path, 'v1')
        self.assertIsNone(tag_range.previous)
        self.assertEqual(tag_range.rev_range, tag_range.tag_sha)
        self.assertEqual(tag_range.label, 'inicio del repo → v1')


class ReadCommitsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = RepoBuilder(self.tmp.name)
        self.base = self.repo.commit({DAO: 'class PersonajeDAO {\n    void guardar() {}\n}\n'}, 'base')

    def tearDown(self):
        self.tmp.cleanup()

    def read(self):
        return read_commits(self.repo.path, f"{self.base}..HEAD", ANALYSIS_CONFIG)

    def test_lineas_en_blanco_no_cuentan(self):
        self.repo.commit({SERVICE: 'class S {\n\n\n    int x;\n}\n'}, 'agrega servicio')
        [commit] = self.read()
        self.assertEqual((commit.added, commit.deleted), (3, 0))
        self.assertEqual(commit.files[0].layer, 'servicio')

    def test_reindentado_no_cuenta(self):
        self.repo.commit({DAO: 'class PersonajeDAO {\n        void guardar() {}\n}\n'}, 'reindenta')
        [commit] = self.read()
        self.assertEqual((commit.added, commit.deleted), (0, 0))

    def test_archivos_generados_no_cuentan_ni_van_al_diff(self):
        self.repo.commit({'target/classes/X.class': 'binario\n' * 50, SERVICE: 'class S {}\n'}, 'compila')
        [commit] = self.read()
        self.assertEqual(commit.added, 1)
        self.assertEqual([f.path for f in commit.counted_files], [SERVICE])

    def test_archivo_borrado_se_atribuye_a_su_capa(self):
        self.repo.commit({DAO: None}, 'borra dao')
        [commit] = self.read()
        self.assertEqual((commit.files[0].path, commit.files[0].layer), (DAO, 'persistencia'))
        self.assertEqual(commit.deleted, 3)

    def test_lineas_de_sql_que_empiezan_con_guiones_se_cuentan_como_contenido(self):
        sql_path = 'src/main/resources/data.sql'
        self.repo.commit({sql_path: '-- a/comentario\n+++ b/raro\nSELECT 1;\n'}, 'agrega sql',
                         date='2026-05-02T10:00:00+00:00')
        self.repo.commit({sql_path: 'SELECT 2;\n'}, 'cambia sql', date='2026-05-03T10:00:00+00:00')
        commits = read_commits(self.repo.path, f"{self.base}..HEAD", ANALYSIS_CONFIG)
        self.assertEqual([(c.added, c.deleted) for c in commits], [(3, 0), (1, 3)])
        self.assertEqual({f.path for c in commits for f in c.files}, {sql_path})

    def test_co_autores_y_revert(self):
        self.repo.commit({SERVICE: 'class S {}\n'}, 'Revert "algo"', co_authors=[('Beto Diaz', 'Beto@Example.com')])
        [commit] = self.read()
        self.assertEqual(commit.co_authors, [('Beto Diaz', 'beto@example.com')])
        self.assertTrue(commit.is_revert)

    def test_merges_se_leen_aparte(self):
        self.repo.branch('feature')
        self.repo.commit({SERVICE: 'class S {}\n'}, 'agrega servicio')
        self.repo.checkout('main')
        self.repo.merge('feature', author=('Beto Diaz', 'beto@example.com'))
        self.assertEqual(len(self.read()), 1)
        [merge] = read_merges(self.repo.path, f"{self.base}..HEAD")
        self.assertEqual(merge.author_email, 'beto@example.com')


class ParsePatchTest(unittest.TestCase):
    def test_diff_guarda_encabezados_de_hunk_y_lineas(self):
        patch = '\n'.join([
            f'diff --git a/{SERVICE} b/{SERVICE}',
            'index 1..2 100644',
            f'--- a/{SERVICE}',
            f'+++ b/{SERVICE}',
            '@@ -1 +1,2 @@ class S',
            '-int x;',
            '+int y;',
            '+int z;',
        ])
        [change] = parse_patch(patch, ANALYSIS_CONFIG)
        self.assertEqual((change.added, change.deleted), (2, 1))
        self.assertEqual(change.patch[0], '@@ -1 +1,2 @@ class S')


if __name__ == '__main__':
    unittest.main()
