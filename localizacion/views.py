from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from decouple import config
from .models import Localizacion
from .serializers import LocalizacionSerializer


class LocalizacionViewSet(viewsets.ModelViewSet):
    queryset = Localizacion.objects.all()
    serializer_class = LocalizacionSerializer
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def find(self, request):
        """
        Busca direcciones usando Mapbox Geocoding API
        Query params:
        - q: string de búsqueda (requerido)
        - limit: número máximo de resultados (opcional, default: 5)
        """
        query = request.query_params.get('q', '').strip()
        limit = int(request.query_params.get('limit', 5))
        
        if not query:
            return Response(
                {'error': 'El parámetro "q" es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        mapbox_token = config('MAPBOX_ACCESS_TOKEN', default=None)
        
        if not mapbox_token:
            hardcoded_results = [
                {
                    'place_name': 'Av. Corrientes 1234, Buenos Aires, Argentina',
                    'center': [-58.381592, -34.603722],
                    'place_type': ['address'],
                    'properties': {
                        'address': 'Av. Corrientes 1234'
                    },
                    'context': [
                        {'id': 'locality', 'text': 'Buenos Aires'},
                        {'id': 'region', 'text': 'Ciudad Autónoma de Buenos Aires'},
                        {'id': 'country', 'text': 'Argentina'}
                    ]
                },
                {
                    'place_name': 'Av. Santa Fe 5678, Buenos Aires, Argentina',
                    'center': [-58.399544, -34.595412],
                    'place_type': ['address'],
                    'properties': {
                        'address': 'Av. Santa Fe 5678'
                    },
                    'context': [
                        {'id': 'locality', 'text': 'Buenos Aires'},
                        {'id': 'region', 'text': 'Ciudad Autónoma de Buenos Aires'},
                        {'id': 'country', 'text': 'Argentina'}
                    ]
                },
                {
                    'place_name': 'Av. 9 de Julio 1000, Buenos Aires, Argentina',
                    'center': [-58.381775, -34.607814],
                    'place_type': ['address'],
                    'properties': {
                        'address': 'Av. 9 de Julio 1000'
                    },
                    'context': [
                        {'id': 'locality', 'text': 'Buenos Aires'},
                        {'id': 'region', 'text': 'Ciudad Autónoma de Buenos Aires'},
                        {'id': 'country', 'text': 'Argentina'}
                    ]
                }
            ]
            
            results = []
            for feature in hardcoded_results[:limit]:
                city = next((c['text'] for c in feature.get('context', []) if c['id'] == 'locality'), '')
                state = next((c['text'] for c in feature.get('context', []) if c['id'] == 'region'), '')
                country = next((c['text'] for c in feature.get('context', []) if c['id'] == 'country'), '')
                
                results.append({
                    'place_name': feature['place_name'],
                    'address': feature.get('properties', {}).get('address', feature['place_name']),
                    'longitude': feature['center'][0],
                    'latitude': feature['center'][1],
                    'city': city,
                    'state': state,
                    'country': country,
                    'place_type': feature.get('place_type', ['address'])[0]
                })
            
            return Response({
                'query': query,
                'results': results,
                'total': len(results),
                'note': 'Resultados hardcodeados - Configure MAPBOX_ACCESS_TOKEN para usar Mapbox API'
            })
        
        try:
            import requests
            
            url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{query}.json"
            params = {
                'access_token': mapbox_token,
                'limit': limit,
                'language': 'es',
                'country': 'AR'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            features = data.get('features', [])
            
            results = []
            for feature in features:
                city = next((c['text'] for c in feature.get('context', []) if 'place' in c['id']), '')
                state = next((c['text'] for c in feature.get('context', []) if 'region' in c['id']), '')
                country = next((c['text'] for c in feature.get('context', []) if 'country' in c['id']), '')
                
                results.append({
                    'place_name': feature['place_name'],
                    'address': feature.get('properties', {}).get('address', feature['place_name']),
                    'longitude': feature['center'][0],
                    'latitude': feature['center'][1],
                    'city': city,
                    'state': state,
                    'country': country,
                    'place_type': feature.get('place_type', ['address'])[0]
                })
            
            return Response({
                'query': query,
                'results': results,
                'total': len(results)
            })
            
        except ImportError:
            return Response(
                {'error': 'La librería requests no está instalada. Ejecute: pip install requests'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except requests.exceptions.RequestException as e:
            return Response(
                {'error': f'Error al conectar con Mapbox API: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response(
                {'error': f'Error inesperado: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
