from unittest.mock import patch

from rest_framework.test import APITestCase

from mensajeria.models import Chat, Mensajes
from usuario.models import Usuario


class ChatCreateNotificationTests(APITestCase):
    """POST /api/mensajeria/chats/ es el endpoint del botón "Consultar"."""

    def setUp(self):
        self.cliente = Usuario.objects.create_user(
            correo='cliente@test.com',
            password='x',
            nombre='Ana',
            apellido='Cliente',
            telefono='111',
        )
        self.profesional = Usuario.objects.create_user(
            correo='pro@test.com',
            password='x',
            nombre='Juan',
            apellido='Pro',
            telefono='222',
            is_owner_empresa=True,
        )

    def _crear_chat(self, mensaje_inicial):
        self.client.force_authenticate(user=self.cliente)
        return self.client.post(
            '/api/mensajeria/chats/',
            {'receiver_id': self.profesional.id, 'mensaje_inicial': mensaje_inicial},
            format='json',
        )

    @patch('mensajeria.views.notificar_usuario')
    def test_chat_nuevo_con_mensaje_notifica_al_profesional(self, notificar):
        resp = self._crear_chat('Hola, quiero un presupuesto')

        self.assertEqual(resp.status_code, 201)
        self.assertEqual(Mensajes.objects.count(), 1)

        notificar.delay.assert_called_once()
        kwargs = notificar.delay.call_args.kwargs
        self.assertEqual(kwargs['usuario_id'], self.profesional.id)
        self.assertEqual(kwargs['mensaje'], 'Hola, quiero un presupuesto')
        self.assertEqual(kwargs['data']['tipo'], 'mensaje')
        self.assertEqual(kwargs['data']['entity_id'], Chat.objects.get().id)

    @patch('mensajeria.views.notificar_usuario')
    def test_chat_existente_no_descarta_el_mensaje_inicial(self, notificar):
        """Regresión: antes se devolvía 200 temprano y el mensaje se perdía."""
        Chat.objects.create(sender=self.profesional, receiver=self.cliente)

        resp = self._crear_chat('Consulta por precios personalizados')

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Chat.objects.count(), 1)
        self.assertEqual(Mensajes.objects.count(), 1)
        self.assertEqual(
            Mensajes.objects.get().texto,
            'Consulta por precios personalizados',
        )
        notificar.delay.assert_called_once()

    @patch('mensajeria.views.notificar_usuario')
    def test_chat_sin_mensaje_inicial_no_notifica(self, notificar):
        resp = self._crear_chat('')

        self.assertEqual(resp.status_code, 201)
        self.assertEqual(Mensajes.objects.count(), 0)
        notificar.delay.assert_not_called()

    @patch('mensajeria.views.notificar_usuario')
    def test_no_se_puede_crear_chat_con_uno_mismo(self, notificar):
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.post(
            '/api/mensajeria/chats/',
            {'receiver_id': self.cliente.id, 'mensaje_inicial': 'hola'},
            format='json',
        )

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Chat.objects.count(), 0)
        notificar.delay.assert_not_called()
