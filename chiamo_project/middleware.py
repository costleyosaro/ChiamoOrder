# chiamo_project/middleware.py

import logging
import time
import re
from django.http import JsonResponse
from django.conf import settings

logger = logging.getLogger('django.security')


class SecurityHeadersMiddleware:
    """Add extra security headers to all responses."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        
        return response


class RequestLoggingMiddleware:
    """Log suspicious requests for security monitoring."""
    
    SUSPICIOUS_PATTERNS = [
        r'\.\./',
        r'<script',
        r'javascript:',
        r'SELECT.*FROM',
        r'UNION.*SELECT',
        r'INSERT.*INTO',
        r'DROP.*TABLE',
        r'eval\(',
        r'exec\(',
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.patterns = [re.compile(p, re.IGNORECASE) for p in self.SUSPICIOUS_PATTERNS]
    
    def __call__(self, request):
        start_time = time.time()
        
        # Check for suspicious patterns
        self._check_suspicious(request)
        
        response = self.get_response(request)
        
        # Log slow requests (more than 2 seconds)
        duration = time.time() - start_time
        if duration > 2:
            logger.warning(
                f'Slow request: {request.method} {request.path} - {duration:.2f}s'
            )
        
        return response
    
    def _check_suspicious(self, request):
        """Check request for suspicious patterns."""
        full_path = request.get_full_path()
        
        body = ''
        if request.method in ['POST', 'PUT', 'PATCH']:
            try:
                body = request.body.decode('utf-8', errors='ignore')
            except:
                pass
        
        combined = f"{full_path} {body}"
        
        for pattern in self.patterns:
            if pattern.search(combined):
                logger.warning(
                    f'Suspicious request: {request.method} {request.path} '
                    f'from {self._get_client_ip(request)}'
                )
                break
    
    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')