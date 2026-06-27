from localizacion.utils import calcular_distancia_km
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.db import transaction
from usuario.models import Usuario, PasswordResetToken
from usuario.utils import obtener_localizacion_usuario, foto_usuario_api
from usuario_localizacion.models import UsuarioLocalizacion
from usuario_profesion.models import UsuarioProfesion
from usuario.serializers import (
    UsuarioSerializer, UsuarioCreateSerializer,
    ChangePasswordSerializer, LoginSerializer, RegistroSerializer,
    UpdateRangoMapaSerializer, FilterUsersMapaSerializer, UsuarioInMapaSerializer,
    UpdateUsuarioSerializer, ValidateEmailExistSerializer, SocialLoginSerializer,
    RequestPasswordResetSerializer, ConfirmPasswordResetSerializer,
    AdminUsuarioSerializer, AdminUsuarioUpdateSerializer
)
from localizacion.models import Localizacion
from empresas.models import Empresa
from empresas.utils import crear_empresa, validar_nombre_empresa_unico
from suscripciones.models import Subscripcion
# Columna real en BD para admin_id (p. ej. admin_id_id); el SQL evita suposiciones.
_EMPRESA_ADMIN_FK_COL = Empresa._meta.get_field("admin_id").column
from profesion.utils import obtener_profesion_por_id
from decimal import Decimal 
from django.shortcuts import get_object_or_404
from django.db.models import Q, F
from decimal import Decimal
import math
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth
import resend
from django.conf import settings
from django.db import connection
from django.db.models import Min

def _precio_para_filtro(r: dict) -> float | None:
    if r.get('tipo') == 'producto':
        p = r.get('precio')
    else:
        p = r.get('precio_servicio') or r.get('precio')
    return float(p) if p is not None else None


from usuario.mapa_helpers import (
    batch_visibility_data as _batch_visibility_data,
    es_visible_en_mapa as _es_visible_en_mapa,
    resolve_map_users_from_bounds,
    resolve_map_users_national,
    serialize_usuarios_mapa,
)

