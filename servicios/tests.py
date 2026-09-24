from decimal import Decimal

from rest_framework.test import APITestCase

from profesion.models import Profesion
from servicios.models import Servicio
from usuario.models import Usuario
from usuario_profesion.models import UsuarioProfesion


class ServicioPrecioRangoTests(APITestCase):
    """Un servicio tiene precio fijo O un rango de precios, nunca los dos ni ninguno."""

    def setUp(self):
        self.profesional = Usuario.objects.create_user(
            correo='pro-servicios@test.com',
            password='x',
            nombre='Pro',
            apellido='Servicios',
            telefono='555',
            is_owner_empresa=True,
        )
        self.profesion = Profesion.objects.create(nombre='Plomería Test')
        UsuarioProfesion.objects.create(usuario=self.profesional, profesion=self.profesion)
        self.client.force_authenticate(user=self.profesional)

    def _crear(self, **extra):
        payload = {
            'profesion': self.profesion.id,
            'nombre': 'Cambio de canilla',
            'divisa': 'UYU',
            'tiempo': 60,
            **extra,
        }
        return self.client.post('/api/servicios/', payload, format='json')

    # --- precio fijo ---

    def test_precio_fijo(self):
        resp = self._crear(precio='1500')

        self.assertEqual(resp.status_code, 201, resp.content)
        servicio = Servicio.objects.get()
        self.assertEqual(servicio.precio, Decimal('1500'))
        self.assertIsNone(servicio.precio_min)
        self.assertIsNone(servicio.precio_max)
        self.assertFalse(servicio.usa_precio_rango)
        self.assertFalse(resp.json()['data']['usa_precio_rango'])

    def test_precio_cero_es_invalido(self):
        resp = self._crear(precio='0')
        self.assertEqual(resp.status_code, 400)

    # --- rango ---

    def test_rango_valido_sincera_precio_al_minimo(self):
        resp = self._crear(precio_min='1000', precio_max='3000')

        self.assertEqual(resp.status_code, 201, resp.content)
        servicio = Servicio.objects.get()
        self.assertEqual(servicio.precio_min, Decimal('1000'))
        self.assertEqual(servicio.precio_max, Decimal('3000'))
        # El rango manda: `precio` queda como referencia para listados y sumas.
        self.assertEqual(servicio.precio, Decimal('1000'))
        self.assertTrue(servicio.usa_precio_rango)
        self.assertTrue(resp.json()['data']['usa_precio_rango'])
        self.assertEqual(resp.json()['data']['precio_min'], '1000.00')
        self.assertEqual(resp.json()['data']['precio_max'], '3000.00')

    def test_el_rango_pisa_el_precio_enviado(self):
        resp = self._crear(precio='9999', precio_min='1000', precio_max='3000')

        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(Servicio.objects.get().precio, Decimal('1000'))

    def test_rango_puede_omitir_el_precio(self):
        resp = self._crear(precio_min='500', precio_max='800')
        self.assertEqual(resp.status_code, 201, resp.content)

    # --- combinaciones inválidas ---

    def test_solo_minimo_es_invalido(self):
        resp = self._crear(precio_min='1000')

        self.assertEqual(resp.status_code, 400)
        self.assertIn('precio_min', resp.json()['data'])

    def test_solo_maximo_es_invalido(self):
        resp = self._crear(precio_max='3000')

        self.assertEqual(resp.status_code, 400)
        self.assertIn('precio_min', resp.json()['data'])

    def test_maximo_menor_al_minimo_es_invalido(self):
        resp = self._crear(precio_min='3000', precio_max='1000')

        self.assertEqual(resp.status_code, 400)
        self.assertIn('precio_max', resp.json()['data'])

    def test_minimo_cero_es_invalido(self):
        resp = self._crear(precio_min='0', precio_max='1000')

        self.assertEqual(resp.status_code, 400)
        self.assertIn('precio_min', resp.json()['data'])

    def test_sin_precio_ni_rango_es_invalido(self):
        resp = self._crear()

        self.assertEqual(resp.status_code, 400)
        self.assertIn('precio', resp.json()['data'])
        self.assertEqual(Servicio.objects.count(), 0)

    # --- edición ---

    def test_pasar_de_rango_a_precio_fijo(self):
        self._crear(precio_min='1000', precio_max='3000')
        servicio = Servicio.objects.get()

        resp = self.client.patch(
            f'/api/servicios/{servicio.id}/',
            {'precio': '2500', 'precio_min': None, 'precio_max': None},
            format='json',
        )

        self.assertEqual(resp.status_code, 200, resp.content)
        servicio.refresh_from_db()
        self.assertEqual(servicio.precio, Decimal('2500'))
        self.assertIsNone(servicio.precio_min)
        self.assertIsNone(servicio.precio_max)
        self.assertFalse(servicio.usa_precio_rango)

    def test_pasar_de_precio_fijo_a_rango(self):
        self._crear(precio='2500')
        servicio = Servicio.objects.get()

        resp = self.client.patch(
            f'/api/servicios/{servicio.id}/',
            {'precio_min': '1000', 'precio_max': '4000'},
            format='json',
        )

        self.assertEqual(resp.status_code, 200, resp.content)
        servicio.refresh_from_db()
        self.assertTrue(servicio.usa_precio_rango)
        self.assertEqual(servicio.precio, Decimal('1000'))

    # --- catálogo público ---

    def test_el_catalogo_publico_expone_el_rango(self):
        self._crear(nombre='Con rango', precio_min='1000', precio_max='3000')

        resp = self.client.get(f'/api/servicios/{self.profesional.id}/obtener-servicios/')

        self.assertEqual(resp.status_code, 200)
        servicios = resp.json()['data']
        self.assertEqual(len(servicios), 1)
        self.assertTrue(servicios[0]['usa_precio_rango'])
        self.assertEqual(servicios[0]['precio_min'], '1000.00')
        self.assertEqual(servicios[0]['precio_max'], '3000.00')
