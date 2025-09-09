"""
Prompt injection detection and mitigation for AI endpoints.

This module provides security safeguards against prompt injection attempts
in user-provided content before forwarding to AI providers.
"""

import re
from typing import Tuple, Dict, Any
from django.http import JsonResponse
from rest_framework import status


# High-risk patterns that should be rejected outright
HIGH_RISK_PATTERNS = [
    r'\b(ignore|disregard|forget)\s+(all|any|previous|above|earlier|everything)',
    r'\bsystem\s*(prompt|message|role)',
    r'\bdeveloper\s*(instructions?|commands?|mode)',
    r'\b(you\s+are\s+now|act\s+as)\s+(chatgpt|gpt|an?\s+ai|assistant|helpful)',
    r'\bjailbreak\b',
    r'\bdan\s+mode\b',
    r'\bdo\s+anything\s+now\b',
    r'```\s*(system|user|assistant)',
    r'\[INST\]|\[\/INST\]',  # Common instruction delimiters
    r'<\|.*\|>',  # Token-like patterns
]

# Medium-risk patterns that should be neutralized but not rejected
MEDIUM_RISK_PATTERNS = [
    r'\bprompt\s+injection\b',
    r'\bchain\s+of\s+thought\b',
    r'\btool\s+(call|usage|invocation)',
    r'\bfunction\s+call',
    r'\bstep\s+by\s+step',
]

# Compiled patterns for performance
_HIGH_RISK_RE = re.compile('|'.join(HIGH_RISK_PATTERNS), re.IGNORECASE)
_MEDIUM_RISK_RE = re.compile('|'.join(MEDIUM_RISK_PATTERNS), re.IGNORECASE)


def analyze_prompt_injection_risk(text: str) -> Tuple[str, Dict[str, Any]]:
    """
    Analyze text for prompt injection patterns.
    
    Returns:
        Tuple of (risk_level, details) where risk_level is 'high', 'medium', or 'low'
    """
    if not isinstance(text, str) or not text.strip():
        return 'low', {}
    
    text_lower = text.lower()
    details = {}
    
    # Check for high-risk patterns
    high_risk_matches = _HIGH_RISK_RE.findall(text)
    if high_risk_matches:
        details['high_risk_patterns'] = high_risk_matches[:3]  # Limit for logging
        return 'high', details
    
    # Check for medium-risk patterns
    medium_risk_matches = _MEDIUM_RISK_RE.findall(text)
    if medium_risk_matches:
        details['medium_risk_patterns'] = medium_risk_matches[:3]
        return 'medium', details
    
    # Additional heuristics for suspicion
    suspicious_indicators = 0
    
    # Multiple role/persona changes
    if text_lower.count('you are') > 2:
        suspicious_indicators += 1
        details['multiple_role_changes'] = True
    
    # Excessive use of instruction-like language
    instruction_words = ['ignore', 'forget', 'disregard', 'override', 'bypass']
    instruction_count = sum(1 for word in instruction_words if word in text_lower)
    if instruction_count >= 3:
        suspicious_indicators += 1
        details['excessive_instructions'] = instruction_count
    
    # Unusual formatting suggesting prompt manipulation
    if text.count('```') > 2 or text.count('[') > 5 or text.count('<|') > 1:
        suspicious_indicators += 1
        details['suspicious_formatting'] = True
    
    if suspicious_indicators >= 2:
        return 'medium', details
    
    return 'low', details


def sanitize_medium_risk_content(text: str) -> str:
    """
    Neutralize medium-risk content by replacing suspicious patterns.
    """
    # Replace medium-risk patterns with placeholder
    sanitized = _MEDIUM_RISK_RE.sub('[content-filtered]', text)
    
    # Additional character-level sanitization
    # Remove potential instruction delimiters
    sanitized = re.sub(r'```\s*(system|user|assistant)', '[code-block]', sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r'\[INST\]|\[\/INST\]', '[instruction]', sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r'<\|[^|]*\|>', '[token]', sanitized)
    
    return sanitized


def prompt_shield_middleware(text: str) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Main prompt shield function.
    
    Returns:
        Tuple of (allowed, processed_text, metadata)
        - allowed: False if content should be rejected
        - processed_text: sanitized version of input
        - metadata: details about detection and processing
    """
    risk_level, details = analyze_prompt_injection_risk(text)
    
    metadata = {
        'risk_level': risk_level,
        'original_length': len(text),
        'details': details
    }
    
    if risk_level == 'high':
        return False, text, metadata
    elif risk_level == 'medium':
        sanitized = sanitize_medium_risk_content(text)
        metadata['sanitized_length'] = len(sanitized)
        return True, sanitized, metadata
    else:
        return True, text, metadata


def create_injection_rejection_response(metadata: Dict[str, Any]) -> JsonResponse:
    """
    Create a standardized rejection response for high-risk content.
    """
    return JsonResponse({
        'error': 'prompt_injection_detected',
        'message': 'Content was flagged as potentially unsafe and cannot be processed.',
        'risk_level': metadata.get('risk_level'),
        'code': 'INJECTION_SHIELD_BLOCK'
    }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)