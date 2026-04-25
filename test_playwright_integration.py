#!/usr/bin/env python3
"""
Test script to verify Playwright integration with AMI security protocols.
"""

import subprocess
import sys
from pathlib import Path


def check_ami_browser_exists() -> bool:
    """Check if ami-browser command exists and is accessible."""
    print("\n1. Checking if ami-browser command is available...")
    try:
        result = subprocess.run(
            ["which", "ami-browser"], capture_output=True, text=True, check=True
        )
        print(f"   ✓ ami-browser found at: {result.stdout.strip()}")
    except subprocess.CalledProcessError:
        print("   ✗ ami-browser command not found")
        return False
    else:
        return True


def check_playwright_version() -> bool:
    """Check Playwright version."""
    print("\n2. Checking Playwright version...")
    try:
        result = subprocess.run(
            ["ami-browser", "--version"], capture_output=True, text=True, check=True
        )
        print(f"   ✓ Playwright version: {result.stdout.strip()}")
    except subprocess.CalledProcessError as e:
        print(f"   ✗ Failed to get Playwright version: {e}")
        return False
    else:
        return True


def check_playwright_commands() -> bool:
    """Check available Playwright commands."""
    print("\n3. Checking available Playwright commands...")
    try:
        result = subprocess.run(
            ["ami-browser", "help"], capture_output=True, text=True, check=True
        )
        help_text = result.stdout
        commands = ["open", "codegen", "install", "screenshot", "pdf", "show-trace"]
        found_commands = [
            cmd
            for cmd in commands
            if f"  {cmd} " in help_text or f"\n{cmd} " in help_text
        ]
        print(f"   ✓ Found commands: {', '.join(found_commands)}")
    except subprocess.CalledProcessError as e:
        print(f"   ✗ Failed to get help text: {e}")
        return False
    else:
        return True


def check_browser_scripts(root: Path) -> bool:
    """Check if browser scripts exist."""
    print("\n4. Checking browser scripts...")
    browser_scripts_dir = root / "ami" / "scripts" / "browser"
    scripts = ["dom-query.js", "screenshot.js", "console.js"]

    for script in scripts:
        script_path = browser_scripts_dir / script
        if script_path.exists():
            print(f"   ✓ {script} exists")
        else:
            print(f"   ✗ {script} not found at {script_path}")
            return False
    return True


def check_extensions_config(root: Path) -> bool:
    """Verify ami-browser is registered via the manifest registry."""
    print("\n5. Checking extensions manifest...")
    manifest = (
        root / "ami" / "scripts" / "bin" / "enterprise" / "extension.manifest.yaml"
    )
    if not manifest.exists():
        print(f"   ✗ Manifest not found at {manifest}")
        return False
    content = manifest.read_text()
    if "ami-browser" in content and "Browser automation (Playwright)" in content:
        print("   ✓ ami-browser properly configured in enterprise manifest")
        return True
    print("   ✗ ami-browser not registered in enterprise manifest")
    return False


def test_playwright_integration():
    """
    Test that Playwright integration works properly with AMI security protocols.
    """
    print("Testing Playwright Integration with AMI Security Protocols")
    print("=" * 60)
    root = Path(__file__).parent

    if not check_ami_browser_exists():
        return False
    if not check_playwright_version():
        return False
    if not check_playwright_commands():
        return False
    if not check_browser_scripts(root):
        return False
    if not check_extensions_config(root):
        return False

    print("\n" + "=" * 60)
    print("✓ All tests passed! Playwright integration is properly set up.")
    return True


if __name__ == "__main__":
    success = test_playwright_integration()
    sys.exit(0 if success else 1)
