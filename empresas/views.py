import logging
import requests as req

from django.conf import settings
from django.shortcuts import redirect
from localizacion.utils import calcular_distancia_km
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from usuario.utils import obtener_localizacion_usuario
from .models import Empresa, CategoriaProducto, Producto
from .serializers import EmpresaSerializer, CategoriaProductoSerializer, ProductoSerializer
from .utils import validar_nombre_empresa_unico
from .estadisticas import estadisticas_empresa
from rest_framework.decorators import action
from django.db.models import Q

logger = logging.getLogger(__name__)

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

    def _autodetectar_pais(self, empresa):
        """Intenta detectar el país de la empresa desde su localizacion."""
        if empresa.localizacion and empresa.localizacion.country:
            codigo = _pais_desde_nombre(empresa.localizacion.country)
            if codigo and empresa.pais != codigo:
                empresa.pais = codigo
                empresa.save(update_fields=['pais', 'updated_at'])

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
        empresa.save(update_fields=[
            'pais', 'mp_access_token', 'mp_refresh_token', 'mp_user_id',
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


class CategoriaProductoViewSet(viewsets.ModelViewSet):
    queryset = CategoriaProducto.objects.all()
    serializer_class = CategoriaProductoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        empresa_id = self.request.query_params.get('empresa_id', None)
        
        if empresa_id:
            queryset = queryset.filter(empresa_id=empresa_id)
        else:
            empresas_usuario = Empresa.objects.filter(admin_id=self.request.user)
            queryset = queryset.filter(empresa__in=empresas_usuario)
        
        return queryset

    def perform_create(self, serializer):
        empresa_id = self.request.data.get('empresa')
        empresa = Empresa.objects.filter(id=empresa_id, admin_id=self.request.user).first()
        
        if not empresa:
            raise serializers.ValidationError({'error': 'No tienes permisos para crear categorías en esta empresa'})
        
        serializer.save()

    def perform_update(self, serializer):
        empresa = serializer.instance.empresa
        
        if empresa.admin_id != self.request.user:
            raise serializers.ValidationError({'error': 'No tienes permisos para modificar esta categoría'})
        
        serializer.save()

    def perform_destroy(self, instance):
        if instance.empresa.admin_id != self.request.user:
            raise serializers.ValidationError({'error': 'No tienes permisos para eliminar esta categoría'})
        
        instance.delete()


class ProductoViewSet(viewsets.ModelViewSet):
    queryset = Producto.objects.all()
    serializer_class = ProductoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        empresa_id = self.request.query_params.get('empresa_id', None)
        categoria_id = self.request.query_params.get('categoria_id', None)
        search = self.request.query_params.get('search', None)
        
        if empresa_id:
            queryset = queryset.filter(empresa_id=empresa_id)
        
        if categoria_id:
            queryset = queryset.filter(categoria_id=categoria_id)
        
        if not empresa_id and not categoria_id:
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
        
        return queryset.select_related('empresa', 'categoria')

    def perform_create(self, serializer):
        empresa_id = self.request.data.get('empresa')
        empresa = Empresa.objects.filter(id=empresa_id, admin_id=self.request.user).first()
        
        if not empresa:
            raise serializers.ValidationError({'error': 'No tienes permisos para crear productos en esta empresa'})
        
        serializer.save()

    def perform_update(self, serializer):
        empresa = serializer.instance.empresa
        
        if empresa.admin_id != self.request.user:
            raise serializers.ValidationError({'error': 'No tienes permisos para modificar este producto'})
        
        serializer.save()

    def perform_destroy(self, instance):
        if instance.empresa.admin_id != self.request.user:
            raise serializers.ValidationError({'error': 'No tienes permisos para eliminar este producto'})
        
        instance.delete()

