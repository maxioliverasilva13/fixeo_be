from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.db.models import Q, F, FloatField, Count
from django.db.models.functions import ACos, Cos, Sin, Radians
from django.db.models.expressions import Value
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
from localizacion.models import Localizacion
from localizacion.utils import calcular_distancia_km
from mensajeria.models import Chat
from profesion.models import Profesion
from trabajos.utils import filtrar_trabajos_por_distancia_sql
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
from mensajeria.models import Recurso
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from empresas.models import Empresa


def _moneda_profesional(usuario) -> str:
    empresa = Empresa.objects.filter(admin_id=usuario).first()
    if empresa:
        return empresa.moneda_local
    return 'USD'


def _sort_por_fecha_reciente(items, fecha_key):
    """Ordena dicts serializados: más recientes primero (created_at / fecha_inicio ISO)."""
    def key_fn(item):
        val = item
        for part in fecha_key.split('.'):
            val = (val or {}).get(part) if isinstance(val, dict) else None
        if val is None:
            return ''
        return val.isoformat() if hasattr(val, 'isoformat') else str(val)

    items.sort(key=key_fn, reverse=True)


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

        from usuario.zonas_utils import filtrar_profesionales_fuera_zonas_exclusion
        return filtrar_profesionales_fuera_zonas_exclusion(
            profesionales_cercanos,
            lat_trabajo,
            lng_trabajo,
        )
    
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
        currency = serializer.validated_data.get('currency', None)

        fecha = serializer.validated_data['fecha']
        hora = serializer.validated_data['hora']
        fecha_inicio_combinada = datetime.combine(fecha, hora)

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
            UsuarioLocalizacion.objects.create(
                usuario=usuario,
                localizacion=localizacion,
                es_principal=False
            )
        
        trabajo = Trabajo.objects.create(
            usuario=usuario,
            descripcion=descripcion,
            esUrgente=True,
            status='pendiente_urgente',
            localizacion=localizacion,
            profesion_urgente=profesion,
            fecha_inicio=fecha_inicio_combinada,
            radio_busqueda_km=None,
            es_domicilio_profesional=False,
            currency=currency, 
        )

        fotos = serializer.validated_data.get('fotos', [])

        if fotos:
            recursos = [
                Recurso(
                    url=foto,
                    tipo='imagen',
                    nombre='imagen_trabajo',
                    trabajo=trabajo
                )
                for foto in fotos
            ]

            Recurso.objects.bulk_create(recursos)
        
        profesionales_cercanos = self._buscar_profesionales_cercanos(
            profesion_id, 
            latitud, 
            longitud,
            excluir_usuario_id=usuario.id
        )

        print("profesionales_cercanos")
        print(profesionales_cercanos)
        
        if profesionales_cercanos:
            notificar_usuarios_multiple.delay(
                usuarios_ids=profesionales_cercanos,
                titulo=f"Nuevo trabajo urgente de {profesion.nombre}",
                mensaje=descripcion[:100],
                data={
                    'deep_link': f'/trabajos/urgente/{trabajo.id}',
                    'entity_id': trabajo.id,
                    'tipo': 'nuevo_trabajo_urgente'
                }
            )
        
        return Response(
            TrabajoUrgenteDetailSerializer(trabajo, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )

    def _get_localizacion_usuario(self, usuario):
        localizacion = UsuarioLocalizacion.objects.filter(
            usuario=usuario,
            localizacion__isPrimary=True
        ).select_related('localizacion').first()
        
        if not localizacion:
            localizacion = UsuarioLocalizacion.objects.filter(
                usuario=usuario
            ).select_related('localizacion').first()
        
        return localizacion
    
    def list(self, request):
        usuario = request.user
        usuario_profesiones = UsuarioProfesion.objects.filter(usuario=usuario).values_list('profesion_id', flat=True)
        status_filter = request.query_params.get("status")
        filter_param = request.query_params.get("filter", "not_applied")
        sort_param = request.query_params.get("sort", "recent")

        if not usuario_profesiones:
            return Response({
                'message': 'No tienes profesiones configuradas',
                'trabajos': []
            })
        
        localizacion_usuario = self._get_localizacion_usuario(usuario)
        
        if not localizacion_usuario:
            return Response({
                'message': 'No tienes localización configurada',
                'trabajos': []
            })
        
        trabajos_urgentes_qs = Trabajo.objects.filter(
            esUrgente=True,
            profesion_urgente_id__in=usuario_profesiones,
            fecha_inicio__gte=timezone.now(),
        ).exclude(
            usuario=usuario
        ).select_related(
            'usuario',
            'localizacion',
            'profesion_urgente'
        )

        if filter_param == "no_offers":
            trabajos_urgentes_qs = trabajos_urgentes_qs.annotate(
                num_ofertas=Count("ofertas", distinct=True)
            ).filter(num_ofertas=0).exclude(ofertas__profesional=usuario)
        elif filter_param == "not_applied":
            trabajos_urgentes_qs = trabajos_urgentes_qs.exclude(
                ofertas__profesional=usuario,
                ofertas__status__in=['pendiente', 'aceptada'],
            )
        
        if status_filter:
            trabajos_urgentes_qs = trabajos_urgentes_qs.filter(status=status_filter)

        trabajos_urgentes_qs = trabajos_urgentes_qs.distinct()

        trabajo_ids_cercanos = filtrar_trabajos_por_distancia_sql(
            trabajos_urgentes_qs,
            usuario,
            localizacion_usuario.localizacion.latitud,
            localizacion_usuario.localizacion.longitud
        )
        
        trabajos_cercanos = Trabajo.objects.filter(
            id__in=trabajo_ids_cercanos
        ).select_related('usuario', 'localizacion', 'profesion_urgente').prefetch_related('ofertas')

        if sort_param == "soonest":
            trabajos_cercanos = trabajos_cercanos.order_by('fecha_inicio', '-created_at')
        elif sort_param == "fewest_offers":
            trabajos_cercanos = trabajos_cercanos.annotate(
                num_ofertas=Count('ofertas', distinct=True)
            ).order_by('num_ofertas', '-created_at')
        else:
            trabajos_cercanos = trabajos_cercanos.order_by('-created_at')

        resultado = []
        for trabajo in trabajos_cercanos:
            distancia = calcular_distancia_km(
                float(localizacion_usuario.localizacion.latitud),
                float(localizacion_usuario.localizacion.longitud),
                float(trabajo.localizacion.latitud),
                float(trabajo.localizacion.longitud)
            )
            
            trabajo_data = TrabajoUrgenteDetailSerializer(
                trabajo,
                context={'request': request},
            ).data
            trabajo_data['distancia_km'] = round(distancia, 2)
            resultado.append(trabajo_data)

        return Response({
            'count': len(resultado),
            'trabajos': resultado
        })

    def retrieve(self, request, pk=None):
        try:
            trabajo = Trabajo.objects.get(id=pk, esUrgente=True)
        except Trabajo.DoesNotExist:
            return Response({'error': 'Trabajo urgente no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        
        return Response(
            TrabajoUrgenteDetailSerializer(trabajo, context={'request': request}).data
        )
    
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

        if trabajo.localizacion_id and trabajo.localizacion:
            from usuario.zonas_utils import obtener_zonas_activas, punto_en_zona_exclusion
            if punto_en_zona_exclusion(
                trabajo.localizacion.latitud,
                trabajo.localizacion.longitud,
                obtener_zonas_activas(request.user),
            ):
                return Response(
                    {'error': 'Este trabajo está en una zona donde indicaste que no trabajás.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        
        serializer = OfertaTrabajoCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        currency = serializer.validated_data.get('currency') or _moneda_profesional(request.user)

        existing = OfertaTrabajo.objects.filter(
            trabajo=trabajo,
            profesional=request.user,
        ).first()

        if existing:
            if existing.status != 'rechazada':
                return Response(
                    {'error': 'Ya has realizado una oferta para este trabajo'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            existing.precio_ofertado = serializer.validated_data['precio_ofertado']
            existing.currency = currency
            existing.tiempo_estimado = serializer.validated_data['tiempo_estimado']
            existing.mensaje = serializer.validated_data.get('mensaje', '')
            existing.fecha_inicio = serializer.validated_data.get('fecha_inicio')
            existing.status = 'pendiente'
            existing.save()
            oferta = existing
            is_reoffer = True
        else:
            oferta = OfertaTrabajo.objects.create(
                trabajo=trabajo,
                profesional=request.user,
                precio_ofertado=serializer.validated_data['precio_ofertado'],
                currency=currency,
                tiempo_estimado=serializer.validated_data['tiempo_estimado'],
                mensaje=serializer.validated_data.get('mensaje', ''),
                fecha_inicio=serializer.validated_data.get('fecha_inicio')
            )
            is_reoffer = False
        
        notificar_usuario.delay(
            usuario_id=trabajo.usuario.id,
            titulo="Nueva oferta recibida" if not is_reoffer else "Oferta actualizada",
            mensaje=f"{request.user.nombre} hizo una oferta de ${oferta.precio_ofertado}",
            data={
                'deep_link': f'/trabajos/urgente/{trabajo.id}/ofertas',
                'entity_id': oferta.id,
                'tipo': 'nueva_oferta'
            }
        )
        
        return Response(
            OfertaTrabajoSerializer(oferta).data,
            status=status.HTTP_200_OK if is_reoffer else status.HTTP_201_CREATED
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
        
        ofertas = trabajo.ofertas.filter(status='pendiente').select_related(
            'profesional'
        ).order_by('-created_at')
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
        trabajo.currency = oferta.currency or _moneda_profesional(oferta.profesional)
        trabajo.fecha_inicio = fecha_inicio
        trabajo.fecha_fin = fecha_fin
        trabajo.disponibilidad = disponibilidad_ocupada
        trabajo.save(update_fields=[
            'status', 'profesional', 'precio_final', 'currency',
            'fecha_inicio', 'fecha_fin', 'disponibilidad'
        ])

        trabajo.refresh_from_db()
        
        trabajo.ofertas.exclude(id=oferta.id).update(status='rechazada')
        
        chat = Chat.objects.filter(
            Q(sender=trabajo.usuario, receiver=oferta.profesional) |
            Q(sender=oferta.profesional, receiver=trabajo.usuario)
        ).first()

        if not chat:
            chat = Chat.objects.create(
                sender=trabajo.usuario,
                receiver=oferta.profesional,
                trabajo=trabajo
            )

            channel_layer = get_channel_layer()
            room_name = f"usuario_channel_{chat.receiver.id}"

            async_to_sync(channel_layer.group_send)(f'chat_{room_name}', {
                'type': 'chat_message',
                'message': '',
                'user_id': chat.sender.id,
                'leido': False,
                'chat_id': chat.id,
                'chat': {
                    'id': chat.id,
                    'sender_id': chat.sender.id,
                    'sender_nombre': f"{chat.sender.nombre} {chat.sender.apellido}",
                    'receiver_id': chat.receiver.id,
                    'receiver_nombre': f"{chat.receiver.nombre} {chat.receiver.apellido}",
                    'trabajo_id': chat.trabajo.id if chat.trabajo else None,
                    'ultimo_mensaje_at': chat.created_at.isoformat(),
                }
            })
        
        notificar_usuario.delay(
            usuario_id=oferta.profesional.id,
            titulo="¡Tu oferta fue aceptada!",
            mensaje=f"Tu oferta de ${oferta.precio_ofertado} fue aceptada",
            data={
                'deep_link': f'/trabajos/{trabajo.id}',
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
                    'deep_link': f'/trabajos/urgente/{trabajo.id}',
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

        if oferta.status != 'pendiente':
            return Response(
                {'error': 'Solo se pueden rechazar solicitudes pendientes'},
                status=status.HTTP_400_BAD_REQUEST
            )

        motivo = (request.data.get('motivo') or '').strip()
        if len(motivo) < 5:
            return Response(
                {'error': 'Indicá un motivo de al menos 5 caracteres'},
                status=status.HTTP_400_BAD_REQUEST
            )

        oferta.status = 'rechazada'
        oferta.motivo_rechazo = motivo
        oferta.save(update_fields=['status', 'motivo_rechazo', 'updated_at'])

        notificar_usuario.delay(
            usuario_id=oferta.profesional.id,
            titulo="Tu solicitud no fue seleccionada",
            mensaje=motivo[:120],
            data={
                'deep_link': f'/trabajos/urgente/{trabajo.id}',
                'entity_id': trabajo.id,
                'tipo': 'oferta_rechazada',
                'motivo_rechazo': motivo,
            }
        )
        
        return Response({
            'message': 'Oferta rechazada exitosamente',
            'oferta': OfertaTrabajoSerializer(oferta).data
        })

    @action(detail=False, methods=['get'], url_path='mis-ofertas')
    def mis_ofertas(self, request):
        usuario = request.user
        status_filter = request.query_params.get('status')

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
        ).order_by('-trabajo__created_at', '-created_at')

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

                trabajo_data = TrabajoUrgenteDetailSerializer(
                    trabajo,
                    context={'request': request},
                ).data

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

        _sort_por_fecha_reciente(resultado, 'trabajo.created_at')

        return Response({
            'count': len(resultado),
            'trabajos': resultado
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
            'trabajos': TrabajoUrgenteDetailSerializer(
                trabajos,
                many=True,
                context={'request': request},
            ).data
        })

    @action(detail=True, methods=['post'], url_path='cancelar')
    @transaction.atomic
    def cancelar_trabajo(self, request, pk=None):
        """
        Cancela un trabajo urgente.
        Solo el creador (cliente) puede cancelar.
        Solo se puede cancelar si está en estado 'pendiente_urgente'.
        """
        try:
            trabajo = Trabajo.objects.get(id=pk, esUrgente=True)
        except Trabajo.DoesNotExist:
            return Response({'error': 'Trabajo urgente no encontrado'}, status=status.HTTP_404_NOT_FOUND)

        if trabajo.usuario != request.user:
            return Response(
                {'error': 'Solo el creador del trabajo puede cancelarlo'},
                status=status.HTTP_403_FORBIDDEN
            )

        if trabajo.status == 'cancelado':
            return Response(
                {'error': 'El trabajo ya está cancelado'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if trabajo.status != 'pendiente_urgente':
            return Response(
                {'error': f'No se puede cancelar un trabajo en estado "{trabajo.status}"'},
                status=status.HTTP_400_BAD_REQUEST
            )

        trabajo.status = 'cancelado'
        trabajo.save(update_fields=['status'])

        ofertas_pendientes = trabajo.ofertas.filter(status='pendiente')
        for oferta in ofertas_pendientes:
            oferta.status = 'rechazada'
            oferta.save(update_fields=['status'])

            notificar_usuario.delay(
                usuario_id=oferta.profesional.id,
                titulo="Trabajo cancelado",
                mensaje="El cliente canceló el trabajo urgente",
                data={
                    'deep_link': f'/trabajos/urgente/{trabajo.id}',
                    'entity_id': trabajo.id,
                    'tipo': 'trabajo_urgente_cancelado'
                }
            )

        return Response({
            'message': 'Trabajo urgente cancelado exitosamente',
            'trabajo': TrabajoUrgenteDetailSerializer(trabajo).data
        }, status=status.HTTP_200_OK)
