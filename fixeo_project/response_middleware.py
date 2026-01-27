import json
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from rest_framework.response import Response
from rest_framework import status


class StandardizedResponseMiddleware(MiddlewareMixin):
    """
    Middleware que estandariza todas las respuestas de la API
    Formato: { ok: bool, message: str, data: any }
    """
    
    def process_response(self, request, response):
        if not request.path.startswith('/api/'):
            return response
        
        if hasattr(response, 'data'):
            return self._standardize_drf_response(response)
        
        if isinstance(response, JsonResponse):
            return self._standardize_json_response(response)
        
        return response
    
    def _standardize_drf_response(self, response):
        """Estandariza respuestas de Django REST Framework"""
        status_code = response.status_code
        
        is_success = 200 <= status_code < 300
        
        if not response.is_rendered:
            response.render()
        
        message = self._get_message(response.data, status_code, is_success)
        
        data = self._extract_data(response.data)
        
        standardized_data = {
            'ok': is_success,
            'message': message,
            'data': data
        }
        
        # Usar JsonResponse en lugar de Response de DRF para evitar problemas con renderers
        new_response = JsonResponse(standardized_data, status=status_code)
        
        # Copiar headers importantes de la respuesta original
        for header, value in response.items():
            if header.lower() not in ['content-type', 'content-length']:
                new_response[header] = value
        
        return new_response
    
    def _standardize_json_response(self, response):
        """Estandariza respuestas JsonResponse de Django"""
        try:
            data = json.loads(response.content.decode('utf-8'))
        except:
            data = None
        
        status_code = response.status_code
        is_success = 200 <= status_code < 300
        
        standardized_data = {
            'ok': is_success,
            'message': self._get_message(data, status_code, is_success),
            'data': data
        }
        
        return JsonResponse(standardized_data, status=status_code)
    
    def _get_message(self, data, status_code, is_success):
        """Obtiene el mensaje apropiado según el contexto"""
        
        # Si ya viene un mensaje en los datos
        if isinstance(data, dict):
            if 'message' in data:
                return data['message']
            if 'detail' in data:
                return data['detail']
            if 'error' in data:
                return data['error']
        
        messages = {
            200: 'Operación exitosa',
            201: 'Recurso creado exitosamente',
            204: 'Recurso eliminado exitosamente',
            400: 'Solicitud inválida',
            401: 'No autenticado',
            403: 'No autorizado',
            404: 'Recurso no encontrado',
            405: 'Método no permitido',
            500: 'Error interno del servidor',
        }
        
        return messages.get(status_code, 'Operación completada' if is_success else 'Error en la operación')
    
    def _extract_data(self, response_data):
        """Extrae los datos relevantes de la respuesta"""
        
        if isinstance(response_data, dict):
            data = response_data.copy()
            data.pop('message', None)
            data.pop('detail', None)
            data.pop('error', None)
            
            if list(data.keys()) == ['ok']:
                return None
            
            return data if data else None
        
        if isinstance(response_data, list):
            return response_data
        
        return response_data
    
    def process_exception(self, request, exception):
        """Maneja excepciones no capturadas"""
        
        if not request.path.startswith('/api/'):
            return None
        
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Excepción no manejada: {str(exception)}", exc_info=True)
        
        error_response = {
            'ok': False,
            'message': str(exception) if str(exception) else 'Error interno del servidor',
            'data': None
        }
        
        return JsonResponse(error_response, status=500)

