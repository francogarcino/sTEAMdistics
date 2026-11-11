import unittest
from steamdistics.context import TRUNCATED_MARK, assign_aliases, build_scrubber, commit_block, fit_budget
from steamdistics.identity import group_members
from steamdistics.reentrega import format_issues_for_prompt, select_correction_issues
from tests.helpers import make_change, make_commit, utc


class FitBudgetTest(unittest.TestCase):
    def test_entra_completo_si_no_supera_el_presupuesto(self):
        blocks = ['a' * 10, 'b' * 20]
        self.assertEqual(fit_budget(blocks, 100), (blocks, False))

    def test_recorta_solo_los_bloques_grandes(self):
        small_block, huge_block = 'a' * 100, 'b' * 5000
        fitted, truncated = fit_budget([small_block, huge_block], 1000)
        self.assertTrue(truncated)
        self.assertEqual(fitted[0], small_block)
        self.assertTrue(fitted[1].endswith(TRUNCATED_MARK))
        self.assertLessEqual(sum(len(b) for b in fitted), 1000)


class CommitBlockTest(unittest.TestCase):
    def test_incluye_commit_archivo_y_capa(self):
        commit = make_commit(sha='abcdef1234' + '0' * 30, subject='agrega dao',
                             files=[make_change('dao/A.java', 'persistencia', 1, 0, patch=['@@ -0,0 +1 @@', '+x'])])
        block = commit_block(commit)
        self.assertIn('=== abcdef12', block)
        self.assertIn('"agrega dao"', block)
        self.assertIn('--- dao/A.java [persistencia]', block)


class ScrubberTest(unittest.TestCase):
    def test_reemplaza_nombres_emails_y_logins_por_alias(self):
        members = group_members([make_commit()], logins_by_sha={'a' * 40: 'anag'})
        aliases = assign_aliases(members)
        scrub = build_scrubber(members, aliases)
        self.assertEqual(scrub('fix de ANA GOMEZ (ana@example.com, @anag)'),
                         'fix de Integrante A (Integrante A, @Integrante A)')

    def test_no_reemplaza_dentro_de_otras_palabras(self):
        members = group_members([make_commit()], logins_by_sha={'a' * 40: 'ana'})
        scrub = build_scrubber(members, assign_aliases(members))
        self.assertEqual(scrub('List<Banana> bananas; // ana'), 'List<Banana> bananas; // Integrante A')


def raw_issue(number, labels, author='profe', state='open', created='2026-05-01T00:00:00Z', closed=None):
    return {'number': number, 'title': f'issue {number}', 'body': 'detalle', 'state': state,
            'labels': [{'name': name} for name in labels], 'user': {'login': author},
            'created_at': created, 'closed_at': closed}


class SelectCorrectionIssuesTest(unittest.TestCase):
    def test_filtra_por_severidad_docente_y_fechas_y_ordena(self):
        issues = [
            raw_issue(1, ['Menor']),
            raw_issue(2, ['Grave']),
            raw_issue(3, ['Grave'], author='alumno'),
            raw_issue(4, ['bug']),
            raw_issue(5, ['Observación'], state='closed', closed='2026-04-01T00:00:00Z'),
            raw_issue(6, ['Corregir'], state='closed', closed='2026-05-05T00:00:00Z'),
            raw_issue(7, ['Grave'], created='2026-06-01T00:00:00Z'),
        ]
        selected = select_correction_issues(issues, frozenset({'profe'}),
                                            created_before=utc('2026-05-10T00:00:00+00:00'),
                                            closed_after=utc('2026-04-15T00:00:00+00:00'))
        self.assertEqual([i.number for i in selected], [2, 6, 1])
        self.assertIn('#6 [Corregir] (cerrado)', format_issues_for_prompt(selected))

    def test_sin_docentes_configurados_acepta_cualquier_autor(self):
        selected = select_correction_issues([raw_issue(3, ['grave'], author='alumno')], frozenset())
        self.assertEqual([i.number for i in selected], [3])


if __name__ == '__main__':
    unittest.main()
