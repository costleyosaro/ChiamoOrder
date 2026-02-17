# your_app_name/decorators.py

from functools import wraps
from django.http import JsonResponse
from django.core.cache import cache
import hashlib
import time


def rate_limit(requests_per_minute=60, key_prefix='rate_limit'):
    """Custom rate limiting decorator."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Create unique key based on IP and endpoint
            ip = get_client_ip(request)
            endpoint = f"{request.method}:{request.path}"
            cache_key = f"{key_prefix}:{hashlib.md5(f'{ip}:{endpoint}'.encode()).hexdigest()}"
            
            # Get current request count
            request_count = cache.get(cache_key, 0)
            
            if request_count >= requests_per_minute:
                return JsonResponse({
                    'success': False,
                    'error': {
                        'code': 429,
                        'message': 'Rate limit exceeded. Please slow down.',
                        'retry_after': 60
                    }
                }, status=429)
            
            # Increment counter
            cache.set(cache_key, request_count + 1, 60)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_https(view_func):
    """Require HTTPS for sensitive endpoints."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.is_secure() and not settings.DEBUG:
            return JsonResponse({
                'success': False,
                'error': {
                    'code': 403,
                    'message': 'HTTPS required.'
                }
            }, status=403)
        return view_func(request, *args, **kwargs)
    return wrapper


def validate_content_type(allowed_types=['application/json']):
    """Validate content type of requests."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.method in ['POST', 'PUT', 'PATCH']:
                content_type = request.content_type
                if not any(t in content_type for t in allowed_types):
                    return JsonResponse({
                        'success': False,
                        'error': {
                            'code': 415,
                            'message': f'Unsupported content type. Allowed: {allowed_types}'
                        }
                    }, status=415)
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def get_client_ip(request):
    """Get client IP address."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')