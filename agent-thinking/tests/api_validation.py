"""
API Key validation utilities for testing AI service connectivity
"""

import os
from typing import Tuple

import requests
from google import genai
from openai import OpenAI


def check_gemini_api_key(api_key: str, model_name: str = "gemini-2.5-flash-lite-preview-06-17") -> Tuple[bool, str]:
    """
    Check if a Google Gemini API key is valid and can connect to the API.
    
    Args:
        api_key (str): Your Google Gemini API key
        model_name (str): Which model to test with
    
    Returns:
        tuple: (bool: is_valid, str: message)
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
    params = {'key': api_key}
    
    # Simple test payload
    payload = {
        "contents": [{
            "parts": [{
                "text": "Hello"
            }]
        }]
    }
    
    try:
        response = requests.post(url, params=params, json=payload, timeout=30)
        response.raise_for_status()
        
        # Check if we got a successful response
        if response.status_code == 200:
            return True, "API key is valid and working"
        else:
            return False, f"API returned status code: {response.status_code}"
            
    except requests.exceptions.HTTPError as err:
        if response.status_code == 400:
            return False, "Invalid request - possible API key issue"
        elif response.status_code == 403:
            return False, "Permission denied - likely invalid API key"
        else:
            return False, f"HTTP error occurred: {err}"
    except Exception as e:
        return False, f"An error occurred: {str(e)}"


def check_openai_api_key(api_key: str, model_name: str = "gpt-4.1-nano-2025-04-14") -> Tuple[bool, str]:
    """
    Check if an OpenAI API key is valid and can connect to the API.
    
    Args:
        api_key (str): Your OpenAI API key
        model_name (str): Which model to test with
    
    Returns:
        tuple: (bool: is_valid, str: message)
    """
    try:
        client = OpenAI(api_key=api_key)
        
        # Try to make a simple completion request
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=5,
            timeout=30
        )
        
        if response and response.choices:
            return True, "API key is valid and working"
        else:
            return False, "API key validation failed - no response received"
            
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "authentication" in error_msg.lower():
            return False, "Invalid API key - authentication failed"
        elif "404" in error_msg or "model" in error_msg.lower():
            return False, f"Model '{model_name}' not found or not accessible"
        elif "429" in error_msg or "rate" in error_msg.lower():
            return False, "Rate limit exceeded - try again later"
        else:
            return False, f"An error occurred: {error_msg}"