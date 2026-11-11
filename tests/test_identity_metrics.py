import unittest
from steamdistics.gitlog import MergeCommit
from steamdistics.identity import group_members
from steamdistics.metrics import compute_member_metrics, activity_shares
from tests.helpers import ANALYSIS_CONFIG, make_change, make_commit, utc


class GroupMembersTest(unittest.TestCase):
    def test_emails_distintos_con_el_mismo_login_son_la_misma_persona(self):
        work_email = make_commit(sha='1' * 40, name='ana', email='ana@trabajo.com')
        personal_email = make_commit(sha='2' * 40, name='Ana G', email='ana@gmail.com')
        members = group_members([work_email, personal_email], logins_by_sha={'1' * 40: 'anag', '2' * 40: 'anag'})
        self.assertEqual(len(members), 1)
        self.assertEqual(members[0].login, 'anag')
        self.assertEqual(members[0].emails, {'ana@trabajo.com', 'ana@gmail.com'})

    def test_email_noreply_de_github_da_el_login(self):
        web_commit = make_commit(email='12345+anag@users.noreply.github.com')
        [member] = group_members([web_commit], roster=['AnaG'])
        self.assertEqual(member.login, 'anag')
        self.assertEqual(len(member.authored), 1)

    def test_nombre_completo_igual_unifica_y_nombre_de_una_palabra_no(self):
        laptop = make_commit(sha='1' * 40, name='Ana Gomez', email='ana@a.com')
        desktop = make_commit(sha='2' * 40, name='ana  gómez', email='ana@b.com')
        first_ubuntu = make_commit(sha='3' * 40, name='ubuntu', email='x@lab1')
        second_ubuntu = make_commit(sha='4' * 40, name='ubuntu', email='y@lab2')
        members = group_members([laptop, desktop, first_ubuntu, second_ubuntu])
        self.assertEqual(sorted(len(m.authored) for m in members), [1, 1, 2])

    def test_integrante_del_roster_sin_commits_aparece_sin_actividad(self):
        members = group_members([make_commit()], logins_by_sha={'a' * 40: 'anag'}, roster=['anag', 'beto'])
        inactive = [m for m in members if not m.has_activity]
        self.assertEqual([m.login for m in inactive], ['beto'])

    def test_co_autor_recibe_el_commit_en_pareja(self):
        paired = make_commit(co_authors=[('Beto Diaz', 'beto@example.com')])
        members = {m.name: m for m in group_members([paired])}
        self.assertEqual(len(members['Ana Gomez'].authored), 1)
        self.assertEqual(len(members['Beto Diaz'].co_authored), 1)

    def test_solo_merges_cuenta_como_actividad(self):
        web_merge = MergeCommit('m' * 40, 'Beto Diaz', 'beto@example.com', 'Merge pull request #1')
        members = {m.name: m for m in group_members([make_commit()], merges=[web_merge])}
        self.assertTrue(members['Beto Diaz'].has_activity)
        self.assertEqual(len(members['Beto Diaz'].merges), 1)


class MetricsTest(unittest.TestCase):
    def test_capas_dias_y_trabajo_sobre_la_hora(self):
        early = make_commit(sha='1' * 40, date='2026-05-01T10:00:00+00:00',
                            files=[make_change('dao/A.java', 'persistencia', 30, 10)])
        last_minute = make_commit(sha='2' * 40, date='2026-05-09T22:00:00+00:00', subject='Revert "x"',
                                  files=[make_change('service/B.java', 'servicio', 50, 10),
                                         make_change('target/C.class', 'otros', 500, 0, generated=True)])
        [member] = group_members([early, last_minute])
        metrics = compute_member_metrics(member, utc('2026-05-10T10:00:00+00:00'), ANALYSIS_CONFIG)
        self.assertEqual((metrics.added, metrics.deleted, metrics.files_touched), (80, 20, 2))
        self.assertEqual(metrics.layer_share('servicio'), 60)
        self.assertEqual(metrics.layer_share('otros'), 0)
        self.assertEqual(metrics.late_share, {24: 60, 48: 60})
        self.assertEqual(metrics.active_days, 2)
        self.assertEqual(metrics.reverts, 1)

    def test_porcentaje_de_actividad_del_equipo(self):
        heavy = make_commit(sha='1' * 40, files=[make_change('a', 'otros', 75, 0)])
        light = make_commit(sha='2' * 40, name='Beto Diaz', email='beto@example.com',
                            files=[make_change('b', 'otros', 25, 0)])
        members = group_members([heavy, light])
        metrics = {m.name: compute_member_metrics(m, utc('2026-06-01T00:00:00+00:00'), ANALYSIS_CONFIG)
                   for m in members}
        self.assertEqual(activity_shares(metrics), {'Ana Gomez': 75, 'Beto Diaz': 25})


if __name__ == '__main__':
    unittest.main()