SQL_QUERY = f"""
SELECT *
FROM (
    SELECT
        'usuario' AS tipo,
        u.id,
        CASE
            WHEN e.id IS NOT NULL THEN e.nombre
            ELSE NULLIF(
                TRIM(CONCAT_WS(' ', NULLIF(TRIM(u.nombre), ''), NULLIF(TRIM(u.apellido), ''))),
                ''
            )
        END AS titulo,
        string_agg(DISTINCT p.nombre, ', ') AS extra,
        u.foto_url,
        u.rounded_foto_url,
        NULL::numeric AS precio,
        NULL::text AS codigo,
        NULL::text AS foto_producto,
        CASE WHEN e.id IS NOT NULL THEN e.nombre ELSE NULL::text END AS empresa_nombre,
        e.id AS empresa_id,
        NULL::text AS ciudad,
        NULL::text AS pais,
        COALESCE(e.latitud, loc.latitud) AS latitud,
        COALESCE(e.longitud, loc.longitud) AS longitud,
        CASE WHEN e.id IS NOT NULL THEN
            GREATEST(
                similarity(e.nombre, %s),
                COALESCE(similarity(e.descripcion, %s), 0),
                COALESCE(similarity(e.ubicacion, %s), 0),
                COALESCE(MAX(similarity(p.nombre, %s)), 0)
            )
        ELSE
            GREATEST(
                similarity(u.nombre, %s),
                similarity(u.apellido, %s),
                COALESCE(MAX(similarity(p.nombre, %s)), 0)
            )
        END AS rank,
        u.rating,
        EXISTS(
            SELECT 1 FROM trabajo t
            WHERE t.profesional_id = u.id AND t."esUrgente" = true
        ) AS es_urgente,
        array_agg(DISTINCT p.id) FILTER (WHERE p.id IS NOT NULL) AS profesion_ids,
        NULL::numeric AS precio_servicio,
        NULL::integer AS producto_id,
        u.cant_calif
    FROM usuario u
    LEFT JOIN LATERAL (
        SELECT
            e0.id,
            e0.nombre,
            e0.descripcion,
            e0.ubicacion,
            e0.latitud,
            e0.longitud
        FROM empresa e0
        WHERE e0.{_EMPRESA_ADMIN_FK_COL} = u.id
          AND NOT COALESCE(e0.is_deleted, false)
        ORDER BY e0.id
        LIMIT 1
    ) e ON TRUE
    LEFT JOIN usuario_localizacion ul ON ul.usuario_id = u.id AND ul.es_principal = true
    LEFT JOIN localizacion loc ON loc.id = ul.localizacion_id
    LEFT JOIN usuario_profesion up ON up.usuario_id = u.id
    LEFT JOIN profesion p ON p.id = up.profesion_id
    WHERE
        u.id != %s
        AND u.is_active = true
        AND (
            (
                e.id IS NOT NULL
                AND (
                    e.nombre %% %s
                    OR e.nombre ILIKE %s
                    OR e.descripcion %% %s
                    OR e.descripcion ILIKE %s
                    OR e.ubicacion %% %s
                    OR e.ubicacion ILIKE %s
                    OR p.nombre %% %s
                    OR p.nombre ILIKE %s
                )
            )
            OR (
                e.id IS NULL
                AND (
                    u.nombre %% %s
                    OR u.nombre ILIKE %s
                    OR u.apellido %% %s
                    OR u.apellido ILIKE %s
                    OR p.nombre %% %s
                    OR p.nombre ILIKE %s
                )
            )
        )
    GROUP BY u.id, u.foto_url, u.rounded_foto_url, u.nombre, u.apellido, u.cant_calif,
        e.id, e.nombre, e.descripcion, e.ubicacion, e.latitud, e.longitud,
        loc.latitud, loc.longitud

    UNION ALL

    SELECT
        'producto' AS tipo,
        u.id,
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
        ) AS rank,
        0::numeric AS rating,
        false AS es_urgente,
        NULL::integer[] AS profesion_ids,
        NULL::numeric AS precio_servicio,
        pr.id AS producto_id,
        0::integer AS cant_calif
    FROM producto pr
    JOIN empresa e ON e.id = pr.empresa_id AND NOT COALESCE(e.is_deleted, false)
    JOIN usuario u ON u.id = e.{_EMPRESA_ADMIN_FK_COL}
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
) combined
ORDER BY rank DESC
LIMIT %s;
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
                
                es_empresa = serializer.validated_data['es_empresa']
                rango_mapa = serializer.validated_data.get('rango_mapa_km')
                if es_empresa and rango_mapa is None:
                    rango_mapa = Decimal('10.00')

                usuario = Usuario.objects.create_user(
                    correo=serializer.validated_data['email'],
                    password=serializer.validated_data['password'],
                    nombre=serializer.validated_data['nombre'],
                    apellido=serializer.validated_data['apellido'],
                    foto_url=serializer.validated_data.get('foto_url', ''),
                    trabajo_domicilio=serializer.validated_data['trabajo_domicilio'],
                    trabajo_local=serializer.validated_data['trabajo_local'],
                    telefono=serializer.validated_data.get('telefono', ''),
                    is_owner_empresa=es_empresa,
                    rounded_foto_url=serializer.validated_data.get('rounded_foto_url', ''),
                    rango_mapa_km=rango_mapa if es_empresa else Decimal('10.00'),
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
                        localizacion=localizacion,
                        es_principal=True,
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
                    nombre_empresa = (
                        serializer.validated_data.get('nombre_empresa') or ''
                    ).strip()
                    if not nombre_empresa:
                        nombre_empresa = f"{usuario.nombre} {usuario.apellido}".strip()
                    if not validar_nombre_empresa_unico(nombre_empresa):
                        raise ValueError(
                            f"Ya existe una empresa con el nombre '{nombre_empresa}'"
                        )
                    crear_empresa(
                        nombre=nombre_empresa,
                        ubicacion=serializer.validated_data.get('direction_name', ''),
                        latitud=serializer.validated_data['latitude'],
                        longitud=serializer.validated_data['longitude'],
                        admin_id=usuario,
                        descripcion='',
                        unipersonal=True,
                        localizacion=localizacion_empresa.localizacion if localizacion_empresa else None,
                        vende_productos=serializer.validated_data.get('vende_productos', False),
                        vende_servicios=serializer.validated_data.get('vende_servicios', True),
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

        if user.is_deleted or not user.is_active:
            return Response(
                {'error': 'Esta cuenta fue eliminada'},
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
        if request.user.is_deleted or not request.user.is_active:
            return Response(
                {'error': 'Esta cuenta fue eliminada'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated], url_path='admin/buscar')
    def admin_buscar_usuarios(self, request):
        if not (request.user.is_staff or request.user.is_superuser):
            return Response({'error': 'Sin permisos'}, status=status.HTTP_403_FORBIDDEN)

        q = request.query_params.get('q', '').strip()
        if not q:
            return Response({'error': 'Parámetro q requerido'}, status=status.HTTP_400_BAD_REQUEST)

        from suscripciones.models import Subscripcion
        from django.utils import timezone

        filtro = Q(nombre__icontains=q) | Q(apellido__icontains=q) | Q(correo__icontains=q)
        if q.isdigit():
            filtro |= Q(id=int(q))

        usuarios = Usuario.objects.filter(filtro).select_related('rol')[:20]

        resultado = []
        for u in usuarios:
            sub = (
                Subscripcion.objects
                .filter(user_id=u, cancelada=False, expiracion__gt=timezone.now())
                .select_related('plan_id')
                .order_by('-created_at')
                .first()
            )
            resultado.append({
                'id': u.id,
                'nombre': u.nombre,
                'apellido': u.apellido,
                'correo': u.correo,
                'rol': u.rol.nombre if u.rol else ('owner' if u.is_owner_empresa else 'usuario'),
                'fecha_registro': u.created_at,
                'suscripcion': {
                    'activa': True,
                    'plan': sub.plan_id.nombre if sub and sub.plan_id else None,
                    'fecha_vencimiento': sub.expiracion,
                    'jobs_restantes': sub.jobs_restantes,
                } if sub else None,
            })

        return Response(resultado)


    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated], url_path='admin/stats')
    def admin_usuario_stats(self, request, pk=None):
        if not (request.user.is_staff or request.user.is_superuser):
            return Response({'error': 'Sin permisos'}, status=status.HTTP_403_FORBIDDEN)

        from suscripciones.models import Subscripcion
        from django.utils import timezone

        u = get_object_or_404(Usuario.objects.select_related('rol'), pk=pk)
        sub = (
            Subscripcion.objects
            .filter(user_id=u, cancelada=False, expiracion__gt=timezone.now())
            .select_related('plan_id')
            .order_by('-created_at')
            .first()
        )

        return Response({
            'id': u.id,
            'nombre': u.nombre,
            'apellido': u.apellido,
            'correo': u.correo,
            'rol': u.rol.nombre if u.rol else ('owner' if u.is_owner_empresa else 'usuario'),
            'fecha_registro': u.created_at,
            'suscripcion': {
                'activa': True,
                'plan': sub.plan_id.nombre if sub and sub.plan_id else None,
                'fecha_vencimiento': sub.expiracion,
                'jobs_restantes': sub.jobs_restantes,
            } if sub else None,
        })


    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated], url_path='admin/extender-suscripcion')
    def admin_extender_suscripcion(self, request):
        if not (request.user.is_staff or request.user.is_superuser):
            return Response({'error': 'Sin permisos'}, status=status.HTTP_403_FORBIDDEN)

        from suscripciones.models import Subscripcion
        from django.utils import timezone
        from datetime import timedelta

        usuario_id = request.data.get('usuario_id')
        dias       = int(request.data.get('dias', 30))
        jobs_extra = int(request.data.get('jobs_extra', 0))

        if not usuario_id:
            return Response({'error': 'usuario_id requerido'}, status=status.HTTP_400_BAD_REQUEST)

        u = get_object_or_404(Usuario, pk=usuario_id)
        sub = (
            Subscripcion.objects
            .filter(user_id=u, cancelada=False, expiracion__gt=timezone.now())
            .order_by('-created_at')
            .first()
        )

        if not sub:
            return Response({'error': 'El usuario no tiene suscripción activa'}, status=status.HTTP_404_NOT_FOUND)

        base = sub.expiracion if sub.expiracion > timezone.now() else timezone.now()
        sub.expiracion = base + timedelta(days=dias)

        if jobs_extra > 0:
            sub.jobs_restantes = (sub.jobs_restantes or 0) + jobs_extra

        sub.save(update_fields=['expiracion', 'jobs_restantes'])

        return Response({
            'message': f'Suscripción extendida {dias} días' + (f' y {jobs_extra} jobs agregados' if jobs_extra else ''),
            'nueva_expiracion': sub.expiracion,
            'jobs_restantes': sub.jobs_restantes,
        })

    @action(detail=False, methods=['patch', 'put'], permission_classes=[IsAuthenticated], url_path='update_me')
    def update_me(self, request):
        usuario = request.user

        serializer = UpdateUsuarioSerializer(
            usuario,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        user_data = UsuarioSerializer(usuario).data

        return Response({
            'message': 'Información actualizada exitosamente',
            'user': user_data
        })

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated], url_path='delete_me')
    def delete_me(self, request):
        from django.utils import timezone
        from notificaciones.models import DeviceToken

        usuario = request.user

        if usuario.is_deleted or not usuario.is_active:
            return Response(
                {'error': 'La cuenta ya fue eliminada'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        refresh_token = request.data.get('refresh_token')
        if refresh_token:
            try:
                RefreshToken(refresh_token).blacklist()
            except Exception:
                pass

        usuario.is_deleted = True
        usuario.is_active = False
        usuario.deleted_at = timezone.now()
        usuario.save(update_fields=['is_deleted', 'is_active', 'deleted_at'])

        DeviceToken.objects.filter(usuario=usuario).delete()

        return Response(
            {'message': 'Cuenta eliminada exitosamente'},
            status=status.HTTP_200_OK,
        )

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
            try:
                limit = int(request.query_params.get('limit', 50))
            except (TypeError, ValueError):
                limit = 50
            limit = max(1, min(limit, 100))

            north = Decimal(request.query_params['north'])
            south = Decimal(request.query_params['south'])
            east  = Decimal(request.query_params['east'])
            west  = Decimal(request.query_params['west'])

            profesion_id  = request.query_params.get('profesion_id')
            sort_by       = request.query_params.get('sort_by', 'mejor_valorados')
            max_price     = request.query_params.get('max_price')
            is_urgent     = request.query_params.get('is_urgent')

            usuarios = resolve_map_users_from_bounds(
                north=north,
                south=south,
                east=east,
                west=west,
                limit=limit,
                sort_by=sort_by,
                profesion_id=profesion_id,
                max_price=max_price,
                is_urgent=is_urgent,
            )
            return Response(serialize_usuarios_mapa(usuarios))
    
    @action(detail=False, methods=['get'], url_path='search')
    def search(self, request):
        q = request.query_params.get("q", "").strip()
        if not q:
            return Response({"error": "Parámetro q es requerido"}, status=400)
        
        limit = int(request.query_params.get("limit", 50))
        lim = max(1, min(limit, 100))

        profesion_id = request.query_params.get('profesion_id')
        sort_by      = request.query_params.get('sort_by')
        max_price    = request.query_params.get('max_price')
        is_urgent    = request.query_params.get('is_urgent')

        like_q  = f"%{q}%"
        user_id = request.user.id

        with connection.cursor() as cursor:
            cursor.execute(SQL_QUERY, [
                # usuario: rank (4 params empresa + 3 freelancer; el CASE elige por fila)
                q, q, q, q,
                q, q, q,
                # usuario: where
                user_id,
                q, like_q, q, like_q, q, like_q, q, like_q,
                q, like_q, q, like_q, q, like_q,
                # producto: rank + where
                q, q,
                user_id,
                q, q, q,
                like_q, like_q, like_q,
                lim,
            ])
            columns = [col[0] for col in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]

        for r in results:
            if 'foto_url' in r:
                r['foto_url'] = foto_usuario_api(r.get('foto_url'))
            if 'rounded_foto_url' in r:
                r['rounded_foto_url'] = foto_usuario_api(r.get('rounded_foto_url'))

        usuario_ids = [r['id'] for r in results if r.get('tipo') == 'usuario']
        if usuario_ids:
            usuarios_qs = Usuario.objects.filter(id__in=usuario_ids).prefetch_related('empresas_administradas')
            subs_map, efectivo_counts = _batch_visibility_data(usuario_ids)
            visibles = {u.id for u in usuarios_qs if _es_visible_en_mapa(u, subs_map, efectivo_counts)}
            results = [r for r in results if r.get('tipo') != 'usuario' or r['id'] in visibles]

        if profesion_id:
            pid = int(profesion_id)
            results = [r for r in results if pid in (r.get('profesion_ids') or [])]

        if max_price:
            mp = float(max_price)
            results = [r for r in results if _precio_para_filtro(r) is None or _precio_para_filtro(r) <= mp]

        if is_urgent == 'true':
            results = [r for r in results if r.get('es_urgente')]

        if sort_by == 'mejor_valorados':
            results.sort(key=lambda x: float(x.get('rating') or 0), reverse=True)
        elif sort_by == 'mas_cercanos':
            results.sort(key=lambda x: x.get('rank', 0))
        elif sort_by == 'mejor_precio':
            results.sort(key=lambda x: (_precio_para_filtro(x) is None, _precio_para_filtro(x) or 0))

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
        try:
            limit = int(request.query_params.get('limit', 25))
        except (TypeError, ValueError):
            limit = 25
        limit = max(1, min(limit, 100))

        sort_by = request.query_params.get('sort_by', 'mejor_valorados')
        usuarios = resolve_map_users_national(limit=limit, sort_by=sort_by)
        return Response(serialize_usuarios_mapa(usuarios))

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated], url_path='top-zona')
    def top_zona(self, request):
        """Top usuarios dentro de bounds, con límite"""
        north = Decimal(request.query_params['north'])
        south = Decimal(request.query_params['south'])
        east  = Decimal(request.query_params['east'])
        west  = Decimal(request.query_params['west'])
        try:
            limit = int(request.query_params.get('limit', 50))
        except (TypeError, ValueError):
            limit = 50
        limit = max(1, min(limit, 100))
        sort_by = request.query_params.get('sort_by', 'mejor_valorados')

        usuarios = resolve_map_users_from_bounds(
            north=north,
            south=south,
            east=east,
            west=west,
            limit=limit,
            sort_by=sort_by,
        )
        return Response(serialize_usuarios_mapa(usuarios))
    
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
            if usuario.is_deleted or not usuario.is_active:
                return Response(
                    {'error': 'Esta cuenta fue eliminada'},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
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


class AdminUsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all().select_related('rol').prefetch_related('empresas_administradas')
    serializer_class = AdminUsuarioSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get_queryset(self):
        queryset = Usuario.objects.all().select_related('rol').prefetch_related('empresas_administradas')

        is_active = self.request.query_params.get('is_active')
        is_staff = self.request.query_params.get('is_staff')
        is_owner_empresa = self.request.query_params.get('is_owner_empresa')
        is_deleted = self.request.query_params.get('is_deleted')
        rol_id = self.request.query_params.get('rol_id')
        search = self.request.query_params.get('search')

        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        if is_staff is not None:
            queryset = queryset.filter(is_staff=is_staff.lower() == 'true')
        if is_owner_empresa is not None:
            queryset = queryset.filter(is_owner_empresa=is_owner_empresa.lower() == 'true')
        if is_deleted is not None:
            queryset = queryset.filter(is_deleted=is_deleted.lower() == 'true')
        if rol_id:
            queryset = queryset.filter(rol_id=rol_id)
        if search:
            queryset = queryset.filter(
                Q(nombre__icontains=search) |
                Q(apellido__icontains=search) |
                Q(correo__icontains=search) |
                Q(id__iexact=search)
            )

        return queryset

    def get_serializer_class(self):
        if self.action in ['update', 'partial_update']:
            return AdminUsuarioUpdateSerializer
        return AdminUsuarioSerializer

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        usuario = serializer.save()
        return Response({
            'ok': True,
            'message': 'Operación exitosa',
            'data': AdminUsuarioSerializer(usuario).data,
        })

    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        usuario = self.get_object()
        usuario.is_deleted = True
        usuario.is_active = False
        from django.utils import timezone
        usuario.deleted_at = timezone.now()
        usuario.save(update_fields=['is_deleted', 'is_active', 'deleted_at'])
        return Response({'message': 'Usuario eliminado correctamente'}, status=status.HTTP_200_OK)