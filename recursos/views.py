from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from decouple import config
import uuid
import os


class RecursosViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    @action(detail=False, methods=['post'], url_path='upload')
    def upload(self, request):
        """
        Sube un archivo a Supabase Storage
        """
        from .serializers import UploadFileSerializer
        
        serializer = UploadFileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        supabase_url = config('SUPABASE_URL', default=None)
        supabase_key = config('SUPABASE_KEY', default=None)
        supabase_bucket = config('SUPABASE_BUCKET', default='fixeo-uploads')
        
        if not supabase_url or not supabase_key:
            return Response(
                {'error': 'Credenciales de Supabase no configuradas. Configure SUPABASE_URL y SUPABASE_KEY en el archivo .env'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        try:
            from supabase import create_client
            
            # Crear cliente de Supabase
            supabase = create_client(supabase_url, supabase_key)
            
            # Obtener el archivo y la carpeta
            file = serializer.validated_data['file']
            folder = serializer.validated_data.get('folder', 'uploads')
            
            # Generar nombre único para el archivo
            file_extension = os.path.splitext(file.name)[1]
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            file_path = f"{folder}/{unique_filename}"
            
            # Leer el contenido del archivo
            file_content = file.read()
            
            # Subir archivo a Supabase Storage
            response = supabase.storage.from_(supabase_bucket).upload(
                path=file_path,
                file=file_content,
                file_options={
                    "content-type": file.content_type,
                    "x-upsert": "false"
                }
            )
            
            # Obtener URL pública del archivo
            public_url = supabase.storage.from_(supabase_bucket).get_public_url(file_path)
            
            return Response({
                'message': 'Archivo subido exitosamente',
                'file_path': file_path,
                'public_url': public_url,
                'original_name': file.name,
                'size': file.size,
                'content_type': file.content_type
            }, status=status.HTTP_201_CREATED)
            
        except ImportError:
            return Response(
                {'error': 'La librería supabase-py no está instalada. Ejecute: pip install supabase'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response(
                {'error': f'Error al subir archivo a Supabase: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
