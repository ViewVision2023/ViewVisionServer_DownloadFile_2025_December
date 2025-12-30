#!/usr/bin/env python3
"""
Test script for srt_stats module
Run this after building to verify everything works
"""

import sys

def test_module_import():
    """Test that the module can be imported"""
    print("Test 1: Module import... ", end="")
    try:
        import srt_stats
        print("✓ PASS")
        return True
    except ImportError as e:
        print(f"✗ FAIL: {e}")
        return False

def test_constants():
    """Test that socket state constants are defined"""
    print("Test 2: Constants... ", end="")
    try:
        import srt_stats
        
        expected_constants = {
            'SRTS_INIT': 1,
            'SRTS_OPENED': 2,
            'SRTS_LISTENING': 3,
            'SRTS_CONNECTING': 4,
            'SRTS_CONNECTED': 5,
            'SRTS_BROKEN': 6,
            'SRTS_CLOSING': 7,
            'SRTS_CLOSED': 8,
            'SRTS_NONEXIST': 9,
        }
        
        for name, value in expected_constants.items():
            actual = getattr(srt_stats, name, None)
            if actual != value:
                print(f"✗ FAIL: {name} = {actual}, expected {value}")
                return False
        
        print("✓ PASS")
        return True
    except Exception as e:
        print(f"✗ FAIL: {e}")
        return False

def test_invalid_socket():
    """Test error handling for invalid socket"""
    print("Test 3: Error handling... ", end="")
    try:
        import srt_stats
        
        # Try to get stats for non-existent socket
        try:
            stats = srt_stats.get_stats(999999)
            print("✗ FAIL: Should have raised RuntimeError")
            return False
        except RuntimeError:
            # Expected behavior
            pass
        
        # Try to get state for non-existent socket
        state = srt_stats.get_socket_state(999999)
        if state == srt_stats.SRTS_NONEXIST:
            print("✓ PASS")
            return True
        else:
            print(f"✗ FAIL: Expected SRTS_NONEXIST (9), got {state}")
            return False
            
    except Exception as e:
        print(f"✗ FAIL: {e}")
        return False

def test_function_signatures():
    """Test that functions have correct signatures"""
    print("Test 4: Function signatures... ", end="")
    try:
        import srt_stats
        import inspect
        
        # Check get_stats exists and is callable
        if not callable(getattr(srt_stats, 'get_stats', None)):
            print("✗ FAIL: get_stats not callable")
            return False
        
        # Check get_socket_state exists and is callable
        if not callable(getattr(srt_stats, 'get_socket_state', None)):
            print("✗ FAIL: get_socket_state not callable")
            return False
        
        print("✓ PASS")
        return True
    except Exception as e:
        print(f"✗ FAIL: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 50)
    print("SRT Stats Module Tests")
    print("=" * 50)
    print()
    
    tests = [
        test_module_import,
        test_constants,
        test_invalid_socket,
        test_function_signatures,
    ]
    
    results = []
    for test in tests:
        results.append(test())
        print()
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    print("=" * 50)
    if passed == total:
        print(f"✅ ALL TESTS PASSED ({passed}/{total})")
        print("=" * 50)
        return 0
    else:
        print(f"❌ SOME TESTS FAILED ({passed}/{total})")
        print("=" * 50)
        return 1

if __name__ == "__main__":
    sys.exit(main())
