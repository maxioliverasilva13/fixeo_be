from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from localizacion.models import Localizacion
from localizacion.utils import calcular_distancia_km
from profesion.models import Profesion
from usuario.models import Usuario
from usuario_localizacion.models import UsuarioLocalizacion
from usuario_profesion.models import UsuarioProfesion
from disponibilidad.models import Disponibilidad, Tipo
from .models import Trabajo, OfertaTrabajo
from .serializers import (
    TrabajoUrgenteCreateSerializer,
    TrabajoUrgenteDetailSerializer,
    OfertaTrabajoSerializer,
    OfertaTrabajoCreateSerializer
)


class TrabajoUrgenteViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def create(self, request):
        serializer = TrabajoUrgenteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        usuario = request.user
        descripcion = serializer.validated_data['descripcion']
        profesion_id = serializer.validated_data['profesion_id']
        latitud = serializer.validated_data['latitud']
        longitud = serializer.validated_data['longitud']
        direccion = serializer.validated_data.get('direccion', '')
        radio_busqueda_km = serializer.validated_data.get('radio_busqueda_km', 10.00)
        
        try:
            profesion = Profesion.objects.get(id=profesion_id)
        except Profesion.DoesNotExist:
            return Response({'error': 'Profesión no encontrada'}, status=status.HTTP_404_NOT_FOUND)
        
        localizacion = Localizacion.objects.filter(
            latitud=latitud,
            longitud=longitud
        ).first()
        
        if not localizacion:
            localizacion = Localizacion.objects.create(
                ubicacion=direccion,
                latitud=latitud,
                longitud=longitud,
                address=direccion,
                isPrimary=False
            )
        
        trabajo = Trabajo.objects.create(
            usuario=usuario,
            descripcion=descripcion,
            esUrgente=True,
            status='pendiente_urgente',
            localizacion=localizacion,
            profesion_urgente=profesion,
            radio_busqueda_km=radio_busqueda_km,
            es_domicilio_profesional=False
        )
        
        return Response(
            TrabajoUrgenteDetailSerializer(trabajo).data,
            status=status.HTTP_201_CREATED
        )
    
    def list(self, request):
        usuario = request.user
        usuario_profesiones = UsuarioProfesion.objects.filter(usuario=usuario).values_list('profesion_id', flat=True)
        
        if not usuario_profesiones:
            return Response({
                'message': 'No tienes profesiones configuradas',
                'trabajos': []
            })
        
        localizacion_usuario = UsuarioLocalizacion.objects.filter(
            usuario=usuario,
            localizacion__isPrimary=True
        ).select_related('localizacion').first()
        
        if not localizacion_usuario:
            localizacion_usuario = UsuarioLocalizacion.objects.filter(
                usuario=usuario
            ).select_related('localizacion').first()
        
        if not localizacion_usuario:
            return Response({
                'message': 'No tienes localización configurada',
                'trabajos': []
            })
        
        trabajos_urgentes = Trabajo.objects.filter(
            esUrgente=True,
            status='pendiente_urgente',
            profesion_urgente_id__in=usuario_profesiones
        ).exclude(
            usuario=usuario
        ).select_related('usuario', 'localizacion', 'profesion_urgente')
        
        print(str(usuario_profesiones))
        print("xd1")
        print(trabajos_urgentes.count())
        trabajos_cercanos = []
        for trabajo in trabajos_urgentes:
            if trabajo.localizacion:
                distancia = calcular_distancia_km(
                    float(localizacion_usuario.localizacion.latitud),
                    float(localizacion_usuario.localizacion.longitud),
                    float(trabajo.localizacion.latitud),
                    float(trabajo.localizacion.longitud)
                )
                
                if distancia <= float(trabajo.radio_busqueda_km or 10):
                    trabajo_data = TrabajoUrgenteDetailSerializer(trabajo).data
                    trabajo_data['distancia_km'] = round(distancia, 2)
                    trabajos_cercanos.append(trabajo_data)
        
        trabajos_cercanos.sort(key=lambda x: x['distancia_km'])
        
        return Response({
            'count': len(trabajos_cercanos),
            'trabajos': trabajos_cercanos
        })
    
    def retrieve(self, request, pk=None):
        try:
            trabajo = Trabajo.objects.get(id=pk, esUrgente=True)
        except Trabajo.DoesNotExist:
            return Response({'error': 'Trabajo urgente no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        
        return Response(TrabajoUrgenteDetailSerializer(trabajo).data)
    
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def ofertar(self, request, pk=None):
        try:
            trabajo = Trabajo.objects.get(id=pk, esUrgente=True)
        except Trabajo.DoesNotExist:
            return Response({'error': 'Trabajo urgente no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        
        if trabajo.status != 'pendiente_urgente':
            return Response(
                {'error': 'Este trabajo ya no acepta ofertas'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if trabajo.usuario == request.user:
            return Response(
                {'error': 'No puedes ofertar en tu propio trabajo'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if OfertaTrabajo.objects.filter(trabajo=trabajo, profesional=request.user).exists():
            return Response(
                {'error': 'Ya has realizado una oferta para este trabajo'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = OfertaTrabajoCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        oferta = OfertaTrabajo.objects.create(
            trabajo=trabajo,
            profesional=request.user,
            precio_ofertado=serializer.validated_data['precio_ofertado'],
            tiempo_estimado=serializer.validated_data['tiempo_estimado'],
            mensaje=serializer.validated_data.get('mensaje', '')
        )
        
        return Response(
            OfertaTrabajoSerializer(oferta).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['get'])
    def ofertas(self, request, pk=None):
        try:
            trabajo = Trabajo.objects.get(id=pk, esUrgente=True)
        except Trabajo.DoesNotExist:
            return Response({'error': 'Trabajo urgente no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        
        if trabajo.usuario != request.user:
            return Response(
                {'error': 'Solo el creador del trabajo puede ver las ofertas'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        ofertas = trabajo.ofertas.select_related('profesional').all()
        return Response({
            'count': ofertas.count(),
            'ofertas': OfertaTrabajoSerializer(ofertas, many=True).data
        })
    
    @action(detail=True, methods=['post'], url_path='ofertas/(?P<oferta_id>[^/.]+)/aceptar')
    @transaction.atomic
    def aceptar_oferta(self, request, pk=None, oferta_id=None):
        try:
            trabajo = Trabajo.objects.get(id=pk, esUrgente=True)
        except Trabajo.DoesNotExist:
            return Response({'error': 'Trabajo urgente no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        
        if trabajo.usuario != request.user:
            return Response(
                {'error': 'Solo el creador del trabajo puede aceptar ofertas'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if trabajo.status != 'pendiente_urgente':
            return Response(
                {'error': 'Este trabajo ya no acepta cambios en ofertas'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            oferta = OfertaTrabajo.objects.get(id=oferta_id, trabajo=trabajo)
        except OfertaTrabajo.DoesNotExist:
            return Response({'error': 'Oferta no encontrada'}, status=status.HTTP_404_NOT_FOUND)
        
        now = timezone.now()
        tiempo_estimado_minutos = oferta.tiempo_estimado
        fecha_inicio = now
        fecha_fin = now + timedelta(minutes=tiempo_estimado_minutos)
        
        disponibilidad_ocupada = Disponibilidad.objects.create(
            usuario=oferta.profesional,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            tipo=Tipo.OCUPADO,
            origen='trabajo'
        )
        
        oferta.status = 'aceptada'
        oferta.save()
        
        trabajo.status = 'aceptado'
        trabajo.profesional = oferta.profesional
        trabajo.precio_final = oferta.precio_ofertado
        trabajo.fecha_inicio = fecha_inicio
        trabajo.fecha_fin = fecha_fin
        trabajo.disponibilidad = disponibilidad_ocupada
        trabajo.save()
        
        trabajo.ofertas.exclude(id=oferta.id).update(status='rechazada')
        
        return Response({
            'message': 'Oferta aceptada exitosamente',
            'trabajo': TrabajoUrgenteDetailSerializer(trabajo).data
        })
    
    @action(detail=True, methods=['post'], url_path='ofertas/(?P<oferta_id>[^/.]+)/rechazar')
    @transaction.atomic
    def rechazar_oferta(self, request, pk=None, oferta_id=None):
        try:
            trabajo = Trabajo.objects.get(id=pk, esUrgente=True)
        except Trabajo.DoesNotExist:
            return Response({'error': 'Trabajo urgente no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        
        if trabajo.usuario != request.user:
            return Response(
                {'error': 'Solo el creador del trabajo puede rechazar ofertas'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if trabajo.status != 'pendiente_urgente':
            return Response(
                {'error': 'Este trabajo ya no acepta cambios en ofertas'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            oferta = OfertaTrabajo.objects.get(id=oferta_id, trabajo=trabajo)
        except OfertaTrabajo.DoesNotExist:
            return Response({'error': 'Oferta no encontrada'}, status=status.HTTP_404_NOT_FOUND)
        
        oferta.status = 'rechazada'
        oferta.save()
        
        return Response({
            'message': 'Oferta rechazada exitosamente',
            'oferta': OfertaTrabajoSerializer(oferta).data
        })
    
    @action(detail=False, methods=['get'], url_path='mis-solicitudes')
    def mis_solicitudes(self, request):
        status_filter = request.query_params.get('status', None)
        
        trabajos = Trabajo.objects.filter(
            usuario=request.user,
            esUrgente=True
        ).select_related('profesional', 'localizacion', 'profesion_urgente').prefetch_related('ofertas')
        
        if status_filter:
            trabajos = trabajos.filter(status=status_filter)
        
        trabajos = trabajos.order_by('-created_at')
        
        return Response({
            'count': trabajos.count(),
            'trabajos': TrabajoUrgenteDetailSerializer(trabajos, many=True).data
        })
