#!/usr/bin/env python3
"""
Simple test program to validate Textual's markup escape function
"""

from textual.markup import escape

# Create test strings with problematic square brackets
test_string1 = "Normal text with [square brackets]"
test_string2 = "Array data [100, 150, 200]"
test_string3 = "Text with [b]what looks like[/b] markup tags"
test_string4 = """Multi-line output with brackets:
Line 1: [value1]
Line 2: [100, 200, 300]
Line 3: [this is some text]"""

# Test both the textual.markup.escape function and manual replacement
print("Testing textual.markup.escape:")
print("-" * 50)
print(f"Original: {test_string1}")
print(f"Escaped:  {escape(test_string1)}")
print()
print(f"Original: {test_string2}")
print(f"Escaped:  {escape(test_string2)}")
print()
print(f"Original: {test_string3}")
print(f"Escaped:  {escape(test_string3)}")
print()
print(f"Original: {test_string4}")
print(f"Escaped:  {escape(test_string4)}")

print("\n\nTesting manual replacement:")
print("-" * 50)
print(f"Original: {test_string1}")
print(f"Replaced: {test_string1.replace('[', '[[').replace(']', ']]')}")
print()
print(f"Original: {test_string2}")
print(f"Replaced: {test_string2.replace('[', '[[').replace(']', ']]')}")
print()
print(f"Original: {test_string3}")
print(f"Replaced: {test_string3.replace('[', '[[').replace(']', ']]')}")
print()
print(f"Original: {test_string4}")
print(f"Replaced: {test_string4.replace('[', '[[').replace(']', ']]')}") 