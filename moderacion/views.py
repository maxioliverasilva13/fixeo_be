from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from usuario.models import Usuario

from .models import ContentReport, UsuarioBlock
from .serializers import (
    ContentReportCreateSerializer,
    ContentReportSerializer,
    UsuarioBlockSerializer,
)
from .services import notify_moderators


class ModeracionViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'], url_path='reportes')
    def crear_reporte(self, request):
        serializer = ContentReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        reported_user = None
        reported_user_id = data.get('reported_user_id')
        if reported_user_id:
            if reported_user_id == request.user.id:
                return Response(
                    {'error': 'No podés reportarte a vos mismo'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            reported_user = get_object_or_404(Usuario, id=reported_user_id)

        report = ContentReport.objects.create(
            reporter=request.user,
            reported_user=reported_user,
            content_type=data['content_type'],
            content_id=data.get('content_id'),
            reason=data.get('reason') or ContentReport.Reason.OTHER,
            details=(data.get('details') or '').strip(),
        )
        notify_moderators(report)
        return Response(
            ContentReportSerializer(report).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['get', 'post'], url_path='bloqueos')
    def bloqueos(self, request):
        if request.method == 'GET':
            qs = (
                UsuarioBlock.objects
                .filter(blocker=request.user)
                .select_related('blocked')
                .order_by('-created_at')
            )
            return Response(UsuarioBlockSerializer(qs, many=True).data)

        blocked_id = request.data.get('blocked_user_id') or request.data.get('user_id')
        if not blocked_id:
            return Response(
                {'error': 'blocked_user_id es requerido'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            blocked_id = int(blocked_id)
        except (TypeError, ValueError):
            return Response({'error': 'blocked_user_id inválido'}, status=400)

        if blocked_id == request.user.id:
            return Response(
                {'error': 'No podés bloquearte a vos mismo'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        blocked = get_object_or_404(Usuario, id=blocked_id)
        reason = (request.data.get('reason') or '').strip()[:255]
        # Incluye soft-deleted: UniqueConstraint + SoftDeleteManager
        block = UsuarioBlock.all_objects.filter(
            blocker=request.user,
            blocked=blocked,
        ).first()
        created = False
        if block is None:
            block = UsuarioBlock.objects.create(
                blocker=request.user,
                blocked=blocked,
                reason=reason,
            )
            created = True
        else:
            if getattr(block, 'is_deleted', False):
                block.restore(user=request.user)
                created = True
            if reason:
                block.reason = reason
                block.save(update_fields=['reason', 'updated_at'])

        # También dejamos un reporte para que el equipo actúe ≤24h
        report = ContentReport.objects.create(
            reporter=request.user,
            reported_user=blocked,
            content_type=ContentReport.ContentType.PROFILE,
            content_id=blocked.id,
            reason=ContentReport.Reason.HARASSMENT,
            details=reason or 'Usuario bloqueado por el reportante.',
        )
        notify_moderators(report)

        return Response(
            UsuarioBlockSerializer(block).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=False, methods=['delete'], url_path=r'bloqueos/(?P<user_id>[^/.]+)')
    def desbloquear(self, request, user_id=None):
        deleted, _ = UsuarioBlock.objects.filter(
            blocker=request.user,
            blocked_id=user_id,
        ).delete()
        if not deleted:
            return Response({'error': 'Bloqueo no encontrado'}, status=404)
        return Response({'ok': True})

    @action(
        detail=False,
        methods=['get'],
        url_path='admin/reportes',
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def admin_reportes(self, request):
        status_filter = request.query_params.get('status', ContentReport.Status.PENDING)
        qs = (
            ContentReport.objects
            .select_related('reporter', 'reported_user')
            .order_by('-created_at')
        )
        if status_filter and status_filter != 'all':
            qs = qs.filter(status=status_filter)
        return Response(ContentReportSerializer(qs[:200], many=True).data)

    @action(
        detail=False,
        methods=['patch'],
        url_path=r'admin/reportes/(?P<report_id>[^/.]+)',
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def admin_actualizar_reporte(self, request, report_id=None):
        report = get_object_or_404(ContentReport, id=report_id)
        new_status = request.data.get('status')
        admin_notes = request.data.get('admin_notes')

        valid_statuses = {c.value for c in ContentReport.Status}
        if new_status is not None:
            if new_status not in valid_statuses:
                return Response(
                    {'error': f'status inválido. Usá: {", ".join(sorted(valid_statuses))}'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            report.status = new_status

        if admin_notes is not None:
            report.admin_notes = str(admin_notes)[:5000]

        report.save()
        return Response(ContentReportSerializer(report).data)
