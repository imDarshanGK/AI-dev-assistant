"""
Unit tests for backend/app/services/llm_analysis.py
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.services.llm_analysis import LLMAnalysisClient, LLMAnalysisError

def test_extract_json_success():
    # Test typical valid cases
    assert LLMAnalysisClient._extract_json('{"a": 1}') == {"a": 1}
    assert LLMAnalysisClient._extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert LLMAnalysisClient._extract_json('```\n{"a": 1}\n```') == {"a": 1}
    assert LLMAnalysisClient._extract_json('Here is the json:\n{"a": 1}\nHope this helps') == {"a": 1}


def test_extract_json_complex_braces():
    # Test string with extra outer braces in chat text
    raw = 'The user key is {user_123}. Here is the output:\n{"a": 1}\nFooter details: {some: other}'
    assert LLMAnalysisClient._extract_json(raw) == {"a": 1}
    
    # Test nested valid JSON but with unbalanced outer text containing braces
    raw_nested = 'Notes {not json} {"a": {"b": 2}} trailing {stuff}'
    assert LLMAnalysisClient._extract_json(raw_nested) == {"a": {"b": 2}}


def test_extract_json_failures():
    # Test cases that should raise LLMAnalysisError
    with pytest.raises(LLMAnalysisError):
        LLMAnalysisClient._extract_json('no json here')
        
    with pytest.raises(LLMAnalysisError):
        LLMAnalysisClient._extract_json('{invalid json format')
