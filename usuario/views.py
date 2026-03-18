from localizacion.utils import calcular_distancia_km
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.db import transaction
from usuario.models import Usuario, PasswordResetToken
from usuario.utils import obtener_localizacion_usuario
from usuario_localizacion.models import UsuarioLocalizacion
from usuario_profesion.models import UsuarioProfesion
from usuario.serializers import (
    UsuarioSerializer, UsuarioCreateSerializer,
    ChangePasswordSerializer, LoginSerializer, RegistroSerializer,
    UpdateRangoMapaSerializer, FilterUsersMapaSerializer, UsuarioInMapaSerializer,
    UpdateUsuarioSerializer, ValidateEmailExistSerializer, SocialLoginSerializer,
    RequestPasswordResetSerializer, ConfirmPasswordResetSerializer
)
from localizacion.models import Localizacion
from empresas.utils import crear_empresa
from profesion.utils import obtener_profesion_por_id
from decimal import Decimal 
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.db.models import Avg
from decimal import Decimal
import math
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth
import resend
from django.conf import settings
from django.db import connection

SQL_QUERY = """
WITH empresas_ranked AS (
    SELECT
        e.id,
        e.nombre AS titulo,
        u.foto_url,
        u.rounded_foto_url,
        string_agg(DISTINCT p.nombre, ', ') AS profesiones_texto,
        e.latitud,
        e.longitud,
        e.descripcion,
        GREATEST(
            similarity(u.nombre, %s),
            similarity(u.apellido, %s),
            similarity(u.nombre || ' ' || u.apellido, %s),
            similarity(e.nombre, %s),
            MAX(COALESCE(similarity(p.nombre, %s), 0))
        ) AS rank
    FROM empresa e
    JOIN usuario u ON u.id = e.admin_id_id
    LEFT JOIN usuario_profesion up ON up.usuario_id = u.id
    LEFT JOIN profesion p ON p.id = up.profesion_id
    WHERE
        u.id != %s
        AND (
            u.nombre %% %s
            OR u.apellido %% %s
            OR (u.nombre || ' ' || u.apellido) %% %s
            OR u.nombre ILIKE %s
            OR u.apellido ILIKE %s
            OR e.nombre %% %s
            OR e.nombre ILIKE %s
            OR p.nombre %% %s
            OR p.nombre ILIKE %s
        )
    GROUP BY e.id, u.foto_url, u.rounded_foto_url, u.nombre, u.apellido, e.latitud, e.longitud, e.descripcion
)

SELECT
    'usuario' AS tipo,
    id,
    titulo,
    profesiones_texto AS extra,
    foto_url,
    rounded_foto_url,
    NULL::numeric AS precio,
    NULL::text AS codigo,
    NULL::text AS foto_producto,
    titulo AS empresa_nombre,
    id AS empresa_id,
    NULL::text AS ciudad,
    NULL::text AS pais,
    latitud,
    longitud,
    rank
FROM empresas_ranked

UNION ALL

SELECT
    'producto' AS tipo,
    pr.id,
    pr.nombre AS titulo,
    pr.descripcion AS extra,
    NULL,
    NULL,
    pr.precio,
    pr.codigo,
    pr.foto,
    e.nombre,
    e.id,
    NULL::text AS ciudad,
    NULL::text AS pais,
    e.latitud,
    e.longitud,
    GREATEST(
        similarity(pr.nombre, %s),
        COALESCE(similarity(pr.descripcion, %s), 0)
    ) AS rank
FROM producto pr
JOIN empresa e ON e.id = pr.empresa_id
JOIN usuario u ON u.id = e.admin_id_id
WHERE
    u.id != %s
    AND (
        pr.nombre %% %s
        OR pr.descripcion %% %s
        OR pr.codigo %% %s
        OR pr.nombre ILIKE %s
        OR pr.descripcion ILIKE %s
        OR pr.codigo ILIKE %s
    )

ORDER BY rank DESC
LIMIT 30;
"""

