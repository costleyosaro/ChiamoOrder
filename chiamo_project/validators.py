# chiamo_project/validators.py

import re
import bleach
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class CustomPasswordValidator:
    """Custom password validator with additional rules."""
    
    def __init__(self):
        self.min_length = 8
    
    def validate(self, password, user=None):
        errors = []
        
        if len(password) < self.min_length:
            errors.append(f'Password must be at least {self.min_length} characters.')
        
        if not re.search(r'[A-Z]', password):
            errors.append('Password must contain at least one uppercase letter.')
        
        if not re.search(r'[a-z]', password):
            errors.append('Password must contain at least one lowercase letter.')
        
        if not re.search(r'\d', password):
            errors.append('Password must contain at least one digit.')
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append('Password must contain at least one special character.')
        
        if errors:
            raise ValidationError(errors)
    
    def get_help_text(self):
        return _(
            "Your password must contain at least 8 characters, "
            "including uppercase, lowercase, numbers, and special characters."
        )


def sanitize_input(text, allow_html=False):
    """Sanitize user input to prevent XSS."""
    if text is None:
        return None
    
    if not isinstance(text, str):
        return text
    
    if allow_html:
        allowed_tags = ['b', 'i', 'u', 'em', 'strong', 'p', 'br']
        return bleach.clean(text, tags=allowed_tags, attributes={}, strip=True)
    else:
        return bleach.clean(text, tags=[], strip=True)