from rest_framework import serializers
from empresas.models import Horarios
from datetime import time


class HorariosSerializer(serializers.ModelSerializer):

    def validate_dia_semana(self, value):
        try:
            dia = int(value)
        except ValueError:
            raise serializers.ValidationError("dia_semana debe ser un número entre 1 y 7")

        if dia < 1 or dia > 7:
            raise serializers.ValidationError("dia_semana debe estar entre 1 y 7")

        return value

    def validate(self, data):
        hora_inicio = data.get('hora_inicio')
        hora_fin = data.get('hora_fin')
        dia_semana = data.get('dia_semana')
        empresa = data.get('empresa')

        # Validaciones básicas de hora
        if hora_inicio and hora_fin:
            if hora_inicio >= hora_fin:
                raise serializers.ValidationError(
                    'hora_inicio debe ser menor que hora_fin'
                )

            if not (time(0, 0) <= hora_inicio <= time(23, 59)):
                raise serializers.ValidationError({
                    'hora_inicio': 'Debe estar entre 00:00:00 y 23:59:00'
                })

            if not (time(0, 0) <= hora_fin <= time(23, 59)):
                raise serializers.ValidationError({
                    'hora_fin': 'Debe estar entre 00:00:00 y 23:59:00'
                })

        if hora_inicio and hora_fin and dia_semana and empresa:
            qs = Horarios.objects.filter(
                empresa=empresa,
                dia_semana=dia_semana,
                enabled=True
            )

            if self.instance:
                qs = qs.exclude(id=self.instance.id)

            solapado = qs.filter(
                hora_inicio__lt=hora_fin,
                hora_fin__gt=hora_inicio
            ).exists()

            if solapado:
                raise serializers.ValidationError(
                    "El horario se solapa con otro existente para ese día"
                )

        return data

    class Meta:
        model = Horarios
        fields = ['id', 'dia_semana', 'hora_inicio', 'hora_fin', 'enabled', 'empresa']
        read_only_fields = ['id']