class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer

    def get_serializer_class(self):
        if self.action == 'create':
            return UsuarioCreateSerializer
        return UsuarioSerializer

    def get_permissions(self):
        if self.action in [
            'create', 'login', 'registro', 'validate_email', 'social_login',
            'request_reset_password', 'confirm_reset_password',  # ← agregá estos
            ]:
            return [AllowAny()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['post'], permission_classes=[AllowAny], url_path='validate-email')
    def validate_email(self, request):
        serializer = ValidateEmailExistSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        emailExist = Usuario.objects.filter(correo=serializer.validated_data['email']).exists()
        if emailExist:
            return Response(
                {'error': 'El correo ya está registrado'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(
            {'message': 'Correo disponible'},
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def registro(self, request):
        serializer = RegistroSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            with transaction.atomic():
                if serializer.validated_data['es_empresa']:
                    if not serializer.validated_data.get('latitude') or not serializer.validated_data.get('longitude'):
                        raise ValueError('Las coordenadas son requeridas para crear una empresa')
                
                usuario = Usuario.objects.create_user(
                    correo=serializer.validated_data['email'],
                    password=serializer.validated_data['password'],
                    nombre=serializer.validated_data['nombre'],
                    apellido=serializer.validated_data['apellido'],
                    foto_url=serializer.validated_data.get('foto_url', ''),
                    trabajo_domicilio=serializer.validated_data['trabajo_domicilio'],
                    trabajo_local=serializer.validated_data['trabajo_local'],
                    telefono=serializer.validated_data.get('telefono', ''),
                    is_owner_empresa=serializer.validated_data['es_empresa'],
                    rounded_foto_url=serializer.validated_data.get('rounded_foto_url', ''),
                )
                
                if serializer.validated_data.get('latitude') and serializer.validated_data.get('longitude'):
                    localizacion = Localizacion.objects.create(
                        ubicacion=serializer.validated_data.get('direction_name', ''),
                        latitud=serializer.validated_data['latitude'],
                        longitud=serializer.validated_data['longitude'],
                        address=serializer.validated_data.get('direction_name', ''),
                        city='',
                        country='',
                        county='',
                        state='',
                        isPrimary=True
                    )
                    
                    UsuarioLocalizacion.objects.create(
                        usuario=usuario,
                        localizacion=localizacion
                    )
                
                profesion_ids = serializer.validated_data.get('profesion_ids', [])
                for profesion_id in profesion_ids:
                    profesion = obtener_profesion_por_id(profesion_id)
                    if profesion:
                        UsuarioProfesion.objects.create(
                            usuario=usuario,
                            profesion=profesion
                        )
                
                if serializer.validated_data['es_empresa']:
                    localizacion_empresa = UsuarioLocalizacion.objects.filter(usuario=usuario).first()
                    crear_empresa(
                        nombre=f"{usuario.nombre} {usuario.apellido}",
                        ubicacion=serializer.validated_data.get('direction_name', ''),
                        latitud=serializer.validated_data['latitude'],
                        longitud=serializer.validated_data['longitude'],
                        admin_id=usuario,
                        descripcion='',
                        unipersonal=True,
                        localizacion=localizacion_empresa.localizacion if localizacion_empresa else None
                    )
                
                refresh = RefreshToken.for_user(usuario)
                user_data = UsuarioSerializer(usuario).data
                
                return Response({
                    'user': user_data,
                    'tokens': {
                        'refresh': str(refresh),
                        'access': str(refresh.access_token),
                    }
                }, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f'Error al crear el usuario: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def login(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = authenticate(
            username=serializer.validated_data['correo'],
            password=serializer.validated_data['password']
        )
        
        if user is None:
            return Response(
                {'error': 'Credenciales inválidas'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        refresh = RefreshToken.for_user(user)
        user_data = UsuarioSerializer(user).data
        
        return Response({
            'user': user_data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        })

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def logout(self, request):
        try:
            refresh_token = request.data.get('refresh_token')
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({'message': 'Logout exitoso'}, status=status.HTTP_200_OK)
        except Exception:
            return Response({'error': 'Token inválido'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
    
    @action(detail=False, methods=['patch', 'put'], permission_classes=[IsAuthenticated])
    def update_me(self, request):
        """
        Actualiza la información del usuario logueado
        
        Campos actualizables:
        - nombre
        - apellido
        - telefono
        - foto_url
        - trabajo_domicilio
        - trabajo_local
        - rango_mapa_km
        - auto_aprobacion_trabajos
        - defaultMessageReservation
        """
        usuario = request.user
        serializer = UpdateUsuarioSerializer(
            usuario, 
            data=request.data, 
            partial=request.method == 'PATCH'
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        user_data = UsuarioSerializer(usuario).data
        
        return Response({
            'message': 'Información actualizada exitosamente',
            'user': user_data
        })

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def change_password(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        if not user.check_password(serializer.validated_data['old_password']):
            return Response(
                {'error': 'Contraseña actual incorrecta'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        
        return Response({'message': 'Contraseña cambiada exitosamente'})

    @action(detail=False, methods=['post'], permission_classes=[AllowAny], url_path='request-reset-password')
    def request_reset_password(self, request):
        serializer = RequestPasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        usuario = Usuario.objects.filter(correo=email).first()

        if usuario:
            PasswordResetToken.objects.filter(usuario=usuario, used=False).update(used=True)

            reset_token = PasswordResetToken.objects.create(usuario=usuario)
            reset_url = f"{settings.FRONTEND_URL}/resetPassword?token={reset_token.token}"

            resend.api_key = settings.RESEND_API_KEY

            resend.Emails.send({
                # "from": "noreply@alavuelta.com",
                "from": "onboarding@resend.dev",
                "to":      ['alavueltaapp@gmail.com'],
                # "to":      [email],
                "subject": "Restablecer tu contraseña",
                "html": f"""
                <div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px 24px;background:#fff;border-radius:16px;">
                <div style="text-align:center;margin-bottom:32px;">
                    <div style="width:64px;height:64px;border-radius:16px;background:linear-gradient(135deg,#8972FD,#AFA0FF);
                                margin:0 auto;line-height:64px;text-align:center;">
                        <span style="font-size:28px;">🔐</span>
                    </div>
                </div>

                <h1 style="font-size:22px;font-weight:700;color:#111;margin:0 0 8px;">
                    Recuperar contraseña
                </h1>
                <p style="font-size:14px;color:#6B7280;margin:0 0 24px;line-height:1.6;">
                    Recibimos una solicitud para restablecer la contraseña de tu cuenta.
                    Si no fuiste vos, podés ignorar este correo.
                </p>

                <a href="{reset_url}"
                    style="display:block;width:100%;padding:16px;background:linear-gradient(135deg,#8972FD,#AFA0FF);
                            color:#fff;font-size:15px;font-weight:700;text-align:center;
                            border-radius:12px;text-decoration:none;box-sizing:border-box;
                            box-shadow:0 4px 20px rgba(137,114,253,0.4);">
                    Restablecer contraseña
                </a>

                <p style="font-size:12px;color:#9CA3AF;margin:24px 0 0;text-align:center;">
                    Este enlace expira en <strong>1 hora</strong>.
                </p>
                </div>
                """,
            })

        return Response({'message': 'Si el correo existe, recibirás un enlace.'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], permission_classes=[AllowAny], url_path='confirm-reset-password')
    def confirm_reset_password(self, request):
        serializer = ConfirmPasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token_value  = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']

        try:
            reset_token = PasswordResetToken.objects.select_related('usuario').get(token=token_value)
        except PasswordResetToken.DoesNotExist:
            return Response({'error': 'Token inválido o expirado.'}, status=status.HTTP_400_BAD_REQUEST)

        if not reset_token.is_valid():
            return Response({'error': 'El enlace expiró. Solicitá uno nuevo.'}, status=status.HTTP_400_BAD_REQUEST)

        usuario = reset_token.usuario
        usuario.set_password(new_password)
        usuario.save()

        reset_token.used = True
        reset_token.save()

        return Response({'message': 'Contraseña actualizada exitosamente.'}, status=status.HTTP_200_OK)


    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def mis_profesiones(self, request):
        """
        Obtiene las profesiones del usuario logueado
        """
        from profesion.serializers import ProfesionSerializer
        
        usuario_profesiones = request.user.usuario_profesiones.all()
        profesiones = [up.profesion for up in usuario_profesiones]
        
        serializer = ProfesionSerializer(profesiones, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def update_rango_mapa(self, request):
        """
        Actualiza el rango del mapa en kilómetros para el usuario logueado
        """
        serializer = UpdateRangoMapaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        usuario = request.user
        usuario.rango_mapa_km = serializer.validated_data['rango_mapa_km']
        usuario.save()
        
        return Response({
            'message': 'Rango del mapa actualizado exitosamente',
            'rango_mapa_km': float(usuario.rango_mapa_km)
        })

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated], url_path='rango-mapa')
    def filter_users_mapa(self, request):
            serializer = FilterUsersMapaSerializer(data=request.query_params)
            serializer.is_valid(raise_exception=True)

            north = Decimal(request.query_params['north'])
            south = Decimal(request.query_params['south'])
            east  = Decimal(request.query_params['east'])
            west  = Decimal(request.query_params['west'])

            profesion_id  = request.query_params.get('profesion_id')
            sort_by       = request.query_params.get('sort_by', 'mejor_valorados')  
            max_price     = request.query_params.get('max_price')
            is_urgent     = request.query_params.get('is_urgent') 

            usuarios_loc = UsuarioLocalizacion.objects.filter(
                localizacion__latitud__lte=north,
                localizacion__latitud__gte=south,
                localizacion__longitud__lte=east,
                localizacion__longitud__gte=west,
                localizacion__isPrimary=True,
                usuario__is_owner_empresa=True,
                usuario__is_active=True,
            ).select_related('usuario', 'localizacion').distinct()

            if profesion_id:
                usuarios_loc = usuarios_loc.filter(
                    usuario__usuario_profesiones__profesion_id=profesion_id
                )

            if max_price:
                usuarios_loc = usuarios_loc.filter(
                    usuario__servicios__precio__lte=Decimal(max_price)
                ).distinct()

            if is_urgent == 'true':
                usuarios_loc = usuarios_loc.filter(
                    usuario__trabajos_asignados__esUrgente=True
                ).distinct()

            center_lat = float((north + south) / 2)
            center_lng = float((east + west) / 2)
            
            results = []
            for ul in usuarios_loc:
                usuario = ul.usuario
                lat = float(ul.localizacion.latitud)
                lng = float(ul.localizacion.longitud)

                dlat = math.radians(lat - center_lat)
                dlng = math.radians(lng - center_lng)
                a = math.sin(dlat/2)**2 + math.cos(math.radians(center_lat)) * math.cos(math.radians(lat)) * math.sin(dlng/2)**2
                distance_km = 6371 * 2 * math.asin(math.sqrt(a))

                avg_rating = usuario.calificaciones_recibidas.aggregate(
                    avg=Avg('rating')
                )['avg'] or 0

                min_price = usuario.servicios.order_by('precio').values_list('precio', flat=True).first()

                results.append({
                    'usuario': usuario,
                    'distance_km': distance_km,
                    'avg_rating': avg_rating,
                    'min_price': float(min_price) if min_price else None,
                })

            # Ordenar
            if sort_by == 'mejor_valorados':
                results.sort(key=lambda x: x['avg_rating'], reverse=True)
            elif sort_by == 'mas_cercanos':
                results.sort(key=lambda x: x['distance_km'])
            elif sort_by == 'mejor_precio':
                results.sort(key=lambda x: (x['min_price'] is None, x['min_price'] or 0))

            return Response([
                UsuarioInMapaSerializer(r['usuario']).data
                for r in results
            ])
    
    @action(detail=False, methods=['get'], url_path='search')
    def search(self, request):
        q = request.query_params.get("q", "").strip()
        if not q:
            return Response({"error": "Parámetro q es requerido"}, status=400)

        like_q = f"%{q}%"
        user_id = request.user.id

        with connection.cursor() as cursor:
            cursor.execute(SQL_QUERY, [
                q, q, q, q, q,
                user_id,
                q, q, q,
                like_q, like_q,
                q, like_q,
                q, like_q,
                q, q,
                user_id,
                q, q, q,
                like_q, like_q, like_q,
            ])
            columns = [col[0] for col in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]

        return Response(results)
    
    @action(detail=True, methods=['get'], url_path='from-me')
    def from_me(self, request, pk=None):
        """
        Devuelve la distancia en KM entre el usuario logueado
        y otro usuario
        """
        usuario_origen = request.user
        usuario_destino = get_object_or_404(Usuario, pk=pk)

        loc_origen = obtener_localizacion_usuario(usuario_origen)
        loc_destino = obtener_localizacion_usuario(usuario_destino)

        if not loc_origen:
            return Response(
                {'error': 'El usuario logueado no tiene localización'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not loc_destino:
            return Response(
                {'error': 'El usuario destino no tiene localización'},
                status=status.HTTP_400_BAD_REQUEST
            )

        distancia = calcular_distancia_km(
            float(loc_origen.latitud),
            float(loc_origen.longitud),
            float(loc_destino.latitud),
            float(loc_destino.longitud),
        )

        return Response({
            'from_user': usuario_origen.id,
            'to_user': usuario_destino.id,
            'distance_km': distancia,
            'from_location': {
                'city': loc_origen.city,
                'country': loc_origen.country,
            },
            'to_location': {
                'city': loc_destino.city,
                'country': loc_destino.country,
            }
        })
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated], url_path='top-nacionales')
    def top_nacionales(self, request):
        limit = int(request.query_params.get('limit', 50))
        sort_by = request.query_params.get('sort_by', 'mejor_valorados')

        usuarios = Usuario.objects.filter(
            is_owner_empresa=True,
            is_active=True,
        ).annotate(
            avg_rating=Avg('calificaciones_recibidas__rating')
        )

        if sort_by == 'mejor_valorados':
            usuarios = usuarios.order_by('-avg_rating')
        elif sort_by == 'mejor_precio':
            usuarios = usuarios.order_by('servicios__precio')

        return Response(UsuarioInMapaSerializer(usuarios[:limit], many=True).data)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated], url_path='top-zona')
    def top_zona(self, request):
        """Top usuarios dentro de bounds, con límite"""
        north = Decimal(request.query_params['north'])
        south = Decimal(request.query_params['south'])
        east  = Decimal(request.query_params['east'])
        west  = Decimal(request.query_params['west'])
        limit = int(request.query_params.get('limit', 50))
        sort_by = request.query_params.get('sort_by', 'mejor_valorados')

        usuarios_loc = UsuarioLocalizacion.objects.filter(
            localizacion__latitud__lte=north,
            localizacion__latitud__gte=south,
            localizacion__longitud__lte=east,
            localizacion__longitud__gte=west,
            localizacion__isPrimary=True,
            usuario__is_owner_empresa=True,
            usuario__is_active=True,
        ).select_related('usuario', 'localizacion').distinct()

        results = []
        for ul in usuarios_loc:
            avg_rating = ul.usuario.calificaciones_recibidas.aggregate(avg=Avg('rating'))['avg'] or 0
            min_price = ul.usuario.servicios.order_by('precio').values_list('precio', flat=True).first()
            results.append({
                'usuario': ul.usuario,
                'avg_rating': avg_rating,
                'min_price': float(min_price) if min_price else None,
            })

        if sort_by == 'mejor_valorados':
            results.sort(key=lambda x: x['avg_rating'], reverse=True)
        elif sort_by == 'mejor_precio':
            results.sort(key=lambda x: (x['min_price'] is None, x['min_price'] or 0))

        return Response([
            UsuarioInMapaSerializer(r['usuario']).data
            for r in results[:limit]
        ])
    
    @action(detail=False, methods=['post'], permission_classes=[AllowAny], url_path='social-login')
    def social_login(self, request):
        serializer = SocialLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        firebase_token = serializer.validated_data['firebase_token']
        email          = serializer.validated_data['email']
        nombre         = serializer.validated_data.get('nombre', '')
        foto_url       = serializer.validated_data.get('foto_url', '')

        try:
            firebase_auth.verify_id_token(firebase_token)
        except Exception:
            return Response(
                {'error': 'Token de Firebase inválido'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        usuario = Usuario.objects.filter(correo=email).first()

        if usuario:
            refresh = RefreshToken.for_user(usuario)
            return Response({
                'user': UsuarioSerializer(usuario).data,
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                }
            })
        else:
            return Response(
                {'error': 'Usuario no registrado', 'isNewUser': True},
                status=status.HTTP_404_NOT_FOUND
            )