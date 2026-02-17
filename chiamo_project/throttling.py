# chiamo_project/throttling.py

from rest_framework.throttling import SimpleRateThrottle


class BurstRateThrottle(SimpleRateThrottle):
    """Throttle for burst requests."""
    scope = 'burst'
    
    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }


class LoginRateThrottle(SimpleRateThrottle):
    """Strict throttle for login attempts."""
    scope = 'login'
    
    def get_cache_key(self, request, view):
        return self.cache_format % {
            'scope': self.scope,
            'ident': self.get_ident(request)
        }


class RegisterRateThrottle(SimpleRateThrottle):
    """Throttle for registration."""
    scope = 'register'
    
    def get_cache_key(self, request, view):
        return self.cache_format % {
            'scope': self.scope,
            'ident': self.get_ident(request)
        }


class AddToCartRateThrottle(SimpleRateThrottle):
    """Throttle for add to cart."""
    scope = 'add_to_cart'
    
    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }