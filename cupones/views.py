from datetime import datetime

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from empresas.models import Empresa
from notificaciones.tasks import notificar_usuario
from usuario.models import Usuario

from .models import Cupon
from .serializers import CrearCuponSerializer, CuponSerializer, ValidarCuponSerializer


def _descripcion_descuento(cupon: Cupon) -> str:
    if cupon.tipo_descuento == Cupon.TipoDescuento.PORCENTAJE:
        return f'{cupon.valor:g}% de descuento'
    return f'${cupon.valor:g} de descuento'


def _fin_del_dia(fecha) -> 'timezone.datetime | None':
    if not fecha:
        return None
    return timezone.make_aware(datetime.combine(fecha, datetime.max.time()))


class CuponViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def _mi_empresa(self, request) -> Empresa | None:
        return Empresa.objects.filter(admin_id=request.user).first()

    def list(self, request):
        """GET /cupones/?cliente_id= — cupones que MI empresa le dio a un cliente."""
        empresa = self._mi_empresa(request)
        if not empresa:
            return Response([])

        qs = Cupon.objects.filter(empresa=empresa)
        cliente_id = request.query_params.get('cliente_id')
        if cliente_id:
            qs = qs.filter(cliente_id=cliente_id)

        return Response(CuponSerializer(qs.order_by('-created_at'), many=True).data)

    def create(self, request):
        """POST /cupones/ — el profesional le ofrece un cupón a un cliente puntual."""
        empresa = self._mi_empresa(request)
        if not empresa:
            return Response(
                {'error': 'No tenés una empresa asociada'},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not request.user.is_owner_empresa:
            return Response(
                {'error': 'Solo el propietario puede crear cupones'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CrearCuponSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        cliente = get_object_or_404(Usuario, id=data['cliente_id'])

        cupon = Cupon.objects.create(
            empresa=empresa,
            cliente=cliente,
            tipo_descuento=data['tipo_descuento'],
            valor=data['valor'],
            fecha_expiracion=_fin_del_dia(data.get('fecha_expiracion')),
        )

        notificar_usuario.delay(
            usuario_id=cliente.id,
            titulo='¡Tenés un cupón nuevo!',
            mensaje=f'{empresa.nombre} te regaló un cupón de {_descripcion_descuento(cupon)}.',
            data={
                'entity_id': cupon.id,
                'tipo': 'cupon_creado',
            },
        )

        return Response(CuponSerializer(cupon).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='mis-cupones')
    def mis_cupones(self, request):
        """GET /cupones/mis-cupones/?empresa_id= — cupones ACTIVOS (no usados, no
        vencidos) que YO (cliente logueado) tengo para gastar en esa empresa."""
        empresa_id = request.query_params.get('empresa_id')
        if not empresa_id:
            return Response({'error': 'empresa_id es requerido'}, status=status.HTTP_400_BAD_REQUEST)

        qs = Cupon.objects.filter(
            cliente=request.user,
            empresa_id=empresa_id,
            fecha_uso__isnull=True,
        ).filter(
            Q(fecha_expiracion__isnull=True) | Q(fecha_expiracion__gt=timezone.now()),
        ).order_by('-created_at')

        return Response(CuponSerializer(qs, many=True).data)

    @action(detail=False, methods=['post'], url_path='validar')
    def validar(self, request):
        """POST /cupones/validar/ — chequea si un código es válido para ese cliente+empresa."""
        serializer = ValidarCuponSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        cupon = Cupon.objects.filter(
            codigo__iexact=data['codigo'].strip(),
            empresa_id=data['empresa_id'],
            cliente_id=data['cliente_id'],
        ).first()

        if not cupon:
            return Response({'valido': False, 'motivo_invalidez': 'Cupón no encontrado'})
        if cupon.estado == 'usado':
            return Response({'valido': False, 'motivo_invalidez': 'Este cupón ya fue usado'})
        if cupon.estado == 'expirado':
            return Response({'valido': False, 'motivo_invalidez': 'Este cupón expiró'})

        monto_descuento = (
            float(cupon.valor) if cupon.tipo_descuento == Cupon.TipoDescuento.MONTO_FIJO else None
        )

        return Response({
            'valido': True,
            'cupon': CuponSerializer(cupon).data,
            'monto_descuento': monto_descuento,
        })


def resolver_cupon_para_canje(*, codigo: str, empresa_id: int, cliente_id: int) -> Cupon | None:
    """Usado por checkout de carritos / creación de trabajos al aplicar un
    cupon_codigo: devuelve el cupón solo si es válido (existe, no usado, no
    expirado, y pertenece a ese cliente+empresa); None en cualquier otro caso."""
    if not codigo:
        return None
    cupon = Cupon.objects.filter(
        codigo__iexact=codigo.strip(),
        empresa_id=empresa_id,
        cliente_id=cliente_id,
    ).first()
    if not cupon or cupon.estado != 'activo':
        return None
    return cupon


def calcular_monto_descuento(cupon: Cupon, total) -> 'float':
    """Monto a descontar del `total` (Decimal/float/str) según el tipo de cupón."""
    total = float(total)
    if cupon.tipo_descuento == Cupon.TipoDescuento.MONTO_FIJO:
        return min(float(cupon.valor), total)
    return round(total * (float(cupon.valor) / 100), 2)
