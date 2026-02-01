from localizacion.utils import calcular_distancia_km
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.db import transaction
from usuario.models import Usuario
from usuario.utils import obtener_localizacion_usuario
from usuario_localizacion.models import UsuarioLocalizacion
from usuario_profesion.models import UsuarioProfesion
from usuario.serializers import (
    UsuarioSerializer, UsuarioCreateSerializer,
    ChangePasswordSerializer, LoginSerializer, RegistroSerializer,
    UpdateRangoMapaSerializer
)
from localizacion.models import Localizacion
from empresas.utils import crear_empresa
from profesion.utils import obtener_profesion_por_id
from django.shortcuts import get_object_or_404

class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer

    def get_serializer_class(self):
        if self.action == 'create':
            return UsuarioCreateSerializer
        return UsuarioSerializer

    def get_permissions(self):
        if self.action in ['create', 'login', 'registro']:
            return [AllowAny()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def registro(self, request):
        serializer = RegistroSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            with transaction.atomic():
                if serializer.validated_data['es_empresa']:
                    if not serializer.validated_data.get('latitude') or not serializer.validated_data.get('longitude'):
                        raise ValueError('Las coordenadas son requeridas para crear una empresa')
                
                usuario = Usuario.objects.create_user(
                    correo=serializer.validated_data['email'],
                    password=serializer.validated_data['password'],
                    nombre=serializer.validated_data['nombre'],
                    apellido=serializer.validated_data['apellido'],
                    foto_url=serializer.validated_data.get('foto_url', ''),
                    trabajo_domicilio=serializer.validated_data['trabajo_domicilio'],
                    trabajo_local=serializer.validated_data['trabajo_local'],
                    is_owner_empresa=serializer.validated_data['es_empresa']
                )
                
                if serializer.validated_data.get('latitude') and serializer.validated_data.get('longitude'):
                    localizacion = Localizacion.objects.create(
                        ubicacion=serializer.validated_data.get('direction_name', ''),
                        latitud=serializer.validated_data['latitude'],
                        longitud=serializer.validated_data['longitude'],
                        address=serializer.validated_data.get('direction_name', ''),
                        city='',
                        country='',
                        county='',
                        state='',
                        isPrimary=True
                    )
                    
                    UsuarioLocalizacion.objects.create(
                        usuario=usuario,
                        localizacion=localizacion
                    )
                
                profesion_ids = serializer.validated_data.get('profesion_ids', [])
                for profesion_id in profesion_ids:
                    profesion = obtener_profesion_por_id(profesion_id)
                    if profesion:
                        UsuarioProfesion.objects.create(
                            usuario=usuario,
                            profesion=profesion
                        )
                
                if serializer.validated_data['es_empresa']:
                    localizacion_empresa = UsuarioLocalizacion.objects.filter(usuario=usuario).first()
                    crear_empresa(
                        nombre=f"{usuario.nombre} {usuario.apellido}",
                        ubicacion=serializer.validated_data.get('direction_name', ''),
                        latitud=serializer.validated_data['latitude'],
                        longitud=serializer.validated_data['longitude'],
                        admin_id=usuario,
                        descripcion='',
                        unipersonal=True,
                        localizacion=localizacion_empresa.localizacion if localizacion_empresa else None
                    )
                
                refresh = RefreshToken.for_user(usuario)
                user_data = UsuarioSerializer(usuario).data
                
                return Response({
                    'user': user_data,
                    'tokens': {
                        'refresh': str(refresh),
                        'access': str(refresh.access_token),
                    }
                }, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f'Error al crear el usuario: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def login(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = authenticate(
            username=serializer.validated_data['correo'],
            password=serializer.validated_data['password']
        )
        
        if user is None:
            return Response(
                {'error': 'Credenciales inválidas'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        refresh = RefreshToken.for_user(user)
        user_data = UsuarioSerializer(user).data
        
        return Response({
            'user': user_data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        })

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def logout(self, request):
        try:
            refresh_token = request.data.get('refresh_token')
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({'message': 'Logout exitoso'}, status=status.HTTP_200_OK)
        except Exception:
            return Response({'error': 'Token inválido'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def change_password(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        if not user.check_password(serializer.validated_data['old_password']):
            return Response(
                {'error': 'Contraseña actual incorrecta'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        
        return Response({'message': 'Contraseña cambiada exitosamente'})
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def mis_profesiones(self, request):
        """
        Obtiene las profesiones del usuario logueado
        """
        from profesion.serializers import ProfesionSerializer
        
        usuario_profesiones = request.user.usuario_profesiones.all()
        profesiones = [up.profesion for up in usuario_profesiones]
        
        serializer = ProfesionSerializer(profesiones, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['patch'], permission_classes=[IsAuthenticated])
    def update_rango_mapa(self, request):
        """
        Actualiza el rango del mapa en kilómetros para el usuario logueado
        """
        serializer = UpdateRangoMapaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        usuario = request.user
        usuario.rango_mapa_km = serializer.validated_data['rango_mapa_km']
        usuario.save()
        
        return Response({
            'message': 'Rango del mapa actualizado exitosamente',
            'rango_mapa_km': float(usuario.rango_mapa_km)
        })


    @action(detail=True, methods=['get'], url_path='from-me')
    def from_me(self, request, pk=None):
        """
        Devuelve la distancia en KM entre el usuario logueado
        y otro usuario
        """
        usuario_origen = request.user
        usuario_destino = get_object_or_404(Usuario, pk=pk)

        loc_origen = obtener_localizacion_usuario(usuario_origen)
        loc_destino = obtener_localizacion_usuario(usuario_destino)

        if not loc_origen:
            return Response(
                {'error': 'El usuario logueado no tiene localización'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not loc_destino:
            return Response(
                {'error': 'El usuario destino no tiene localización'},
                status=status.HTTP_400_BAD_REQUEST
            )

        distancia = calcular_distancia_km(
            float(loc_origen.latitud),
            float(loc_origen.longitud),
            float(loc_destino.latitud),
            float(loc_destino.longitud),
        )

        return Response({
            'from_user': usuario_origen.id,
            'to_user': usuario_destino.id,
            'distance_km': distancia,
            'from_location': {
                'city': loc_origen.city,
                'country': loc_origen.country,
            },
            'to_location': {
                'city': loc_destino.city,
                'country': loc_destino.country,
            }
        })
