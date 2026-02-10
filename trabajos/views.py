from django.db import transaction
from localizacion.models import Localizacion
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from datetime import datetime
from disponibilidad.models import Disponibilidad, Tipo
from disponibilidad.utils import calcular_rango, hay_conflicto, rango_horario_empresa
from usuario.models import Usuario
from servicios.models import Servicio
from usuario_localizacion.models import UsuarioLocalizacion
from .models import Calificacion, Trabajo, TrabajoServicio
from .serializers import TrabajoCreateSerializer, TrabajoDetailSerializer, TrabajoListSerializer, TrabajoSerializer
from rest_framework.decorators import action
from django.db.models import Avg
from django.utils.dateparse import parse_date

class TrabajoViewSet(viewsets.ModelViewSet):
    queryset = Trabajo.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Trabajo.objects.all()

        fecha = self.request.query_params.get('date')
        if fecha:
            fecha_parsed = parse_date(fecha)
            if fecha_parsed:
                queryset = queryset.filter(fecha_inicio__date=fecha_parsed)

        return queryset

    def get_serializer_class(self):
        if self.action == 'create':
            return TrabajoCreateSerializer
        elif self.action == 'retrieve': 
            return TrabajoDetailSerializer
        elif self.action == 'list':
            return TrabajoListSerializer
        return TrabajoDetailSerializer
    
    @action(detail=True, methods=['post'], url_path='aprobar')
    def aprobar_trabajo(self, request, pk=None):
        """
        Aprueba un trabajo pendiente.
        Solo el profesional asignado puede aprobar.
        """
        trabajo = self.get_object()
        
        if trabajo.profesional != request.user:
            return Response(
                {'error': 'Solo el profesional asignado puede aprobar este trabajo'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if trabajo.status != 'pendiente':
            return Response(
                {'error': f'No se puede aprobar un trabajo en estado "{trabajo.status}"'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        trabajo.status = 'aceptado'
        trabajo.save()
        
        return Response({
            'message': 'Trabajo aprobado exitosamente',
            'trabajo': TrabajoDetailSerializer(trabajo).data
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'], url_path='rechazar')
    def rechazar_trabajo(self, request, pk=None):
        """
        Rechaza un trabajo pendiente.
        Solo el profesional asignado puede rechazar.
        Puede incluir un motivo opcional.
        """
        trabajo = self.get_object()
        motivo = request.data.get('motivo', '')
        
        # Validar que el usuario es el profesional asignado
        if trabajo.profesional != request.user:
            return Response(
                {'error': 'Solo el profesional asignado puede rechazar este trabajo'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Validar que el trabajo esté en estado pendiente
        if trabajo.status != 'pendiente':
            return Response(
                {'error': f'No se puede rechazar un trabajo en estado "{trabajo.status}"'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Cambiar estado a cancelado
        trabajo.status = 'cancelado'
        
        # Opcional: guardar el motivo en comentario_cliente si lo enviaron
        if motivo:
            trabajo.comentario_cliente = f"Rechazado por profesional: {motivo}"
        
        trabajo.save()
        
        # Opcional: liberar la disponibilidad ocupada
        if trabajo.disponibilidad:
            trabajo.disponibilidad.delete()
        
        return Response({
            'message': 'Trabajo rechazado exitosamente',
            'trabajo': TrabajoDetailSerializer(trabajo).data
        }, status=status.HTTP_200_OK)

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
        es_domicilio_profesional = serializer.validated_data['es_domicilio_profesional']

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

        localizacion = None

        if es_domicilio_profesional:
            userLocation = UsuarioLocalizacion.objects.filter(usuario=profesional)
            existsPrincipal = userLocation.filter(es_principal=True).exists()
            if existsPrincipal:
                localizacion = userLocation.get(es_principal=True).localizacion  
            else:
                if userLocation.first():
                    localizacion = userLocation.first().localizacion
                else:
                    localizacion = None
        else:
            userLocation = UsuarioLocalizacion.objects.filter(usuario=request.user)
            existsPrincipal = userLocation.filter(es_principal=True).exists()
            if existsPrincipal:
                localizacion = userLocation.filter(es_principal=True).localizacion
            else:
                if userLocation.first():
                    localizacion = userLocation.first().localizacion
                else:
                    localizacion = None

        newStatus = 'pendiente'
        if (profesional.auto_aprobacion_trabajos):
            newStatus = 'aceptado'

        precio_final = sum([s.precio for s in servicios])
        trabajo = Trabajo.objects.create(
            usuario=usuario,
            profesional=profesional,
            descripcion=descripcion,
            esUrgente=esUrgente,
            disponibilidad=disponibilidad_ocupada,
            fecha_inicio=inicio,
            fecha_fin=fin,
            es_domicilio_profesional=es_domicilio_profesional,
            precio_final=precio_final,
            localizacion=localizacion,
            status=newStatus
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