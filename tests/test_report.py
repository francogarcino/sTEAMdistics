import unittest
from types import SimpleNamespace
from steamdistics.report import unalias


class UnaliasTest(unittest.TestCase):
    def test_reemplaza_cada_alias_por_su_nombre_sin_pisar_alias_mas_largos(self):
        aliases = [f'Integrante {letter}' for letter in 'AB'] + ['Integrante A1']
        members = [SimpleNamespace(name=n) for n in ('Ana Gomez', 'Beto Diaz', 'Caro Ruiz')]
        data = SimpleNamespace(aliases=aliases, members=members)
        text = 'Integrante A1 y Integrante A revisaron lo de Integrante B; Integrante AB no existe.'
        self.assertEqual(unalias(text, data),
                         'Caro Ruiz y Ana Gomez revisaron lo de Beto Diaz; Integrante AB no existe.')


if __name__ == '__main__':
    unittest.main()
