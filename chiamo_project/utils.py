# chiamo_project/utils.py

from django.http import JsonResponse


def axes_lockout_response(request, credentials, *args, **kwargs):
    """Custom lockout response for failed login attempts."""
    return JsonResponse({
        'success': False,
        'error': {
            'code': 403,
            'message': 'Account locked due to too many failed login attempts. '
                      'Please try again in 30 minutes.',
            'retry_after': 1800
        }
    }, status=403)