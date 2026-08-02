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


class ContentReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentReport
        fields = [
            'id',
            'reporter',
            'reported_user',
            'content_type',
            'content_id',
            'reason',
            'details',
            'status',
            'created_at',
        ]
        read_only_fields = fields


class UsuarioBlockSerializer(serializers.ModelSerializer):
    blocked_nombre = serializers.SerializerMethodField()

    class Meta:
        model = UsuarioBlock
        fields = ['id', 'blocked', 'blocked_nombre', 'reason', 'created_at']
        read_only_fields = fields

    def get_blocked_nombre(self, obj):
        u = obj.blocked
        return f'{(u.nombre or "").strip()} {(u.apellido or "").strip()}'.strip() or u.correo
