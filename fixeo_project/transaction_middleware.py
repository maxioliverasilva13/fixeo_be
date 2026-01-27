from django.db import transaction
from django.utils.deprecation import MiddlewareMixin


class ConditionalAtomicRequestsMiddleware(MiddlewareMixin):
    """
    Middleware que aplica transacciones automáticamente solo a requests
    que modifican datos (POST, PUT, PATCH, DELETE)
    """
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            return transaction.atomic()(view_func)(request, *view_args, **view_kwargs)
        
        return None
