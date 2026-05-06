from rest_framework import serializers
from .models import SurveyResponse

class SurveyResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = SurveyResponse
        fields = ['id', 'name', 'email', 'likelihood', 'role', 'willing_to_pay', 'submitted_at']
        read_only_fields = ['id', 'submitted_at']