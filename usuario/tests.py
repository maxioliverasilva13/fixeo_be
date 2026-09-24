from types import SimpleNamespace

from django.test import SimpleTestCase
from rest_framework.test import APITestCase

from usuario.mapa_helpers import es_mal_calificado, sort_map_result_rows
from usuario.models import Usuario
from usuario.views import _sort_search_results


class PerfilCatalogoCountsTests(APITestCase):
    """El perfil expone cantidad_servicios / cantidad_productos para el CTA
    de "este profesional usa precios personalizados"."""

    def _get_perfil(self, usuario):
        self.client.force_authenticate(user=usuario)
        resp = self.client.get(f'/api/usuarios/{usuario.id}/')
        self.assertEqual(resp.status_code, 200)
        # El StandardizedResponseMiddleware envuelve todo en {ok, message, data}.
        body = resp.json()
        return body.get('data', body)

    def test_profesional_sin_catalogo_devuelve_ceros(self):
        pro = Usuario.objects.create_user(
            correo='sin-catalogo@test.com',
            password='x',
            nombre='Sin',
            apellido='Catalogo',
            telefono='333',
            is_owner_empresa=True,
        )

        data = self._get_perfil(pro)

        self.assertEqual(data['cantidad_servicios'], 0)
        self.assertEqual(data['cantidad_productos'], 0)

    def test_cliente_no_reporta_catalogo(self):
        cliente = Usuario.objects.create_user(
            correo='solo-cliente@test.com',
            password='x',
            nombre='Solo',
            apellido='Cliente',
            telefono='444',
        )

        data = self._get_perfil(cliente)

        self.assertEqual(data['cantidad_servicios'], 0)
        self.assertEqual(data['cantidad_productos'], 0)


class MalCalificadoTests(SimpleTestCase):
    """Un promedio bajo sólo castiga con historial suficiente."""

    def test_tres_resenas_y_promedio_bajo(self):
        self.assertTrue(es_mal_calificado(2.4, 3))

    def test_dos_resenas_no_es_suficiente(self):
        self.assertFalse(es_mal_calificado(1.0, 2))

    def test_justo_en_el_umbral_no_castiga(self):
        self.assertFalse(es_mal_calificado(2.5, 10))

    def test_sin_resenas_no_castiga(self):
        self.assertFalse(es_mal_calificado(0, 0))

    def test_datos_raros_no_rompen(self):
        self.assertFalse(es_mal_calificado(None, None))
        self.assertFalse(es_mal_calificado('', 'x'))


def _fila_usuario(id_, rating, cant_calif, plan_rank=0, rank=0.0):
    return {
        'tipo': 'usuario',
        'id': id_,
        'rating': rating,
        'cant_calif': cant_calif,
        'plan_rank': plan_rank,
        'rank': rank,
    }


