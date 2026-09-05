import logging
import requests as req

from django.conf import settings
from django.shortcuts import redirect
from localizacion.utils import calcular_distancia_km
from rest_framework import viewsets, status, serializers
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser, BasePermission
from usuario.utils import obtener_localizacion_usuario
from .models import Empresa, CategoriaProducto, Producto
from .serializers import EmpresaSerializer, CategoriaProductoSerializer, ProductoSerializer
from .utils import validar_nombre_empresa_unico, generar_subdomain_unico, empresa_tiene_landing_activa
from .gemini_service import analizar_imagen_productos
from .estadisticas import estadisticas_empresa
from rest_framework.decorators import action
from rest_framework.views import APIView
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from servicios.models import Servicio
from servicios.serializers import ServicioSerializer, ServicioCreateSerializer
from servicios.views import _filter_servicios_queryset

logger = logging.getLogger(__name__)


def _user_can_manage_empresa(user, empresa):
    """Owner de la empresa o staff del sistema."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if user.is_staff:
        return True
    return empresa.admin_id_id == user.id


def _get_empresa_for_user(user, empresa_id):
    if not empresa_id:
        return None
    try:
        empresa_id = int(empresa_id)
    except (TypeError, ValueError):
        return None
    empresa = Empresa.objects.filter(id=empresa_id).first()
    if not empresa:
        return None
    if not _user_can_manage_empresa(user, empresa):
        return None
    return empresa

# Mercado Pago OAuth authorization URLs por país
# Países con dominio propio: los confirmados por MP
# Países sin dominio propio: usan auth.mercadopago.com (genérico/redirect)
MP_OAUTH_URLS = {
    'AR': 'https://auth.mercadopago.com.ar/authorization',
    'BO': 'https://auth.mercadopago.com/authorization',
    'BR': 'https://auth.mercadopago.com.br/authorization',
    'CL': 'https://auth.mercadopago.cl/authorization',
    'CO': 'https://auth.mercadopago.com.co/authorization',
    'CR': 'https://auth.mercadopago.com/authorization',
    'CU': 'https://auth.mercadopago.com/authorization',
    'DO': 'https://auth.mercadopago.com/authorization',
    'EC': 'https://auth.mercadopago.com/authorization',
    'GT': 'https://auth.mercadopago.com/authorization',
    'HN': 'https://auth.mercadopago.com/authorization',
    'MX': 'https://auth.mercadopago.com.mx/authorization',
    'NI': 'https://auth.mercadopago.com/authorization',
    'PA': 'https://auth.mercadopago.com/authorization',
    'PE': 'https://auth.mercadopago.com.pe/authorization',
    'PR': 'https://auth.mercadopago.com/authorization',
    'PY': 'https://auth.mercadopago.com/authorization',
    'SV': 'https://auth.mercadopago.com/authorization',
    'UY': 'https://auth.mercadopago.com.uy/authorization',
    'VE': 'https://auth.mercadopago.com/authorization',
}

MP_TOKEN_URL = "https://api.mercadopago.com/oauth/token"


def _pais_desde_nombre(nombre_pais: str) -> str:
    """Convierte un nombre de país (e.g. 'Uruguay') a código ISO (e.g. 'UY')."""
    if not nombre_pais:
        return ''
    normalizado = nombre_pais.strip().lower()
    # Si ya es un código de 2 letras, devolverlo en mayúsculas
    if len(normalizado) == 2:
        return normalizado.upper()
    return Empresa.COUNTRY_NAME_TO_CODE.get(normalizado, '')


class IsStaffOrEmpresaOwner(BasePermission):
    """Staff: acceso completo. Owner (admin_id): solo su empresa en lectura/actualización."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        if view.action in ('retrieve', 'update', 'partial_update'):
            return obj.admin_id_id == request.user.id
        return False


