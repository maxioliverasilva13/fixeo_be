from rest_framework import serializers

from .models import ContentReport, UsuarioBlock


class ContentReportCreateSerializer(serializers.Serializer):
    content_type = serializers.ChoiceField(choices=ContentReport.ContentType.choices)
    content_id = serializers.IntegerField(required=False, allow_null=True)
    reported_user_id = serializers.IntegerField(required=False, allow_null=True)
    reason = serializers.ChoiceField(
        choices=ContentReport.Reason.choices,
        default=ContentReport.Reason.OTHER,
    )
    details = serializers.CharField(required=False, allow_blank=True, max_length=2000)


def _user_display_name(user) -> str | None:
    if not user:
        return None
    name = f'{(user.nombre or "").strip()} {(user.apellido or "").strip()}'.strip()
    return name or user.correo or str(user.id)


class ContentReportSerializer(serializers.ModelSerializer):
    reporter_nombre = serializers.SerializerMethodField()
    reporter_correo = serializers.SerializerMethodField()
    reported_user_nombre = serializers.SerializerMethodField()
    reported_user_correo = serializers.SerializerMethodField()

    class Meta:
        model = ContentReport
        fields = [
            'id',
            'reporter',
            'reporter_nombre',
            'reporter_correo',
            'reported_user',
            'reported_user_nombre',
            'reported_user_correo',
            'content_type',
            'content_id',
            'reason',
            'details',
            'status',
            'admin_notes',
            'created_at',
        ]
        read_only_fields = fields

    def get_reporter_nombre(self, obj):
        return _user_display_name(obj.reporter)

    def get_reporter_correo(self, obj):
        return getattr(obj.reporter, 'correo', None)

    def get_reported_user_nombre(self, obj):
        return _user_display_name(obj.reported_user)

    def get_reported_user_correo(self, obj):
        return getattr(obj.reported_user, 'correo', None) if obj.reported_user else None


class UsuarioBlockSerializer(serializers.ModelSerializer):
    blocked_nombre = serializers.SerializerMethodField()

    class Meta:
        model = UsuarioBlock
        fields = ['id', 'blocked', 'blocked_nombre', 'reason', 'created_at']
        read_only_fields = fields

    def get_blocked_nombre(self, obj):
        u = obj.blocked
        return f'{(u.nombre or "").strip()} {(u.apellido or "").strip()}'.strip() or u.correo