class OrdenBuscadorTests(SimpleTestCase):
    """Plan primero; dentro del plan, calificación; mal calificados al final."""

    def _ids(self, filas, sort_by=None):
        _sort_search_results(filas, sort_by)
        return [f['id'] for f in filas]

    def test_el_plan_manda_sobre_la_calificacion(self):
        filas = [
            _fila_usuario(1, 5.0, 10, plan_rank=10),   # plan chico, excelente
            _fila_usuario(2, 3.0, 10, plan_rank=100),  # plan grande, bueno
        ]

        self.assertEqual(self._ids(filas), [2, 1])

    def test_dentro_del_plan_gana_la_mejor_calificacion(self):
        filas = [
            _fila_usuario(1, 3.0, 10, plan_rank=100),
            _fila_usuario(2, 4.8, 10, plan_rank=100),
            _fila_usuario(3, 4.0, 10, plan_rank=100),
        ]

        self.assertEqual(self._ids(filas), [2, 3, 1])

    def test_mal_calificado_va_ultimo_de_su_plan(self):
        filas = [
            _fila_usuario(1, 1.8, 8, plan_rank=100),   # plan pro, malas reseñas
            _fila_usuario(2, 4.0, 10, plan_rank=100),  # mismo plan, buenas
            _fila_usuario(3, 3.0, 10, plan_rank=100),
        ]

        self.assertEqual(self._ids(filas), [2, 3, 1])

    def test_el_mal_calificado_sigue_arriba_de_un_plan_menor(self):
        """Sólo baja dentro de su grupo: no lo pasa un plan más barato."""
        filas = [
            _fila_usuario(1, 1.8, 8, plan_rank=100),  # pro, mal calificado
            _fila_usuario(2, 5.0, 20, plan_rank=10),  # gratuito, excelente
        ]

        self.assertEqual(self._ids(filas), [1, 2])

    def test_un_profesional_nuevo_no_se_castiga(self):
        filas = [
            _fila_usuario(1, 0, 0, plan_rank=100),     # nuevo, sin reseñas
            _fila_usuario(2, 1.8, 8, plan_rank=100),   # mal calificado
        ]

        self.assertEqual(self._ids(filas), [1, 2])

    def test_la_relevancia_del_texto_desempata(self):
        filas = [
            _fila_usuario(1, 4.0, 10, plan_rank=100, rank=0.1),
            _fila_usuario(2, 4.0, 10, plan_rank=100, rank=0.9),
        ]

        self.assertEqual(self._ids(filas), [2, 1])

    def test_mejor_valorados_usa_el_mismo_criterio(self):
        filas = [
            _fila_usuario(1, 1.8, 8, plan_rank=100),
            _fila_usuario(2, 4.0, 10, plan_rank=100),
        ]

        self.assertEqual(self._ids(filas, 'mejor_valorados'), [2, 1])

    def test_mas_cercanos_no_aplica_la_calificacion(self):
        """Con un criterio explícito del cliente manda la relevancia, no el rating."""
        filas = [
            _fila_usuario(1, 1.8, 8, plan_rank=100, rank=0.9),
            _fila_usuario(2, 5.0, 10, plan_rank=100, rank=0.1),
        ]

        self.assertEqual(self._ids(filas, 'mas_cercanos'), [1, 2])

    def test_los_productos_no_se_degradan(self):
        producto = {
            'tipo': 'producto',
            'id': 99,
            'rating': 0,
            'cant_calif': 0,
            'plan_rank': 100,
            'rank': 0.95,
        }
        filas = [
            _fila_usuario(1, 1.8, 8, plan_rank=100, rank=0.1),
            producto,
            _fila_usuario(2, 4.0, 10, plan_rank=100, rank=0.2),
        ]

        ids = self._ids(filas)

        # El mal calificado queda último; el producto no se degrada.
        self.assertEqual(ids[-1], 1)
        self.assertIn(99, ids)


class OrdenMapaTests(SimpleTestCase):
    """El mapa usa el mismo criterio que el buscador."""

    def _rows(self, *specs):
        return [
            {
                'usuario': SimpleNamespace(
                    id=id_,
                    rating=rating,
                    cant_calif=cant,
                    active_plan_precio=plan,
                    active_plan_jobs=0,
                ),
                'avg_rating': rating,
            }
            for id_, rating, cant, plan in specs
        ]

    def test_mal_calificado_va_ultimo_de_su_plan(self):
        rows = self._rows(
            (1, 1.8, 8, 100),
            (2, 4.0, 10, 100),
        )

        sort_map_result_rows(rows, 'mejor_valorados', {})

        self.assertEqual([r['usuario'].id for r in rows], [2, 1])

    def test_el_plan_sigue_mandando(self):
        rows = self._rows(
            (1, 1.8, 8, 100),
            (2, 5.0, 20, 10),
        )

        sort_map_result_rows(rows, 'mejor_valorados', {})

        self.assertEqual([r['usuario'].id for r in rows], [1, 2])
