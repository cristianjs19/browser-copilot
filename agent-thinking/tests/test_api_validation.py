"""
Tests for API key validation functionality
"""

from unittest.mock import Mock, patch

import pytest
import requests

from .api_validation import check_gemini_api_key, check_openai_api_key

# from openai import OpenAI


class TestGeminiAPIValidation:
    """Test Gemini API key validation"""
    
    def test_valid_gemini_api_key(self):
        """Test with valid Gemini API key"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        
        with patch('requests.post', return_value=mock_response):
            is_valid, message = check_gemini_api_key("valid_key")
            
            assert is_valid is True
            assert message == "API key is valid and working"
    
    def test_invalid_gemini_api_key_403(self):
        """Test with invalid Gemini API key (403 error)"""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError()
        
        with patch('requests.post', return_value=mock_response):
            is_valid, message = check_gemini_api_key("invalid_key")
            
            assert is_valid is False
            assert "Permission denied" in message
    
    def test_invalid_gemini_api_key_400(self):
        """Test with invalid Gemini API key (400 error)"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError()
        
        with patch('requests.post', return_value=mock_response):
            is_valid, message = check_gemini_api_key("invalid_key")
            
            assert is_valid is False
            assert "Invalid request" in message
    
    def test_gemini_api_key_network_error(self):
        """Test Gemini API key validation with network error"""
        with patch('requests.post', side_effect=requests.exceptions.ConnectionError("Network error")):
            is_valid, message = check_gemini_api_key("test_key")
            
            assert is_valid is False
            assert "An error occurred" in message
    
    def test_gemini_api_key_timeout(self):
        """Test Gemini API key validation with timeout"""
        with patch('requests.post', side_effect=requests.exceptions.Timeout("Request timed out")):
            is_valid, message = check_gemini_api_key("test_key")
            
            assert is_valid is False
            assert "An error occurred" in message
    
    def test_gemini_api_key_custom_model(self):
        """Test Gemini API key validation with custom model"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        
        with patch('requests.post', return_value=mock_response) as mock_post:
            is_valid, message = check_gemini_api_key("valid_key", "custom-model")
            
            assert is_valid is True
            assert message == "API key is valid and working"
            # Verify the correct model was used in the URL
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "custom-model" in call_args[0][0]  # URL is first positional argument


class TestOpenAIAPIValidation:
    """Test OpenAI API key validation"""
    
    def test_valid_openai_api_key(self):
        """Test with valid OpenAI API key"""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "Hello"
        
        with patch('tests.api_validation.OpenAI') as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client
            
            is_valid, message = check_openai_api_key("valid_key")
            
            assert is_valid is True
            assert message == "API key is valid and working"
    
    def test_invalid_openai_api_key_401(self):
        """Test with invalid OpenAI API key (401 error)"""
        with patch('tests.api_validation.OpenAI') as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create.side_effect = Exception("401 authentication failed")
            mock_openai.return_value = mock_client
            
            is_valid, message = check_openai_api_key("invalid_key")
            
            assert is_valid is False
            assert "Invalid API key" in message
    
    def test_openai_api_key_model_not_found(self):
        """Test OpenAI API key validation with model not found"""
        with patch('tests.api_validation.OpenAI') as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create.side_effect = Exception("404 model not found")
            mock_openai.return_value = mock_client
            
            is_valid, message = check_openai_api_key("valid_key", "non-existent-model")
            
            assert is_valid is False
            assert "Model 'non-existent-model' not found" in message
    
    def test_openai_api_key_rate_limit(self):
        """Test OpenAI API key validation with rate limit"""
        with patch('tests.api_validation.OpenAI') as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create.side_effect = Exception("429 rate limit exceeded")
            mock_openai.return_value = mock_client
            
            is_valid, message = check_openai_api_key("valid_key")
            
            assert is_valid is False
            assert "Rate limit exceeded" in message
    
    def test_openai_api_key_no_response(self):
        """Test OpenAI API key validation with no response"""
        with patch('tests.api_validation.OpenAI') as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create.return_value = None
            mock_openai.return_value = mock_client
            
            is_valid, message = check_openai_api_key("valid_key")
            
            assert is_valid is False
            assert "API key validation failed" in message
    
    def test_openai_api_key_empty_choices(self):
        """Test OpenAI API key validation with empty choices"""
        mock_response = Mock()
        mock_response.choices = []
        
        with patch('tests.api_validation.OpenAI') as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client
            
            is_valid, message = check_openai_api_key("valid_key")
            
            assert is_valid is False
            assert "API key validation failed" in message
    
    def test_openai_api_key_custom_model(self):
        """Test OpenAI API key validation with custom model"""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "Hello"
        
        with patch('tests.api_validation.OpenAI') as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client
            
            is_valid, message = check_openai_api_key("valid_key", "custom-model")
            
            assert is_valid is True
            assert message == "API key is valid and working"
            # Verify the correct model was used
            mock_client.chat.completions.create.assert_called_once()
            call_args = mock_client.chat.completions.create.call_args
            assert call_args[1]['model'] == "custom-model"
    
    def test_openai_api_key_generic_error(self):
        """Test OpenAI API key validation with generic error"""
        with patch('tests.api_validation.OpenAI') as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create.side_effect = Exception("Generic error")
            mock_openai.return_value = mock_client
            
            is_valid, message = check_openai_api_key("valid_key")
            
            assert is_valid is False
            assert "An error occurred: Generic error" in message
    
    def test_openai_api_key_with_base_url(self):
        """Test OpenAI API key validation with custom base URL"""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "Hello"
        
        with patch('tests.api_validation.OpenAI') as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client
            
            is_valid, message = check_openai_api_key("valid_key", "gpt-4")
            
            assert is_valid is True
            assert message == "API key is valid and working"