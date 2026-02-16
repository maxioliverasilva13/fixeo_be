from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.db.models import Q, F, FloatField
from django.db.models.functions import ACos, Cos, Sin, Radians
from django.db.models.expressions import Value
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
from notificaciones.tasks import notificar_usuario, notificar_usuarios_multiple
from .models import Trabajo, OfertaTrabajo
from .serializers import (
    TrabajoUrgenteCreateSerializer,
    TrabajoUrgenteDetailSerializer,
    OfertaTrabajoSerializer,
    OfertaTrabajoCreateSerializer
)
from datetime import datetime


class TrabajoUrgenteViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    
    def _buscar_profesionales_cercanos(self, profesion_id, latitud, longitud, excluir_usuario_id=None):
        from django.db import connection
        
        lat_trabajo = float(latitud)
        lng_trabajo = float(longitud)
        
        query = """
        WITH profesionales_con_localizacion AS (
            SELECT DISTINCT ON (up.usuario_id)
                up.usuario_id,
                u.rango_mapa_km,
                l.latitud,
                l.longitud,
                ul.es_principal
            FROM usuario_profesion up
            INNER JOIN usuario u ON u.id = up.usuario_id
            INNER JOIN usuario_localizacion ul ON ul.usuario_id = up.usuario_id
            INNER JOIN localizacion l ON l.id = ul.localizacion_id
            WHERE up.profesion_id = %s
                AND up.deleted_at IS NULL
                AND ul.deleted_at IS NULL
                AND l.deleted_at IS NULL
                {excluir_clause}
            ORDER BY up.usuario_id, ul.es_principal DESC NULLS LAST
        ),
        profesionales_con_distancia AS (
            SELECT 
                usuario_id,
                rango_mapa_km,
                (
                    6371 * acos(
                        cos(radians(%s)) * 
                        cos(radians(latitud)) * 
                        cos(radians(longitud) - radians(%s)) + 
                        sin(radians(%s)) * 
                        sin(radians(latitud))
                    )
                ) AS distancia_km
            FROM profesionales_con_localizacion
        )
        SELECT usuario_id
        FROM profesionales_con_distancia
        WHERE distancia_km <= COALESCE(rango_mapa_km, 10.0)
        ORDER BY distancia_km ASC;
        """
        
        excluir_clause = ""
        params = [profesion_id, lat_trabajo, lng_trabajo, lat_trabajo]
        
        if excluir_usuario_id:
            excluir_clause = "AND up.usuario_id != %s"
            params.insert(1, excluir_usuario_id)
        
        query = query.format(excluir_clause=excluir_clause)
        
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            profesionales_cercanos = [row[0] for row in cursor.fetchall()]
        
        return profesionales_cercanos
    
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
        
        # --- NUEVOS CAMPOS ---
        fecha = serializer.validated_data['fecha'] # Date objeto
        hora = serializer.validated_data['hora']   # Time objeto
        # Combinamos ambos en un solo objeto datetime para el campo fecha_inicio
        fecha_inicio_combinada = datetime.combine(fecha, hora)
        # ---------------------

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
        
        # Creamos el trabajo incluyendo la fecha y hora
        trabajo = Trabajo.objects.create(
            usuario=usuario,
            descripcion=descripcion,
            esUrgente=True,
            status='pendiente_urgente',
            localizacion=localizacion,
            profesion_urgente=profesion,
            fecha_inicio=fecha_inicio_combinada, # <--- SE GUARDA AQUÍ
            radio_busqueda_km=None,
            es_domicilio_profesional=False
        )
        
        profesionales_cercanos = self._buscar_profesionales_cercanos(
            profesion_id, 
            latitud, 
            longitud,
            excluir_usuario_id=usuario.id
        )
        
        if profesionales_cercanos:
            notificar_usuarios_multiple.delay(
                usuarios_ids=profesionales_cercanos,
                titulo=f"Nuevo trabajo urgente de {profesion.nombre}",
                mensaje=descripcion[:100],
                data={
                    'deep_link': f'fixeo://trabajos/urgente/{trabajo.id}',
                    'entity_id': trabajo.id,
                    'tipo': 'nuevo_trabajo_urgente'
                }
            )
        
        return Response(
            TrabajoUrgenteDetailSerializer(trabajo).data,
            status=status.HTTP_201_CREATED
        )
    
    def list(self, request):
        usuario = request.user
        usuario_profesiones = UsuarioProfesion.objects.filter(usuario=usuario).values_list('profesion_id', flat=True)
        status_filter = request.query_params.get("status")

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
            profesion_urgente_id__in=usuario_profesiones
        ).exclude(
            usuario=usuario
        ).exclude(
            ofertas__profesional=usuario  
        ).select_related(
            'usuario',
            'localizacion',
            'profesion_urgente'
        ).distinct()
        
        if status_filter:
            trabajos_urgentes = trabajos_urgentes.filter(status=status_filter)

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
            mensaje=serializer.validated_data.get('mensaje', ''),
            fecha_inicio=serializer.validated_data.get('fecha_inicio')
        )
        
        notificar_usuario.delay(
            usuario_id=trabajo.usuario.id,
            titulo="Nueva oferta recibida",
            mensaje=f"{request.user.nombre} hizo una oferta de ${oferta.precio_ofertado}",
            data={
                'deep_link': f'fixeo://trabajos/urgente/{trabajo.id}/ofertas',
                'entity_id': oferta.id,
                'tipo': 'nueva_oferta'
            }
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
        
        tiempo_estimado_minutos = oferta.tiempo_estimado
        fecha_inicio = oferta.fecha_inicio or timezone.now()
        fecha_fin = fecha_inicio + timedelta(minutes=tiempo_estimado_minutos)
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
        
        notificar_usuario.delay(
            usuario_id=oferta.profesional.id,
            titulo="¡Tu oferta fue aceptada!",
            mensaje=f"Tu oferta de ${oferta.precio_ofertado} fue aceptada",
            data={
                'deep_link': f'fixeo://trabajos/{trabajo.id}',
                'entity_id': trabajo.id,
                'tipo': 'oferta_aceptada'
            }
        )
        
        ofertas_rechazadas = trabajo.ofertas.filter(status='rechazada').exclude(id=oferta.id)
        for oferta_rechazada in ofertas_rechazadas:
            notificar_usuario.delay(
                usuario_id=oferta_rechazada.profesional.id,
                titulo="Oferta no seleccionada",
                mensaje="El cliente seleccionó otra oferta para este trabajo",
                data={
                    'deep_link': f'fixeo://trabajos/urgente/{trabajo.id}',
                    'entity_id': trabajo.id,
                    'tipo': 'oferta_rechazada'
                }
            )
        
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

    @action(detail=False, methods=['get'], url_path='mis-ofertas')
    def mis_ofertas(self, request):
        usuario = request.user
        status_filter = request.query_params.get('status')

        # Obtener localización principal del usuario
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

        ofertas = OfertaTrabajo.objects.filter(
            profesional=usuario
        ).select_related(
            'trabajo',
            'trabajo__usuario',
            'trabajo__localizacion',
            'trabajo__profesion_urgente'
        )

        if status_filter:
            ofertas = ofertas.filter(status=status_filter)

        resultado = []

        for oferta in ofertas:
            trabajo = oferta.trabajo

            if trabajo.localizacion:
                distancia = calcular_distancia_km(
                    float(localizacion_usuario.localizacion.latitud),
                    float(localizacion_usuario.localizacion.longitud),
                    float(trabajo.localizacion.latitud),
                    float(trabajo.localizacion.longitud)
                )

                trabajo_data = TrabajoUrgenteDetailSerializer(trabajo).data

                resultado.append({
                    "oferta_id": oferta.id,
                    "status_oferta": oferta.status,
                    "precio_ofertado": oferta.precio_ofertado,
                    "tiempo_estimado": oferta.tiempo_estimado,
                    "mensaje": oferta.mensaje,
                    "created_at": oferta.created_at,
                    "distancia_km": round(distancia, 2),
                    "trabajo": trabajo_data
                })

        resultado.sort(key=lambda x: x['distancia_km'])

        return Response({
            'count': len(resultado),
            'trabajos': resultado
        })
    @action(detail=False, methods=['get'], url_path='mis-solicitudes')
    def mis_solicitudes(self, request):
        print("USER:", request.user.id, request.user)
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
