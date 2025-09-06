#!/usr/bin/env python3
"""
Test script to verify the quoted reply functionality
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from comments import get_parent_comment_for_reply
from utils import escape_markdown_text

def test_quoted_reply_formatting():
    """Test the quoted reply formatting functionality"""
    
    # Sample data for testing
    sample_parent_info = {
        'comment_id': 123,
        'post_id': 45,
        'content': 'This is a test comment that users might reply to. It contains some text that should be displayed in the quoted block.',
        'timestamp': '2024-01-15 10:30:00',
        'sequential_number': 1
    }
    
    # Test the formatting logic
    if sample_parent_info:
        # Create a quoted block showing the original comment
        parent_preview = escape_markdown_text(sample_parent_info['content'][:100] + "..." if len(sample_parent_info['content']) > 100 else sample_parent_info['content'])
        parent_number = sample_parent_info['sequential_number']
        
        # Format with quoted block (like forwarded message)
        quoted_block = f"┌─ *comment\\# {parent_number}*\n│ {parent_preview}\n└─────────────────"
        reply_text = f"{quoted_block}\n\nreply# 1\n\nThis is a test reply to the comment above.\n\n2024-01-15 11:00"
        
        print("=== Quoted Reply Format Test ===")
        print(reply_text)
        print("\n=== With MarkdownV2 Escaping ===")
        print(reply_text.replace("\\", "\\\\"))
    
    print("\n=== Testing Characters ===")
    test_chars = ["┌", "─", "│", "└"]
    for char in test_chars:
        print(f"Character '{char}': \\u{ord(char):04x}")

def test_long_comment():
    """Test with a long comment that needs truncation"""
    long_content = "This is a very long comment that exceeds the 100 character limit and should be truncated with ellipsis at the end to prevent the quoted block from becoming too large and overwhelming in the chat interface."
    
    parent_info = {
        'comment_id': 456,
        'content': long_content,
        'sequential_number': 2
    }
    
    # Create truncated preview
    parent_preview = escape_markdown_text(parent_info['content'][:100] + "..." if len(parent_info['content']) > 100 else parent_info['content'])
    parent_number = parent_info['sequential_number']
    
    # Format with quoted block
    quoted_block = f"┌─ *comment\\# {parent_number}*\n│ {parent_preview}\n└─────────────────"
    reply_text = f"{quoted_block}\n\nreply# 1\n\nThis is a reply to the long comment.\n\n2024-01-15 11:30"
    
    print("\n=== Long Comment Truncation Test ===")
    print(reply_text)

if __name__ == "__main__":
    test_quoted_reply_formatting()
    test_long_comment()
