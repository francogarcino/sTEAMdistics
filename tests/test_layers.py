import unittest
from steamdistics.layers import map_layer, is_generated
from tests.helpers import ANALYSIS_CONFIG


class MapLayerTest(unittest.TestCase):
    def assertLayer(self, path, expected):
        self.assertEqual(map_layer(path, ANALYSIS_CONFIG), expected, path)

    def test_paquetes_de_persistencia_con_distintos_nombres(self):
        for path in ('src/main/java/ar/unq/persistence/PersonajeDAO.java',
                     'src/main/java/ar/unq/dao/impl/HibernatePersonajeDAO.java',
                     'src/main/java/ar/unq/repository/PersonajeRepository.java',
                     'src/main/java/ar/unq/repositorio/X.java'):
            self.assertLayer(path, 'persistencia')

    def test_sufijo_de_archivo_define_la_capa_fuera_de_un_paquete_conocido(self):
        self.assertLayer('src/main/java/ar/unq/HibernatePersonajeDAO.java', 'persistencia')
        self.assertLayer('src/main/java/ar/unq/PersonajeServiceImpl.java', 'servicio')
        self.assertLayer('src/main/java/ar/unq/PersonajeControllerREST.java', 'controller')

    def test_servicios_en_singular_y_plural(self):
        self.assertLayer('src/main/java/ar/unq/services/X.java', 'servicio')
        self.assertLayer('src/main/java/ar/unq/servicio/X.java', 'servicio')

    def test_test_gana_sobre_cualquier_otra_capa(self):
        self.assertLayer('src/test/java/ar/unq/persistence/PersonajeDAOTest.java', 'test')

    def test_modelo_y_otros(self):
        self.assertLayer('src/main/java/ar/unq/modelo/Personaje.java', 'modelo')
        self.assertLayer('pom.xml', 'otros')

    def test_nombre_que_solo_contiene_la_palabra_no_matchea(self):
        self.assertLayer('src/main/java/ar/unq/modelo/DaoTipo.java', 'modelo')


class IsGeneratedTest(unittest.TestCase):
    def test_archivos_generados(self):
        for path in ('target/classes/X.class', '.idea/workspace.xml', 'package-lock.json',
                     'sub/build/out.txt', 'lib/driver.jar', 'mvnw'):
            self.assertTrue(is_generated(path, ANALYSIS_CONFIG), path)

    def test_codigo_fuente_no_es_generado(self):
        self.assertFalse(is_generated('src/main/java/ar/unq/targeting/X.java', ANALYSIS_CONFIG))


if __name__ == '__main__':
    unittest.main()