class EmpresaViewSet(viewsets.ModelViewSet):
    queryset = Empresa.objects.all()
    serializer_class = EmpresaSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        admin_id = self.request.query_params.get('admin_id', None)
        if admin_id:
            queryset = queryset.filter(admin_id=admin_id)
        return queryset
    
    def create(self, request, *args, **kwargs):
        nombre = request.data.get('nombre')
        if nombre and not validar_nombre_empresa_unico(nombre):
            return Response(
                {'error': f"Ya existe una empresa con el nombre '{nombre}'"},
                status=status.HTTP_400_BAD_REQUEST
            )
        response = super().create(request, *args, **kwargs)
        # Auto-detectar país desde la localizacion si no se envió explícitamente
        if 'pais' not in request.data:
            try:
                empresa = Empresa.objects.get(id=response.data.get('id') or response.data.get('data', {}).get('id'))
                self._autodetectar_pais(empresa)
            except Empresa.DoesNotExist:
                pass
        return response

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        # Solo el admin de la empresa puede actualizarla
        if instance.admin_id_id != request.user.id and not request.user.is_staff:
            return Response(
                {'error': 'No tenés permisos para modificar esta empresa'},
                status=status.HTTP_403_FORBIDDEN
            )
        nombre = request.data.get('nombre')
        if nombre and nombre.lower() != instance.nombre.lower() and not validar_nombre_empresa_unico(nombre):
            return Response(
                {'error': f"Ya existe una empresa con el nombre '{nombre}'"},
                status=status.HTTP_400_BAD_REQUEST
            )
        response = super().update(request, *args, **kwargs)
        # Si se actualizó la localizacion y no se mandó pais explícito, re-detectar
        if 'localizacion' in request.data and 'pais' not in request.data:
            try:
                instance.refresh_from_db()
                self._autodetectar_pais(instance)
            except Exception:
                pass
        return response

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        # Solo el admin de la empresa o staff puede eliminarla
        if instance.admin_id != request.user and not request.user.is_staff:
            return Response(
                {'error': 'No tenés permisos para eliminar esta empresa'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().destroy(request, *args, **kwargs)

    def _autodetectar_pais(self, empresa):
        """Intenta detectar el país de la empresa desde su localizacion."""
        if empresa.localizacion and empresa.localizacion.country:
            codigo = _pais_desde_nombre(empresa.localizacion.country)
            if codigo and empresa.pais != codigo:
                empresa.pais = codigo
                empresa.sync_currency_from_pais(save=False)
                empresa.save(update_fields=['pais', 'currency', 'updated_at'])

    @action(detail=True, methods=['patch'], url_path='metodos-pago')
    def actualizar_metodos_pago(self, request, pk=None):
        empresa = self.get_object()

        if empresa.admin_id != request.user:
            return Response(
                {'error': 'No tenés permisos para modificar esta empresa'},
                status=status.HTTP_403_FORBIDDEN
            )

        acepta_efectivo = request.data.get('acepta_efectivo')
        acepta_tarjeta = request.data.get('acepta_tarjeta')

        update_fields = []

        if acepta_tarjeta is not None:
            empresa.acepta_tarjeta = acepta_tarjeta
            update_fields.append('acepta_tarjeta')

        if acepta_efectivo is not None:
            if acepta_efectivo:
                from suscripciones.models import Subscripcion
                from django.utils import timezone
                tiene_sub = Subscripcion.objects.filter(
                    user_id=empresa.admin_id,
                    cancelada=False,
                    expiracion__gt=timezone.now(),
                ).exists()
                if not tiene_sub:
                    return Response(
                        {'error': 'Necesitás una suscripción activa para habilitar pagos en efectivo'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            empresa.acepta_efectivo = acepta_efectivo
            update_fields.append('acepta_efectivo')

        if update_fields:
            empresa.save(update_fields=update_fields)

        return Response(EmpresaSerializer(empresa).data)

    @action(detail=True, methods=['patch'], url_path='landing')
    def actualizar_landing(self, request, pk=None):
        """Actualiza la configuración pública de la landing page."""
        empresa = self.get_object()

        if empresa.admin_id_id != request.user.id and not request.user.is_staff:
            return Response(
                {'error': 'No tenés permisos para modificar esta empresa'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not empresa_tiene_landing_activa(empresa):
            return Response(
                {'error': 'Esta empresa no tiene landing page activa'},
                status=status.HTTP_403_FORBIDDEN,
            )

        allowed = {
            'landing_titulo', 'landing_slogan', 'landing_descripcion', 'landing_foto_url',
        }
        update_fields = []
        for field in allowed:
            if field in request.data:
                setattr(empresa, field, request.data.get(field) or '')
                update_fields.append(field)

        if update_fields:
            empresa.save(update_fields=[*update_fields, 'updated_at'])

        return Response(EmpresaSerializer(empresa).data)

    @action(detail=True, methods=['patch'], url_path='privacidad-mapa')
    def actualizar_privacidad_mapa(self, request, pk=None):
        """Actualiza si la empresa comparte ubicación en el mapa público."""
        empresa = self.get_object()

        if empresa.admin_id_id != request.user.id and not request.user.is_staff:
            return Response(
                {'error': 'No tenés permisos para modificar esta empresa'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if 'compartir_ubicacion_mapa' not in request.data:
            return Response(
                {'error': 'compartir_ubicacion_mapa es requerido'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw = request.data.get('compartir_ubicacion_mapa')
        if isinstance(raw, str):
            compartir = raw.lower() in ('true', '1', 'yes', 'si', 'sí')
        else:
            compartir = bool(raw)

        empresa.compartir_ubicacion_mapa = compartir
        empresa.save(update_fields=['compartir_ubicacion_mapa', 'updated_at'])

        return Response(EmpresaSerializer(empresa).data)

    @action(detail=True, methods=['patch'], url_path='pais')
    def actualizar_pais(self, request, pk=None):
        """Actualiza el país de la empresa (afecta qué OAuth URL de MP se usa)."""
        empresa = self.get_object()
        if empresa.admin_id != request.user:
            return Response({'error': 'No tenés permisos'}, status=status.HTTP_403_FORBIDDEN)

        pais = request.data.get('pais', '').upper()
        codigos_validos = [c for c, _ in Empresa.PAIS_CHOICES]
        if pais not in codigos_validos:
            return Response(
                {'error': f"País inválido. Opciones: {', '.join(codigos_validos)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Si cambia el país y ya tenía MP vinculado, desvincular (tokens del país anterior ya no sirven)
        if empresa.pais != pais and empresa.is_mercadopago_vinculado:
            empresa.mp_access_token = ''
            empresa.mp_refresh_token = ''
            empresa.mp_user_id = ''
            empresa.mp_email = ''
            empresa.is_mercadopago_vinculado = False
            empresa.acepta_tarjeta = False

        empresa.pais = pais
        empresa.sync_currency_from_pais(save=False)
        empresa.save(update_fields=[
            'pais', 'currency', 'mp_access_token', 'mp_refresh_token', 'mp_user_id',
            'mp_email', 'is_mercadopago_vinculado', 'acepta_tarjeta', 'updated_at'
        ])
        return Response(EmpresaSerializer(empresa).data)

    @action(detail=True, methods=['get'], url_path='mp-connect-url')
    def mp_connect_url(self, request, pk=None):
        """
        Devuelve la URL de autorización OAuth de Mercado Pago.
        Acepta ?platform=app para apps Capacitor (redirige via deep link).
        Acepta ?platform=web para navegador (redirige via FRONTEND_URL).
        """
        empresa = self.get_object()

        if empresa.admin_id != request.user:
            return Response(
                {'error': 'No tenés permisos para vincular esta empresa'},
                status=status.HTTP_403_FORBIDDEN
            )

        if not settings.MP_APP_ID:
            return Response(
                {'error': 'La integración con MercadoPago no está configurada'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        platform = request.query_params.get('platform', 'web')
        callback_url = f"{settings.MP_WEBHOOK_BASE_URL}/api/empresas/mp-callback/"
        # Encode empresa_id + platform in state so callback knows where to redirect
        state = f"{empresa.id}_{platform}"

        pais = empresa.pais or 'UY'
        oauth_url = MP_OAUTH_URLS.get(pais, MP_OAUTH_URLS['UY'])

        auth_url = (
            f"{oauth_url}"
            f"?client_id={settings.MP_APP_ID}"
            f"&response_type=code"
            f"&platform_id=mp"
            f"&redirect_uri={callback_url}"
            f"&state={state}"
        )

        return Response({'url': auth_url, 'pais': pais})

    @action(detail=False, methods=['get'], url_path='mp-callback', permission_classes=[AllowAny])
    def mp_callback(self, request):
        """
        Callback OAuth de Mercado Pago.
        MP redirige aquí con ?code=...&state={empresa_id}
        Intercambia el code por access_token y guarda en la Empresa.
        """
        code = request.query_params.get('code')
        state = request.query_params.get('state')  # "{empresa_id}_{platform}"
        error = request.query_params.get('error')

        # Defaults before parsing state
        web_base = f"{settings.FRONTEND_URL}/perfil/empresaMetodosPago"
        app_scheme = getattr(settings, 'MP_APP_SCHEME', 'com.alavueltaapp')
        platform = 'web'
        empresa_id_str = state or ''

        # Parse state: "{empresa_id}_{platform}"
        if state and '_' in state:
            parts = state.rsplit('_', 1)
            empresa_id_str = parts[0]
            platform = parts[1] if len(parts) > 1 else 'web'

        def redirect_result(mp_connect: str, reason: str = ''):
            if platform == 'app':
                params = f"mp_connect={mp_connect}"
                if reason:
                    params += f"&reason={reason}"
                return redirect(f"{app_scheme}://oauth?{params}")
            url = f"{web_base}?mp_connect={mp_connect}"
            if reason:
                url += f"&reason={reason}"
            return redirect(url)

        if error or not code or not state:
            logger.warning("MP OAuth callback con error: error=%s code=%s state=%s", error, code, state)
            return redirect_result('error', error or 'missing_params')

        try:
            empresa = Empresa.objects.get(id=int(empresa_id_str))
        except (Empresa.DoesNotExist, ValueError):
            logger.error("MP OAuth callback: empresa_id inválido state=%s", state)
            return redirect_result('error', 'invalid_state')

        callback_url = f"{settings.MP_WEBHOOK_BASE_URL}/api/empresas/mp-callback/"
        payload = {
            "client_id": settings.MP_APP_ID,
            "client_secret": settings.MP_APP_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": callback_url,
        }

        try:
            resp = req.post(MP_TOKEN_URL, json=payload, timeout=15)
            data = resp.json()
        except Exception as e:
            logger.error("Error intercambiando code por token MP: %s", e)
            return redirect(f"{frontend_base}?mp_connect=error&reason=token_exchange_failed")

        if resp.status_code not in (200, 201) or 'access_token' not in data:
            logger.error("MP token exchange failed: %s %s", resp.status_code, data)
            return redirect(f"{frontend_base}?mp_connect=error&reason=token_exchange_failed")

        empresa.mp_access_token = data.get('access_token', '')
        empresa.mp_refresh_token = data.get('refresh_token', '')
        empresa.mp_user_id = str(data.get('user_id', ''))
        empresa.is_mercadopago_vinculado = True
        empresa.save(update_fields=[
            'mp_access_token', 'mp_refresh_token', 'mp_user_id',
            'is_mercadopago_vinculado', 'updated_at'
        ])

        logger.info("MP vinculado exitosamente para empresa_id=%s mp_user_id=%s platform=%s", empresa.id, empresa.mp_user_id, platform)
        return redirect_result('success')

    @action(detail=True, methods=['post'], url_path='mp-disconnect')
    def mp_disconnect(self, request, pk=None):
        """Desvincula la cuenta de MercadoPago de la empresa."""
        empresa = self.get_object()

        if empresa.admin_id != request.user:
            return Response(
                {'error': 'No tenés permisos para desvincular esta empresa'},
                status=status.HTTP_403_FORBIDDEN
            )

        empresa.mp_access_token = ''
        empresa.mp_refresh_token = ''
        empresa.mp_user_id = ''
        empresa.mp_email = ''
        empresa.is_mercadopago_vinculado = False
        empresa.acepta_tarjeta = False
        empresa.save(update_fields=[
            'mp_access_token', 'mp_refresh_token', 'mp_user_id', 'mp_email',
            'is_mercadopago_vinculado', 'acepta_tarjeta', 'updated_at'
        ])

        return Response({'message': 'MercadoPago desvinculado correctamente'})

    @action(detail=True, methods=['get'], url_path='distance-from-me')
    def distance_from_me(self, request, pk=None):
        empresa = self.get_object()
        usuario = request.user

        loc_usuario = obtener_localizacion_usuario(usuario)
        if not loc_usuario:
            return Response(
                {'error': 'El usuario no tiene localización configurada'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not empresa.localizacion:
            return Response(
                {'error': 'La empresa no tiene localización configurada'},
                status=status.HTTP_400_BAD_REQUEST
            )

        loc_empresa = empresa.localizacion

        distancia = calcular_distancia_km(
            loc_usuario.latitud,
            loc_usuario.longitud,
            loc_empresa.latitud,
            loc_empresa.longitud
        )

        return Response({
            'empresa_id': empresa.id,
            'empresa_nombre': empresa.nombre,
            'distance_km': distancia,
            'user_location': {
                'city': loc_usuario.city,
                'country': loc_usuario.country
            },
            'empresa_location': {
                'city': loc_empresa.city,
                'country': loc_empresa.country
            }
        })

    @action(detail=False, methods=['get'], url_path='estadisticas')
    def estadisticas(self, request):
        """Panel de estadísticas del negocio (solo owner de empresa)."""
        empresa = Empresa.objects.filter(admin_id=request.user).first()
        if not empresa:
            return Response(
                {'error': 'No tenés una empresa asociada'},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not request.user.is_owner_empresa:
            return Response(
                {'error': 'Solo el propietario puede ver estadísticas'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(estadisticas_empresa(empresa, request))

    @action(detail=True, methods=['get'], url_path='estadisticas')
    def estadisticas_por_empresa(self, request, pk=None):
        """Panel de estadísticas de una empresa específica (solo admin/staff)."""
        if not request.user.is_staff:
            return Response(
                {'error': 'Solo el staff puede ver estadísticas de otras empresas'},
                status=status.HTTP_403_FORBIDDEN,
            )
        empresa = self.get_object()
        return Response(estadisticas_empresa(empresa, request))


class AdminEmpresaViewSet(viewsets.ModelViewSet):
    """
    CRUD de empresas para administradores (is_staff).
    El owner de la empresa (admin_id) puede consultar y actualizar vende_productos /
    vende_servicios de su propia empresa vía PATCH/PUT.
    """
    queryset = Empresa.objects.all().select_related('admin_id', 'localizacion')
    serializer_class = EmpresaSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    OWNER_WRITABLE_FIELDS = frozenset({'vende_productos', 'vende_servicios', 'vende_menu_diario'})

    def get_permissions(self):
        if self.action in ('retrieve', 'update', 'partial_update'):
            return [IsAuthenticated(), IsStaffOrEmpresaOwner()]
        return [IsAuthenticated(), IsAdminUser()]

    def _guard_owner_patch_fields(self, request):
        if request.user.is_staff:
            return None
        extra = set(request.data.keys()) - self.OWNER_WRITABLE_FIELDS
        if extra:
            allowed = ', '.join(sorted(self.OWNER_WRITABLE_FIELDS))
            return Response(
                {'error': f'Solo podés modificar: {allowed}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return None

    def update(self, request, *args, **kwargs):
        denied = self._guard_owner_patch_fields(request)
        if denied:
            return denied
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        denied = self._guard_owner_patch_fields(request)
        if denied:
            return denied
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Soft delete de la empresa y desactiva al usuario owner asociado."""
        empresa = self.get_object()
        owner = empresa.admin_id
        user = request.user

        if owner and (owner.pk == user.pk or owner.is_superuser):
            return Response(
                {'error': 'No se puede eliminar la empresa de un administrador del sistema'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from notificaciones.models import DeviceToken

        with transaction.atomic():
            empresa.delete(user=user)
            if owner and not owner.is_staff:
                owner.is_deleted = True
                owner.is_active = False
                owner.deleted_at = timezone.now()
                owner.save(update_fields=['is_deleted', 'is_active', 'deleted_at'])
                DeviceToken.objects.filter(usuario=owner).delete()

        return Response(
            {
                'message': 'Empresa eliminada. El usuario owner fue desactivado.',
                'empresa_id': empresa.id,
                'owner_id': owner.pk if owner else None,
            },
            status=status.HTTP_200_OK,
        )

    def get_queryset(self):
        from fixeo_project.admin_filters import apply_created_at_filters, apply_ordering

        queryset = Empresa.objects.all().select_related('admin_id', 'localizacion')

        # Filtros opcionales
        admin_id = self.request.query_params.get('admin_id')
        pais = self.request.query_params.get('pais')
        nombre = self.request.query_params.get('nombre')
        search = self.request.query_params.get('search')
        vende_productos = self.request.query_params.get('vende_productos')
        vende_servicios = self.request.query_params.get('vende_servicios')
        is_mercadopago_vinculado = self.request.query_params.get('is_mercadopago_vinculado')

        if admin_id:
            queryset = queryset.filter(admin_id=admin_id)
        if pais:
            queryset = queryset.filter(pais=pais.upper())
        if nombre:
            queryset = queryset.filter(nombre__icontains=nombre)
        if search:
            queryset = queryset.filter(
                Q(nombre__icontains=search) |
                Q(descripcion__icontains=search) |
                Q(ubicacion__icontains=search)
            )
        if vende_productos is not None:
            queryset = queryset.filter(vende_productos=vende_productos.lower() == 'true')
        if vende_servicios is not None:
            queryset = queryset.filter(vende_servicios=vende_servicios.lower() == 'true')
        if is_mercadopago_vinculado is not None:
            queryset = queryset.filter(is_mercadopago_vinculado=is_mercadopago_vinculado.lower() == 'true')

        queryset = apply_created_at_filters(queryset, self.request.query_params)
        queryset = apply_ordering(
            queryset,
            self.request.query_params,
            allowed={'created_at', '-created_at', 'nombre', '-nombre', 'id', '-id'},
            default='-created_at',
        )
        return queryset


    def _require_staff(self, request):
        if not request.user.is_staff:
            return Response(
                {'error': 'Solo el staff puede gestionar el catálogo de otras empresas'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return None

    def _get_servicio_for_empresa(self, empresa, servicio_id):
        if not empresa.admin_id_id:
            return None
        return (
            Servicio.objects
            .filter(id=servicio_id, usuario_id=empresa.admin_id_id)
            .select_related('profesion')
            .first()
        )

    @action(detail=True, methods=['get'], url_path='servicios')
    def list_servicios_admin(self, request, pk=None):
        denied = self._require_staff(request)
        if denied:
            return denied
        empresa = self.get_object()
        if not empresa.admin_id_id:
            return Response([])
        qs = (
            Servicio.objects
            .filter(usuario_id=empresa.admin_id_id)
            .select_related('profesion')
            .order_by('profesion__nombre', 'nombre')
        )
        profesion_id = request.query_params.get('profesion_id')
        if profesion_id:
            qs = qs.filter(profesion_id=profesion_id)
        qs = _filter_servicios_queryset(qs, request)
        return Response(ServicioSerializer(qs, many=True).data)

    @action(detail=True, methods=['post'], url_path='servicios')
    def create_servicio_admin(self, request, pk=None):
        denied = self._require_staff(request)
        if denied:
            return denied
        empresa = self.get_object()
        owner = empresa.admin_id
        if not owner:
            return Response(
                {'error': 'La empresa no tiene un usuario owner asociado'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ServicioCreateSerializer(
            data=request.data,
            context={'request': request, 'empresa': empresa, 'servicio_owner': owner},
        )
        serializer.is_valid(raise_exception=True)

        profesion_id = serializer.validated_data['profesion'].id
        nombre = serializer.validated_data['nombre']
        if not owner.usuario_profesiones.filter(profesion_id=profesion_id).exists():
            return Response(
                {'error': 'El owner no tiene asignada esa profesión'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if Servicio.objects.filter(usuario=owner, profesion_id=profesion_id, nombre=nombre).exists():
            return Response(
                {'error': f'Ya existe un servicio con el nombre "{nombre}" para esta profesión'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        servicio = serializer.save(usuario=owner)
        return Response(ServicioSerializer(servicio).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['patch', 'put', 'delete'], url_path='servicios/(?P<servicio_id>[^/.]+)')
    def manage_servicio_admin(self, request, pk=None, servicio_id=None):
        denied = self._require_staff(request)
        if denied:
            return denied
        empresa = self.get_object()
        servicio = self._get_servicio_for_empresa(empresa, servicio_id)
        if not servicio:
            return Response({'error': 'Servicio no encontrado'}, status=status.HTTP_404_NOT_FOUND)

        if request.method == 'DELETE':
            profesion_nombre = servicio.profesion.nombre
            servicio.delete()
            return Response(
                {'message': f'Servicio de {profesion_nombre} eliminado exitosamente'},
                status=status.HTTP_200_OK,
            )

        partial = request.method == 'PATCH'
        owner = empresa.admin_id
        serializer = ServicioCreateSerializer(
            servicio,
            data=request.data,
            partial=partial,
            context={'request': request, 'empresa': empresa, 'servicio_owner': owner},
        )
        serializer.is_valid(raise_exception=True)

        profesion_id = serializer.validated_data.get('profesion', servicio.profesion).id
        nombre = serializer.validated_data.get('nombre', servicio.nombre)
        if 'profesion' in serializer.validated_data and profesion_id != servicio.profesion_id:
            if not owner.usuario_profesiones.filter(profesion_id=profesion_id).exists():
                return Response(
                    {'error': 'El owner no tiene asignada esa profesión'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        if Servicio.objects.filter(
            usuario=owner,
            profesion_id=profesion_id,
            nombre=nombre,
        ).exclude(id=servicio.id).exists():
            return Response(
                {'error': f'Ya existe un servicio con el nombre "{nombre}" para esta profesión'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        servicio = serializer.save()
        return Response(ServicioSerializer(servicio).data)


class CategoriaProductoViewSet(viewsets.ModelViewSet):
    queryset = CategoriaProducto.objects.all()
    serializer_class = CategoriaProductoSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action == 'retrieve':
            return [AllowAny()]
        if self.action == 'list' and self.request.query_params.get('empresa_id'):
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = super().get_queryset()
        empresa_id = self.request.query_params.get('empresa_id', None)
        
        if empresa_id:
            queryset = queryset.filter(empresa_id=empresa_id)
        else:
            if not self.request.user or not self.request.user.is_authenticated:
                return queryset.none()
            if not self.request.user.is_staff:
                empresas_usuario = Empresa.objects.filter(admin_id=self.request.user)
                queryset = queryset.filter(empresa__in=empresas_usuario)
        
        return queryset

    def perform_create(self, serializer):
        empresa = _get_empresa_for_user(self.request.user, self.request.data.get('empresa'))
        if not empresa:
            raise serializers.ValidationError({'error': 'No tienes permisos para crear categorías en esta empresa'})
        serializer.save()

    def perform_update(self, serializer):
        if not _user_can_manage_empresa(self.request.user, serializer.instance.empresa):
            raise serializers.ValidationError({'error': 'No tienes permisos para modificar esta categoría'})
        serializer.save()

    def perform_destroy(self, instance):
        if not _user_can_manage_empresa(self.request.user, instance.empresa):
            raise serializers.ValidationError({'error': 'No tienes permisos para eliminar esta categoría'})
        instance.delete()


class ProductoViewSet(viewsets.ModelViewSet):
    queryset = Producto.objects.all()
    serializer_class = ProductoSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        dia = getattr(self, '_dia_semana_ctx', None)
        if dia is not None:
            ctx['dia_semana'] = dia
        return ctx

    def get_permissions(self):
        # Guest: ver catálogo público de una empresa (mapa / perfil)
        if self.action == 'retrieve':
            return [AllowAny()]
        if self.action == 'list' and self.request.query_params.get('empresa_id'):
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = super().get_queryset()
        empresa_id = self.request.query_params.get('empresa_id', None)
        categoria_id = self.request.query_params.get('categoria_id', None)
        search = self.request.query_params.get('search', None)
        es_menu_diario = self.request.query_params.get('es_menu_diario', None)
        dia_semana = self.request.query_params.get('dia_semana', None)

        if empresa_id:
            queryset = queryset.filter(empresa_id=empresa_id)

        if categoria_id:
            queryset = queryset.filter(categoria_id=categoria_id)

        if es_menu_diario is not None:
            queryset = queryset.filter(
                es_menu_diario=str(es_menu_diario).lower() in ('1', 'true', 'yes')
            )
        elif self.action == 'list':
            # Catálogo retail por defecto en list (compat FE existente)
            queryset = queryset.filter(es_menu_diario=False)

        if dia_semana is not None:
            try:
                dia = int(dia_semana)
            except (TypeError, ValueError):
                dia = None
            if dia and 1 <= dia <= 7:
                incluir_inactivos = str(
                    self.request.query_params.get('incluir_inactivos', '')
                ).lower() in ('1', 'true', 'yes')
                dia_filter = {
                    'dias_menu__dia_semana': dia,
                    'dias_menu__is_deleted': False,
                }
                if not incluir_inactivos:
                    dia_filter['dias_menu__activo'] = True
                queryset = queryset.filter(**dia_filter).distinct()
                # Pasar día al serializer para activo_en_dia
                self._dia_semana_ctx = dia
                self._incluir_inactivos = incluir_inactivos

        if not empresa_id and not categoria_id:
            if not self.request.user or not self.request.user.is_authenticated:
                return queryset.none()
            if not self.request.user.is_staff:
                empresas_usuario = Empresa.objects.filter(admin_id=self.request.user)
                queryset = queryset.filter(empresa__in=empresas_usuario)

        if search:
            palabras = search.strip().split()
            q_filter = Q()

            for palabra in palabras:
                if palabra:
                    q_filter &= (
                        Q(nombre__icontains=palabra) |
                        Q(descripcion__icontains=palabra)
                    )

            queryset = queryset.filter(q_filter)

        return queryset.select_related('empresa', 'categoria').prefetch_related('dias_menu', 'variantes')

    def perform_create(self, serializer):
        empresa = _get_empresa_for_user(self.request.user, self.request.data.get('empresa'))
        if not empresa:
            raise serializers.ValidationError({'error': 'No tienes permisos para crear productos en esta empresa'})
        serializer.save()

    def perform_update(self, serializer):
        if not _user_can_manage_empresa(self.request.user, serializer.instance.empresa):
            raise serializers.ValidationError({'error': 'No tienes permisos para modificar este producto'})
        serializer.save()

    def perform_destroy(self, instance):
        if not _user_can_manage_empresa(self.request.user, instance.empresa):
            raise serializers.ValidationError({'error': 'No tienes permisos para eliminar este producto'})
        instance.delete()

    @action(detail=True, methods=['post'], url_path='vincular-dia')
    def vincular_dia(self, request, pk=None):
        """Agrega un día al plato de menú (reusar plato de otro día)."""
        from .models import ProductoDia

        producto = self.get_object()
        if not _user_can_manage_empresa(request.user, producto.empresa):
            return Response({'error': 'Sin permisos'}, status=status.HTTP_403_FORBIDDEN)
        if not producto.es_menu_diario:
            return Response(
                {'error': 'Solo aplica a platos de menú diario'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            dia = int(request.data.get('dia_semana'))
        except (TypeError, ValueError):
            return Response({'error': 'dia_semana inválido'}, status=status.HTTP_400_BAD_REQUEST)
        if dia < 1 or dia > 7:
            return Response({'error': 'dia_semana debe ser 1-7'}, status=status.HTTP_400_BAD_REQUEST)

        existing = producto.dias_menu.filter(dia_semana=dia).first()
        if existing:
            if existing.is_deleted:
                existing.is_deleted = False
                existing.deleted_at = None
                existing.activo = True
                existing.save(update_fields=['is_deleted', 'deleted_at', 'activo', 'updated_at'])
            elif not existing.activo:
                existing.activo = True
                existing.save(update_fields=['activo', 'updated_at'])
        else:
            ProductoDia.objects.create(producto=producto, dia_semana=dia, activo=True)

        return Response(ProductoSerializer(producto).data)

    @action(detail=True, methods=['post'], url_path='toggle-dia')
    def toggle_dia(self, request, pk=None):
        """Activa/desactiva el plato para un día (sin desvincular)."""
        from .models import ProductoDia

        producto = self.get_object()
        if not _user_can_manage_empresa(request.user, producto.empresa):
            return Response({'error': 'Sin permisos'}, status=status.HTTP_403_FORBIDDEN)
        if not producto.es_menu_diario:
            return Response(
                {'error': 'Solo aplica a platos de menú diario'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            dia = int(request.data.get('dia_semana'))
        except (TypeError, ValueError):
            return Response({'error': 'dia_semana inválido'}, status=status.HTTP_400_BAD_REQUEST)
        if dia < 1 or dia > 7:
            return Response({'error': 'dia_semana debe ser 1-7'}, status=status.HTTP_400_BAD_REQUEST)

        if 'activo' not in request.data:
            return Response({'error': 'activo es requerido'}, status=status.HTTP_400_BAD_REQUEST)
        activo = str(request.data.get('activo')).lower() in ('1', 'true', 'yes')

        existing = producto.dias_menu.filter(dia_semana=dia).first()
        if not existing or existing.is_deleted:
            if not activo:
                return Response(
                    {'error': 'El plato no está vinculado a ese día'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if existing and existing.is_deleted:
                existing.is_deleted = False
                existing.deleted_at = None
                existing.activo = True
                existing.save(update_fields=['is_deleted', 'deleted_at', 'activo', 'updated_at'])
            else:
                ProductoDia.objects.create(producto=producto, dia_semana=dia, activo=True)
        else:
            existing.activo = activo
            existing.save(update_fields=['activo', 'updated_at'])

        return Response(
            ProductoSerializer(producto, context={'request': request, 'dia_semana': dia}).data
        )

    @action(detail=False, methods=['post'], url_path='analizar-imagen')
    def analizar_imagen(self, request):
        """Detecta productos en una imagen con Gemini (visión). No crea nada:
        devuelve los productos detectados para que el usuario los revise/edite
        y confirme el alta desde el frontend.
        """
        empresa = _get_empresa_for_user(request.user, request.data.get('empresa'))
        if not empresa:
            return Response(
                {'ok': False, 'error': 'No tienes permisos sobre esta empresa'},
                status=status.HTTP_403_FORBIDDEN,
            )

        archivo = request.FILES.get('file')
        if not archivo:
            return Response(
                {'ok': False, 'error': 'No se envió ninguna imagen'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        mime_type = archivo.content_type or 'image/jpeg'
        if not mime_type.startswith('image/'):
            return Response(
                {'ok': False, 'error': 'El archivo debe ser una imagen'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if archivo.size > 10 * 1024 * 1024:
            return Response(
                {'ok': False, 'error': 'La imagen supera el tamaño máximo (10MB)'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        categorias = list(
            CategoriaProducto.objects.filter(empresa=empresa).values_list('nombre', flat=True)
        )

        try:
            productos = analizar_imagen_productos(
                image_bytes=archivo.read(),
                mime_type=mime_type,
                categorias_existentes=categorias,
                divisa_default=empresa.currency or empresa.moneda_local,
            )
        except RuntimeError as exc:
            logger.error('Gemini no configurado: %s', exc)
            return Response(
                {'ok': False, 'error': 'El servicio de IA no está disponible'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception:
            logger.exception('Error analizando imagen de productos con Gemini')
            return Response(
                {'ok': False, 'error': 'No se pudo analizar la imagen. Probá con otra foto.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response({'ok': True, 'productos': productos})


class EmpresaPublicLandingView(APIView):
    """Datos públicos de la landing page de una empresa (por subdominio)."""
    permission_classes = [AllowAny]

    def get(self, request, subdomain):
        empresa = (
            Empresa.objects
            .filter(subdomain=subdomain, is_deleted=False)
            .select_related('admin_id', 'localizacion')
            .first()
        )
        if not empresa:
            return Response({'error': 'Empresa no encontrada'}, status=status.HTTP_404_NOT_FOUND)

        if not empresa_tiene_landing_activa(empresa):
            return Response(
                {'error': 'Esta empresa no tiene landing page activa'},
                status=status.HTTP_404_NOT_FOUND,
            )

        admin = empresa.admin_id
        horarios = list(
            empresa.horarios.filter(enabled=True).values(
                'dia_semana', 'hora_inicio', 'hora_fin',
            )
        )
        servicios = ServicioSerializer(
            Servicio.objects.filter(usuario=admin).select_related('profesion'),
            many=True,
        ).data
        productos = ProductoSerializer(
            Producto.objects.filter(empresa=empresa, agotado=False).select_related('categoria'),
            many=True,
        ).data

        from usuario_profesion.models import UsuarioProfesion
        from profesion.serializers import ProfesionSerializer

        profesiones = ProfesionSerializer(
            [up.profesion for up in UsuarioProfesion.objects.filter(usuario=admin).select_related('profesion')],
            many=True,
        ).data

        zonas_no_trabajo = [
            {
                'id': z.id,
                'nombre': z.nombre or f'Zona {i + 1}',
                'latitud': float(z.latitud),
                'longitud': float(z.longitud),
                'radio_km': float(z.radio_km),
            }
            for i, z in enumerate(
                admin.zonas_no_trabajo.filter(activa=True).order_by('nombre', 'id')
            )
        ]

        return Response({
            'empresa': {
                'id': empresa.id,
                'nombre': empresa.nombre,
                'descripcion': empresa.descripcion,
                'subdomain': empresa.subdomain,
                'landing_titulo': empresa.landing_titulo,
                'landing_slogan': empresa.landing_slogan,
                'landing_descripcion': empresa.landing_descripcion,
                'landing_foto_url': empresa.landing_foto_url,
                'ubicacion': empresa.ubicacion,
                'latitud': float(empresa.latitud),
                'longitud': float(empresa.longitud),
                'compartir_ubicacion_mapa': empresa.compartir_ubicacion_mapa,
                'vende_productos': empresa.vende_productos,
                'vende_servicios': empresa.vende_servicios,
                'vende_menu_diario': empresa.vende_menu_diario,
                'acepta_efectivo': empresa.acepta_efectivo,
                'acepta_tarjeta': empresa.acepta_tarjeta,
                'is_mercadopago_vinculado': empresa.is_mercadopago_vinculado,
                'pais': empresa.pais,
                'currency': empresa.currency,
                'foto_url': admin.foto_url,
                'rounded_foto_url': admin.rounded_foto_url,
                'rating': float(admin.rating or 0),
                'cant_calif': admin.cant_calif,
                'trabajo_domicilio': admin.trabajo_domicilio,
                'trabajo_local': admin.trabajo_local,
                'rango_mapa_km': float(admin.rango_mapa_km or 10),
                'tiene_landing_page': bool(empresa.tiene_landing_page),
            },
            'admin_id': admin.id,
            'horarios': horarios,
            'servicios': servicios,
            'productos': productos,
            'profesiones': profesiones,
            'zonas_no_trabajo': zonas_no_trabajo,
        })
