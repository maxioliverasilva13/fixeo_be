from urllib.parse import quote
import requests
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from decouple import config
from rest_framework.permissions import AllowAny
from rest_framework.viewsets import ViewSet

class LocalizacionViewSet(ViewSet):
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def find(self, request):
        query = request.query_params.get('q', '').strip()
        country_param = request.query_params.get('country', 'UY').upper().strip()
        city_param = request.query_params.get('city', '').strip()
        lat = request.query_params.get('lat')
        lng = request.query_params.get('lng')

        try:
            limit = int(request.query_params.get('limit', 10))
        except ValueError:
            limit = 10
        limit = min(limit, 10)

        if not query:
            return Response({'error': 'El parámetro "q" es requerido'}, status=400)

        mapbox_token = config('MAPBOX_ACCESS_TOKEN', default=None)

        has_number = any(char.isdigit() for char in query)
        
        params = {
            'access_token': mapbox_token,
            'limit': 10,
            'language': 'es',
            'country': country_param,
            'autocomplete': 'true',
            'types': 'address' if has_number else 'address,place,neighborhood'
        }

        if lat and lng:
            try:
                lat_f, lng_f = float(lat), float(lng)
                params['proximity'] = f"{lng_f},{lat_f}"
                params['bbox'] = f"{lng_f-0.1},{lat_f-0.1},{lng_f+0.1},{lat_f+0.1}"
            except ValueError:
                pass

        try:
            encoded_query = quote(query)
            url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{encoded_query}.json"
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            features = data.get('features', [])

            results = []
            for feature in features:
                context = feature.get('context', [])

                city = next((c['text'] for c in context if 'place' in c['id']), '')
                state = next((c['text'] for c in context if 'region' in c['id']), '')
                country = next((c['text'] for c in context if 'country' in c['id']), '')

                results.append({
                    'place_name': feature.get('place_name'),
                    'address': feature.get('properties', {}).get('address', feature.get('place_name')),
                    'longitude': feature.get('center', [None, None])[0],
                    'latitude': feature.get('center', [None, None])[1],
                    'city': city,
                    'state': state,
                    'country': country,
                    'place_type': feature.get('place_type', ['address'])[0]
                })

            return Response({
                'query': query,
                'country_filter': country_param,
                'used_proximity': bool(lat and lng),
                'results': results,
                'total': len(results)
            })

        except Exception as e:
            return Response({'error': f'Error: {str(e)}'}, status=500)