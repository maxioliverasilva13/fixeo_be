from datetime import time, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.utils import timezone
from rest_framework.test import APITestCase

from empresas.models import Empresa, Horarios
from profesion.models import Profesion
from servicios.models import Servicio
from trabajos.models import Trabajo
from usuario.models import Usuario
from usuario_profesion.models import UsuarioProfesion


class TrabajoPrecioPersonalizadoTests(APITestCase):
    """Precio personalizado: el rango se congela al solicitar y el profesional
    tiene que estimar el precio dentro de ese rango al aceptar."""

    def setUp(self):
        self.cliente = Usuario.objects.create_user(
            correo='cliente-trabajo@test.com',
            password='x',
            nombre='Ana',
            apellido='Cliente',
            telefono='111',
        )
        self.profesional = Usuario.objects.create_user(
            correo='pro-trabajo@test.com',
            password='x',
            nombre='Juan',
            apellido='Pro',
            telefono='222',
            is_owner_empresa=True,
        )
        self.profesion = Profesion.objects.create(nombre='Plomería Trabajos')
        UsuarioProfesion.objects.create(usuario=self.profesional, profesion=self.profesion)

        self.empresa = Empresa.objects.create(
            nombre='Empresa Test',
            ubicacion='Montevideo',
            descripcion='x',
            latitud=Decimal('-34.9000000'),
            longitud=Decimal('-56.1000000'),
            admin_id=self.profesional,
            pais='UY',
        )
        # Horario abierto todos los días para que la agenda no bloquee el test.
        for dia in range(1, 8):
            Horarios.objects.create(
                empresa=self.empresa,
                dia_semana=str(dia),
                hora_inicio=time(0, 0),
                hora_fin=time(23, 59),
                enabled=True,
            )

        self.servicio_rango = Servicio.objects.create(
            usuario=self.profesional,
            profesion=self.profesion,
            nombre='Con rango',
            precio=Decimal('1000'),
            precio_min=Decimal('1000'),
            precio_max=Decimal('3000'),
            divisa='UYU',
            tiempo=60,
        )
        self.servicio_fijo = Servicio.objects.create(
            usuario=self.profesional,
            profesion=self.profesion,
            nombre='Precio fijo',
            precio=Decimal('500'),
            divisa='UYU',
            tiempo=60,
        )

        self.client.force_authenticate(user=self.cliente)

    def _crear_trabajo(self, *servicios):
        manana = timezone.localdate() + timedelta(days=1)
        with patch('trabajos.views.notificar_usuario'), \
                patch('trabajos.views.enviar_mensaje_whatsapp_task'), \
                patch('trabajos.tasks.enviar_template_confirmacion_trabajo_task'):
            return self.client.post(
                '/api/trabajos/',
                {
                    'descripcion': 'Prueba de precio personalizado',
                    'servicios_ids': [s.id for s in servicios],
                    'fecha': manana.isoformat(),
                    'hora': '10:00',
                    'profesional_id': self.profesional.id,
                    'es_domicilio_profesional': False,
                    'metodo_pago': 'efectivo',
                },
                format='json',
            )

    def _trabajo_pendiente_con_rango(self):
        return Trabajo.objects.create(
            usuario=self.cliente,
            profesional=self.profesional,
            descripcion='Pendiente con rango',
            status='pendiente',
            precio_min=Decimal('1000'),
            precio_max=Decimal('3000'),
            requiere_estimacion_precio=True,
        )

    def _aprobar(self, trabajo, precio_estimado=None):
        self.client.force_authenticate(user=self.profesional)
        payload = {} if precio_estimado is None else {'precio_estimado': precio_estimado}
        with patch('trabajos.views.notificar_usuario'), \
                patch('trabajos.views.enviar_mensaje_whatsapp_task'):
            return self.client.post(f'/api/trabajos/{trabajo.id}/aprobar/', payload, format='json')

    # --- creación: snapshot del rango ---

    def test_servicio_con_rango_no_fija_precio_final(self):
        resp = self._crear_trabajo(self.servicio_rango)

        self.assertEqual(resp.status_code, 201, resp.content)
        trabajo = Trabajo.objects.get()
        self.assertTrue(trabajo.requiere_estimacion_precio)
        self.assertIsNone(trabajo.precio_final)
        self.assertEqual(trabajo.precio_min, Decimal('1000'))
        self.assertEqual(trabajo.precio_max, Decimal('3000'))
        self.assertEqual(trabajo.status, 'pendiente')

    def test_servicio_fijo_sigue_comportandose_igual(self):
        resp = self._crear_trabajo(self.servicio_fijo)

        self.assertEqual(resp.status_code, 201, resp.content)
        trabajo = Trabajo.objects.get()
        self.assertFalse(trabajo.requiere_estimacion_precio)
        self.assertEqual(trabajo.precio_final, Decimal('500'))
        self.assertIsNone(trabajo.precio_min)
        self.assertIsNone(trabajo.precio_max)

    def test_servicios_mixtos_suman_los_extremos(self):
        resp = self._crear_trabajo(self.servicio_rango, self.servicio_fijo)

        self.assertEqual(resp.status_code, 201, resp.content)
        trabajo = Trabajo.objects.get()
        self.assertTrue(trabajo.requiere_estimacion_precio)
        self.assertIsNone(trabajo.precio_final)
        # El fijo entra en ambos extremos: 1000+500 .. 3000+500
        self.assertEqual(trabajo.precio_min, Decimal('1500'))
        self.assertEqual(trabajo.precio_max, Decimal('3500'))

    def test_la_autoprobacion_no_saltea_la_estimacion(self):
        self.profesional.auto_aprobacion_trabajos = True
        self.profesional.save(update_fields=['auto_aprobacion_trabajos'])

        resp = self._crear_trabajo(self.servicio_rango)

        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(Trabajo.objects.get().status, 'pendiente')

    # --- aceptación: precio obligatorio y dentro del rango ---

    def test_no_se_puede_aceptar_sin_precio(self):
        trabajo = self._trabajo_pendiente_con_rango()

        resp = self._aprobar(trabajo)

        self.assertEqual(resp.status_code, 400)
        trabajo.refresh_from_db()
        self.assertEqual(trabajo.status, 'pendiente')
        self.assertIsNone(trabajo.precio_final)

    def test_no_se_puede_aceptar_por_debajo_del_minimo(self):
        trabajo = self._trabajo_pendiente_con_rango()

        resp = self._aprobar(trabajo, '999')

        self.assertEqual(resp.status_code, 400)
        self.assertIn('menor', resp.json()['message'])
        trabajo.refresh_from_db()
        self.assertEqual(trabajo.status, 'pendiente')

    def test_no_se_puede_aceptar_por_encima_del_maximo(self):
        trabajo = self._trabajo_pendiente_con_rango()

        resp = self._aprobar(trabajo, '3001')

        self.assertEqual(resp.status_code, 400)
        self.assertIn('mayor', resp.json()['message'])
        trabajo.refresh_from_db()
        self.assertEqual(trabajo.status, 'pendiente')

    def test_aceptar_con_precio_valido_lo_deja_como_precio_final(self):
        trabajo = self._trabajo_pendiente_con_rango()

        resp = self._aprobar(trabajo, '2500')

        self.assertEqual(resp.status_code, 200, resp.content)
        trabajo.refresh_from_db()
        self.assertEqual(trabajo.status, 'aceptado')
        self.assertEqual(trabajo.precio_final, Decimal('2500'))
        self.assertEqual(trabajo.precio_estimado, Decimal('2500'))
        self.assertFalse(trabajo.requiere_estimacion_precio)

    def test_los_extremos_del_rango_son_validos(self):
        for precio in ('1000', '3000'):
            with self.subTest(precio=precio):
                trabajo = self._trabajo_pendiente_con_rango()
                resp = self._aprobar(trabajo, precio)
                self.assertEqual(resp.status_code, 200, resp.content)
                trabajo.refresh_from_db()
                self.assertEqual(trabajo.precio_final, Decimal(precio))

    def test_un_precio_invalido_no_rompe(self):
        trabajo = self._trabajo_pendiente_con_rango()

        resp = self._aprobar(trabajo, 'no-es-un-numero')

        self.assertEqual(resp.status_code, 400)
        trabajo.refresh_from_db()
        self.assertEqual(trabajo.status, 'pendiente')

    def test_sin_rango_se_acepta_sin_precio(self):
        """El flujo de precio fijo sigue aceptándose como antes."""
        trabajo = Trabajo.objects.create(
            usuario=self.cliente,
            profesional=self.profesional,
            descripcion='Precio fijo',
            status='pendiente',
            precio_final=Decimal('500'),
            requiere_estimacion_precio=False,
        )

        resp = self._aprobar(trabajo)

        self.assertEqual(resp.status_code, 200, resp.content)
        trabajo.refresh_from_db()
        self.assertEqual(trabajo.status, 'aceptado')
        self.assertEqual(trabajo.precio_final, Decimal('500'))

    # --- link de WhatsApp: no se bloquea ---

    def test_el_link_por_token_no_se_bloquea_con_rango(self):
        trabajo = self._trabajo_pendiente_con_rango()

        with patch('trabajos.views.notificar_usuario'), \
                patch('trabajos.views.enviar_mensaje_whatsapp_task'):
            resp = self.client.post(f'/api/trabajos/confirmar/{trabajo.token_confirmacion}/')

        self.assertEqual(resp.status_code, 200, resp.content)
        trabajo.refresh_from_db()
        self.assertEqual(trabajo.status, 'aceptado')
        # Aceptado pero con el precio todavía pendiente de definir en la app.
        self.assertIsNone(trabajo.precio_final)
        self.assertTrue(trabajo.requiere_estimacion_precio)

    # --- completar el precio de un trabajo aceptado sin precio ---

    def _trabajo_aceptado_sin_precio(self):
        return Trabajo.objects.create(
            usuario=self.cliente,
            profesional=self.profesional,
            descripcion='Aceptado sin precio (link de WhatsApp)',
            status='aceptado',
            precio_min=Decimal('1000'),
            precio_max=Decimal('3000'),
            requiere_estimacion_precio=True,
        )

    def _estimar(self, trabajo, precio_estimado):
        self.client.force_authenticate(user=self.profesional)
        with patch('trabajos.views.notificar_usuario'):
            return self.client.post(
                f'/api/trabajos/{trabajo.id}/estimar-precio/',
                {'precio_estimado': precio_estimado},
                format='json',
            )

    def test_se_puede_completar_el_precio_de_un_trabajo_aceptado(self):
        trabajo = self._trabajo_aceptado_sin_precio()

        resp = self._estimar(trabajo, '2200')

        self.assertEqual(resp.status_code, 200, resp.content)
        trabajo.refresh_from_db()
        self.assertEqual(trabajo.status, 'aceptado')
        self.assertEqual(trabajo.precio_final, Decimal('2200'))
        self.assertFalse(trabajo.requiere_estimacion_precio)

    def test_estimar_respeta_el_rango(self):
        trabajo = self._trabajo_aceptado_sin_precio()
        resp = self._estimar(trabajo, '5000')
        self.assertEqual(resp.status_code, 400)
        trabajo.refresh_from_db()
        self.assertIsNone(trabajo.precio_final)

    def test_no_se_puede_estimar_si_ya_tiene_precio(self):
        trabajo = self._trabajo_aceptado_sin_precio()
        self._estimar(trabajo, '2200')

        resp = self._estimar(trabajo, '2500')

        self.assertEqual(resp.status_code, 400)
        trabajo.refresh_from_db()
        self.assertEqual(trabajo.precio_final, Decimal('2200'))
