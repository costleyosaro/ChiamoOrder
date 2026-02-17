# chiamo_project/exceptions.py

import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger('django.security')


def custom_exception_handler(exc, context):
    """Custom exception handler with security logging."""
    
    response = exception_handler(exc, context)
    request = context.get('request')
    
    if response is not None:
        custom_response_data = {
            'success': False,
            'error': {
                'code': response.status_code,
                'message': _get_error_message(exc),
            }
        }
        
        if response.status_code >= 400:
            logger.warning(
                f'API Error: {response.status_code} - '
                f'{request.method if request else "?"} '
                f'{request.path if request else "?"}'
            )
        
        response.data = custom_response_data
    else:
        logger.error(f'Unhandled Exception: {type(exc).__name__} - {str(exc)}')
        
        response = Response({
            'success': False,
            'error': {
                'code': 500,
                'message': 'An unexpected error occurred.'
            }
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return response


def _get_error_message(exc):
    """Get user-friendly error message."""
    if hasattr(exc, 'detail'):
        detail = exc.detail
        if isinstance(detail, dict):
            for key, value in detail.items():
                if isinstance(value, list):
                    return str(value[0])
                return str(value)
        elif isinstance(detail, list):
            return str(detail[0])
        return str(detail)
    return str(exc)