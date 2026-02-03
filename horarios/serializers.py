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

        if hora_inicio and hora_fin:
            if hora_inicio >= hora_fin:
                raise serializers.ValidationError(
                    'hora_inicio debe ser menor que hora_fin'
                )

        return data

    def create(self, validated_data):
        empresa = validated_data['empresa']
        dia_semana = validated_data['dia_semana']

        horario = Horarios.objects.filter(
            empresa=empresa,
            dia_semana=dia_semana
        ).first()

        if horario:
            # 🔁 UPDATE
            for attr, value in validated_data.items():
                setattr(horario, attr, value)
            horario.save()
            return horario

        # ➕ CREATE
        return super().create(validated_data)

    class Meta:
        model = Horarios
        fields = ['id', 'dia_semana', 'hora_inicio', 'hora_fin', 'enabled', 'empresa']
        read_only_fields = ['id']
