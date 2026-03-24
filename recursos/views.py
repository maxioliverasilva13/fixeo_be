from asgiref.sync import async_to_sync
from mensajeria.models import Chat, Recurso
from mensajeria.serializers import RecursoSerializer
from notificaciones.tasks import notificar_usuario
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from decouple import config
from django.shortcuts import get_object_or_404
from usuario.models import Usuario
import uuid
import os
import requests
import io
from PIL import Image, ImageDraw
from channels.layers import get_channel_layer
from rest_framework.permissions import AllowAny, IsAuthenticated

class RecursosViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_permissions(self):
       if self.action in ['upload']:
           return [AllowAny()]
       return [IsAuthenticated()]
    
    def _compress_image(self, image_bytes, max_size=(800, 800), quality=75):
        """
        Comprime una imagen manteniendo proporción
        """
        try:
            img = Image.open(io.BytesIO(image_bytes))
            
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = background
            
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=quality, optimize=True)
            buffer.seek(0)
            
            return buffer.getvalue()
        except Exception:
            return image_bytes
    
    def _create_rounded_image(self, image_bytes, size=(400, 400)):
        try:
            img = Image.open(io.BytesIO(image_bytes)).convert('RGBA')
            
            output = Image.new('RGBA', size, (0, 0, 0, 0))
            
            img_ratio = img.width / img.height
            target_ratio = 1
            
            if img_ratio > target_ratio:
                new_height = size[1]
                new_width = int(new_height * img_ratio)
            else:
                new_width = size[0]
                new_height = int(new_width / img_ratio)
            
            img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            left = (new_width - size[0]) // 2
            top = (new_height - size[1]) // 2
            img_cropped = img_resized.crop((left, top, left + size[0], top + size[1]))
            
            output.paste(img_cropped, (0, 0))
            
            mask = Image.new('L', size, 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, size[0], size[1]), fill=255)
            
            output.putalpha(mask)
            
            buffer = io.BytesIO()
            output.save(buffer, format='PNG')
            buffer.seek(0)
            return buffer.getvalue()
            
        except Exception as e:
            print(f"Error: {e}")
            return None
    
    def _upload_to_supabase(self, file_content, file_path, content_type, supabase_url, supabase_key, supabase_bucket):
        """ 
        """
        upload_url = f"{supabase_url}/storage/v1/object/{supabase_bucket}/{file_path}"
        
        headers = {
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": content_type,
            "x-upsert": "false"
        }
        
        response = requests.post(upload_url, data=file_content, headers=headers, timeout=30)
        
        if response.status_code not in [200, 201]:
            raise Exception(f"Error de Supabase: {response.text}")
        
        public_url = f"{supabase_url}/storage/v1/object/public/{supabase_bucket}/{file_path}"
        return public_url
    
    @action(detail=False, methods=['post'], url_path='upload')
    def upload(self, request):
        """
        Sube un archivo genérico a Supabase Storage.
        
        Query params:
        - isProfile: bool - Si es true, sube imagen normal + versión redondeada (solo imágenes)
        """
        import requests
        
        # Validar archivo
        if 'file' not in request.FILES:
            return Response(
                {'error': 'No se proporcionó ningún archivo'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        file = request.FILES['file']
        is_profile = request.query_params.get('isProfile', 'false').lower() == 'true'
        
        supabase_url = config('SUPABASE_URL')
        supabase_key = config('SUPABASE_KEY')
        supabase_bucket = config('SUPABASE_BUCKET', default='fixeo-uploads')
        
        if not supabase_url or not supabase_key:
            return Response(
                {'error': 'Credenciales de Supabase no configuradas'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        try:
            file_content = file.read()
            content_type = file.content_type or "application/octet-stream"
            is_image = content_type.startswith('image/')
            
            # Generar paths únicos
            file_extension = os.path.splitext(file.name)[1]
            base_filename = str(uuid.uuid4())
            
            result = {
                'original_name': file.name,
                'content_type': content_type,
                'size': file.size,
            }
            
            # Si es imagen, comprimir
            if is_image:
                if is_profile:
                    file_content = self._compress_image(file_content, max_size=(600, 600), quality=80)
                else:
                    file_content = self._compress_image(file_content, max_size=(1080, 1080), quality=82)
            
            # Subir archivo principal
            file_path = f"uploads/{base_filename}{file_extension}"
            public_url = self._upload_to_supabase(
                file_content, file_path, content_type if not is_image else 'image/jpeg',
                supabase_url, supabase_key, supabase_bucket
            )
            result['url'] = public_url
            
            # Si es perfil y es imagen, crear versión redondeada
            if is_profile and is_image:
                rounded_content = self._create_rounded_image(file_content)
                if rounded_content:
                    rounded_path = f"uploads/{base_filename}_rounded.png"
                    rounded_url = self._upload_to_supabase(
                        rounded_content, rounded_path, 'image/png',
                        supabase_url, supabase_key, supabase_bucket
                    )
                    result['rounded_image'] = rounded_url
            
            return Response(result, status=status.HTTP_201_CREATED)
            
        except requests.exceptions.RequestException as e:
            return Response(
                {'error': f'Error de conexión: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response(
                {'error': f'Error al subir archivo: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'], url_path='adjuntar')
    def adjuntar_a_chat(self, request, pk=None):
        """
        Adjunta un recurso existente (por URL) a un chat.
        
        Body:
        - url: string (URL del archivo en Supabase)
        - tipo: string (opcional, auto-detectfado si no se proporciona)
        - nombre: string (opcional, nombre original del archivo)
        - size: int (opcional)
        - content_type: string (opcional)
        """
        chat = get_object_or_404(Chat, pk=pk)
        
        # Verificar permisos
        if chat.sender != request.user and chat.receiver != request.user:
            return Response(
                {'error': 'No tienes permiso en este chat'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Validar datos
        url = request.data.get('url')
        if not url:
            return Response(
                {'error': 'Se requiere la URL del recurso'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Determinar tipo si no se proporciona
        tipo = request.data.get('tipo')
        content_type = request.data.get('content_type', '')
        
        if not tipo:
            if content_type:
                if content_type.startswith('image/'):
                    tipo = 'imagen'
                elif content_type.startswith('video/'):
                    tipo = 'video'
                elif content_type.startswith('audio/'):
                    tipo = 'audio'
                else:
                    tipo = 'archivo'
            else:
                # Inferir de la extensión de la URL
                extension = os.path.splitext(url)[1].lower()
                image_exts = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
                video_exts = ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm']
                audio_exts = ['.mp3', '.wav', '.ogg', '.m4a', '.aac', '.wma']
                
                if extension in image_exts:
                    tipo = 'imagen'
                elif extension in video_exts:
                    tipo = 'video'
                elif extension in audio_exts:
                    tipo = 'audio'
                else:
                    tipo = 'archivo'
        
        # Crear recurso
        recurso = Recurso.objects.create(
            url=url,
            tipo=tipo,
            nombre=request.data.get('nombre', os.path.basename(url.split('?')[0])),
            chat=chat,
            size=request.data.get('size'),
            content_type=content_type or request.data.get('content_type')
        )
        
        # Notificar al otro usuario vía WebSocket
        received_user = chat.receiver if request.user.id == chat.sender_id else chat.sender
        room_name = f"usuario_channel_{received_user.id}"
        channel_layer = get_channel_layer()
        
        payload = {
            'type': 'chat_recurso',
            'recurso': {
                'id': recurso.id,
                'url': recurso.url,
                'tipo': recurso.tipo,
                'nombre': recurso.nombre,
                'size': recurso.size,
                'chat_id': chat.id,
                'created_at': recurso.created_at.isoformat(),
            },
            'user_id': request.user.id,
        }
        
        async_to_sync(channel_layer.group_send)(f'chat_{room_name}', payload)
        
        notificar_usuario.delay(
            usuario_id=received_user.id,
            titulo=f"Nuevo archivo de {request.user.nombre}",
            mensaje=f"Te envió un {tipo}",
            data={
                'deep_link': f'fixeo://chats/{chat.id}',
                'entity_id': chat.id
            }
        )
        
        return Response(
            RecursoSerializer(recurso).data,
            status=status.HTTP_201_CREATED
        )