from rest_framework import serializers
from enums.enums import divisas_permitidas_para_pais


def validar_divisa_empresa(empresa, divisa: str, field_name: str = 'divisa') -> str:
    if not divisa:
        raise serializers.ValidationError({field_name: 'La moneda es obligatoria'})
    permitidas = divisas_permitidas_para_pais(empresa.pais)
    if divisa not in permitidas:
        raise serializers.ValidationError({
            field_name: f"Solo podés usar: {', '.join(permitidas)}"
        })
    return divisa
