from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from datetime import datetime
from disponibilidad.models import Disponibilidad, Tipo
from disponibilidad.utils import calcular_rango, hay_conflicto, rango_horario_empresa
from usuario.models import Usuario
from servicios.models import Servicio
from .models import Calificacion, Trabajo, TrabajoServicio
from .serializers import TrabajoCreateSerializer, TrabajoDetailSerializer, TrabajoListSerializer, TrabajoSerializer
from rest_framework.decorators import action
from django.db.models import Avg

class TrabajoViewSet(viewsets.ModelViewSet):
    queryset = Trabajo.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return TrabajoCreateSerializer
        elif self.action == 'retrieve': 
            return TrabajoDetailSerializer
        elif self.action == 'list':
            return TrabajoListSerializer
        return TrabajoDetailSerializer

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        usuario = request.user
        descripcion = serializer.validated_data['descripcion']
        esUrgente = serializer.validated_data.get('esUrgente', False)
        servicios_ids = serializer.validated_data['servicios_ids']
        fecha = serializer.validated_data['fecha']
        hora = serializer.validated_data['hora']
        profesional_id = serializer.validated_data['profesional_id']

        try:
            profesional = Usuario.objects.get(id=profesional_id)
        except Usuario.DoesNotExist:
            return Response({'error': 'Profesional no encontrado'}, status=status.HTTP_404_NOT_FOUND)

        servicios = Servicio.objects.filter(id__in=servicios_ids)
        if not servicios.exists():
            return Response({'error': 'No se encontraron servicios válidos'}, status=status.HTTP_400_BAD_REQUEST)

        duracion_total = sum([s.tiempo for s in servicios])
        inicio, fin = calcular_rango(fecha, hora, duracion_total)

        rango_empresa = rango_horario_empresa(profesional, inicio)
        if not rango_empresa:
            return Response({'error': 'Fuera del horario de trabajo del profesional'}, status=status.HTTP_409_CONFLICT)

        if hay_conflicto(profesional.id, inicio, fin):
            return Response({'error': 'El horario se solapa con otro trabajo'}, status=status.HTTP_409_CONFLICT)

        disponibilidad_ocupada = Disponibilidad.objects.create(
            usuario=profesional,
            fecha_inicio=inicio,
            fecha_fin=fin,
            tipo=Tipo.OCUPADO,
            origen='trabajo'
        )

        precio_final = sum([s.precio for s in servicios])
        trabajo = Trabajo.objects.create(
            usuario=usuario,
            profesional=profesional,
            descripcion=descripcion,
            esUrgente=esUrgente,
            disponibilidad=disponibilidad_ocupada,
            fecha_inicio=inicio,
            fecha_fin=fin,
            precio_final=precio_final,
            status='pendiente'
        )

        for servicio in servicios:
            TrabajoServicio.objects.create(
                trabajo=trabajo,
                servicio=servicio,
                precio=servicio.precio
            )
            

        return Response({
            'id': trabajo.id,
            'descripcion': trabajo.descripcion,
            'fecha_inicio': trabajo.fecha_inicio,
            'fecha_fin': trabajo.fecha_fin,
            'precio_final': trabajo.precio_final,
            'profesional_id': profesional.id,
            'servicios': [{'id': s.id, 'nombre': s.nombre, 'precio': s.precio} for s in servicios],
            'status': trabajo.status
        }, status=status.HTTP_201_CREATED)

class CalificacionViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def create(self, request):
        """
        Calificar un trabajo.
        Recibe: trabajo_id, rating (1-5), comentario (opcional)
        """
        usuario = request.user
        trabajo_id = request.data.get('trabajo_id')
        rating = request.data.get('rating')
        comentario = request.data.get('comentario', '')

        if not trabajo_id or not rating:
            return Response({'error': 'Faltan parámetros obligatorios'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            trabajo = Trabajo.objects.get(id=trabajo_id)
        except Trabajo.DoesNotExist:
            return Response({'error': 'Trabajo no encontrado'}, status=status.HTTP_404_NOT_FOUND)

        if trabajo.usuario != usuario:
            return Response({'error': 'No puedes calificar este trabajo'}, status=status.HTTP_403_FORBIDDEN)

        calificacion, created = Calificacion.objects.update_or_create(
            trabajo=trabajo,
            user_cal_sender=usuario,
            defaults={'rating': rating, 'comentario': comentario, 'user_cal_recibe': trabajo.profesional}
        )

        return Response({
            'id': calificacion.id,
            'trabajo_id': trabajo.id,
            'rating': calificacion.rating,
            'comentario': calificacion.comentario,
            'user_cal_recibe': calificacion.user_cal_recibe.id,
            'user_cal_sender': calificacion.user_cal_sender.id
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=False, methods=['GET'], url_path='resumen/(?P<usuario_id>[^/.]+)')
    def resumen(self, request, usuario_id=None):
        """
        Devuelve promedio de estrellas, cantidad de calificaciones y últimas 3 calificaciones para un usuario
        """
        calificaciones = Calificacion.objects.filter(user_cal_recibe_id=usuario_id).order_by('-created_at')
        count = calificaciones.count()
        promedio = calificaciones.aggregate(promedio=Avg('rating'))['promedio'] or 0
        ultimas = calificaciones[:3]

        ultimas_data = [{
            'trabajo_id': c.trabajo.id if c.trabajo else None,
            'rating': c.rating,
            'comentario': c.comentario,
            'user_cal_sender': c.user_cal_sender.id
        } for c in ultimas]

        return Response({
            'usuario_id': usuario_id,
            'promedio': round(promedio, 2),
            'cantidad': count,
            'ultimas': ultimas_data
        })