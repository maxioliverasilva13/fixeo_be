from rest_framework import serializers


class UploadFileSerializer(serializers.Serializer):
    file = serializers.FileField(required=True)
    folder = serializers.CharField(required=False, default='uploads', max_length=255)
    
    def validate_file(self, value):
        max_size = 10 * 1024 * 1024 
        if value.size > max_size:
            raise serializers.ValidationError("El archivo no puede superar los 10MB")
        return value
