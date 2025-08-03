#!/usr/bin/env python3
"""
Test Runner for AWS S3 Sync Application

This script runs the complete test suite and provides
detailed reporting on test results and coverage.

Usage:
    python run_tests.py                    # Run all tests
    python run_tests.py --verbose         # Run with verbose output
    python run_tests.py --coverage        # Run with coverage report
    python run_tests.py tests/test_sync.py # Run specific test file
"""

import argparse
import subprocess
import sys
from pathlib import Path

def run_tests(test_path=None, verbose=False, coverage=False, html_report=False):
    """Run the test suite with specified options"""
    
    # Build pytest command
    cmd = ["python", "-m", "pytest"]
    
    if verbose:
        cmd.append("-v")
    
    if coverage:
        cmd.extend(["--cov=scripts", "--cov-report=term-missing"])
        if html_report:
            cmd.append("--cov-report=html")
    
    # Add test path if specified
    if test_path:
        cmd.append(test_path)
    else:
        cmd.append("tests/")
    
    # Add additional pytest options
    cmd.extend([
        "--tb=short",  # Short traceback format
        "--strict-markers",  # Strict marker checking
        "--disable-warnings",  # Disable warnings for cleaner output
    ])
    
    print("🧪 Running AWS S3 Sync Test Suite")
    print("=" * 50)
    print(f"Command: {' '.join(cmd)}")
    print("=" * 50)
    
    try:
        result = subprocess.run(cmd, check=True)
        print("\n✅ All tests passed!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Tests failed with exit code {e.returncode}")
        return False
    except FileNotFoundError:
        print("❌ pytest not found. Please install pytest: pip install pytest pytest-cov")
        return False

def check_dependencies():
    """Check if required testing dependencies are installed"""
    required_packages = ["pytest", "pytest-cov"]
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ Missing required testing dependencies:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\nInstall with: pip install pytest pytest-cov")
        return False
    
    return True

def main():
    """Main entry point for test runner"""
    parser = argparse.ArgumentParser(
        description="Test Runner for AWS S3 Sync Application",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tests.py                    # Run all tests
  python run_tests.py --verbose         # Run with verbose output
  python run_tests.py --coverage        # Run with coverage report
  python run_tests.py tests/test_sync.py # Run specific test file
  python run_tests.py --html-report     # Generate HTML coverage report
        """
    )
    
    parser.add_argument(
        'test_path',
        nargs='?',
        help='Specific test file or directory to run'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    parser.add_argument(
        '--coverage',
        action='store_true',
        help='Generate coverage report'
    )
    parser.add_argument(
        '--html-report',
        action='store_true',
        help='Generate HTML coverage report (requires --coverage)'
    )
    parser.add_argument(
        '--install-deps',
        action='store_true',
        help='Install testing dependencies'
    )
    
    args = parser.parse_args()
    
    # Handle dependency installation
    if args.install_deps:
        print("📦 Installing testing dependencies...")
        try:
            subprocess.run([
                sys.executable, "-m", "pip", "install", 
                "pytest", "pytest-cov", "pytest-mock"
            ], check=True)
            print("✅ Dependencies installed successfully!")
        except subprocess.CalledProcessError:
            print("❌ Failed to install dependencies")
            return 1
    
    # Check dependencies
    if not check_dependencies():
        return 1
    
    # Validate test path if provided
    if args.test_path:
        test_path = Path(args.test_path)
        if not test_path.exists():
            print(f"❌ Test path not found: {args.test_path}")
            return 1
    
    # Run tests
    success = run_tests(
        test_path=args.test_path,
        verbose=args.verbose,
        coverage=args.coverage,
        html_report=args.html_report
    )
    
    if success:
        print("\n🎉 Test suite completed successfully!")
        if args.coverage:
            print("📊 Coverage report generated")
            if args.html_report:
                print("📄 HTML coverage report available in htmlcov/")
        return 0
    else:
        print("\n💥 Test suite failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 