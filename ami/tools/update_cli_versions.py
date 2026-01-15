#!/usr/bin/env python3
"""Update CLI versions in package.json to latest available versions.

This script queries npm for the latest available versions of the CLI tools
and updates the scripts/package.json file accordingly.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional

from agents.ami.cli_components.confirmation_dialog import confirm


def get_latest_npm_version(package_name: str) -> Optional[str]:
    """Get the latest version of a package from npm registry.
    
    Args:
        package_name: Name of the npm package to check
        
    Returns:
        Latest version string or None if error
    """
    try:
        # Use the npm from our bootstrapped environment
        boot_npm = Path.cwd() / ".boot-linux" / "node-env" / "bin" / "npm"
        npm_cmd = str(boot_npm) if boot_npm.exists() else "npm"
        
        # Query npm for the latest version
        result = subprocess.run(
            [npm_cmd, "view", package_name, "version", "--json"], 
            capture_output=True, 
            text=True, 
            check=True
        )
        version = result.stdout.strip()
        # Handle case where npm view returns raw version string instead of JSON
        if version.startswith('"') and version.endswith('"'):
            version = json.loads(version)
        return version
    except subprocess.CalledProcessError as e:
        print(f"Error getting version for {package_name}: {e}")
        print(f"stdout: {e.stdout}, stderr: {e.stderr}")
        return None
    except Exception as e:
        print(f"Unexpected error getting version for {package_name}: {e}")
        return None


def get_current_versions(package_json_path: Path) -> Dict[str, str]:
    """Get current versions from package.json.
    
    Args:
        package_json_path: Path to the package.json file
        
    Returns:
        Dictionary mapping package names to current versions
    """
    with open(package_json_path, 'r') as f:
        data = json.load(f)
    
    dependencies = data.get('dependencies', {})
    cli_packages = {
        '@anthropic-ai/claude-code': dependencies.get('@anthropic-ai/claude-code'),
        '@google/gemini-cli': dependencies.get('@google/gemini-cli'),
        '@qwen-code/qwen-code': dependencies.get('@qwen-code/qwen-code'),
    }
    
    # Filter out packages that aren't present
    return {k: v for k, v in cli_packages.items() if v is not None}


def update_package_json(package_json_path: Path, updates: Dict[str, str]) -> bool:
    """Update package.json with new versions.
    
    Args:
        package_json_path: Path to the package.json file
        updates: Dictionary mapping package names to new versions
        
    Returns:
        True if update was successful, False otherwise
    """
    # Backup original file
    backup_path = package_json_path.with_suffix(package_json_path.suffix + '.backup')
    with open(package_json_path, 'r') as f:
        original_content = f.read()
    
    with open(backup_path, 'w') as f:
        f.write(original_content)
    
    print(f"Backup created at: {backup_path}")
    
    try:
        with open(package_json_path, 'r') as f:
            data = json.load(f)
        
        dependencies = data.get('dependencies', {})
        
        # Update versions
        updated = False
        for package, new_version in updates.items():
            current_version = dependencies.get(package)
            if current_version and current_version != new_version:
                dependencies[package] = new_version
                print(f"Updated {package}: {current_version} -> {new_version}")
                updated = True
            elif current_version == new_version:
                print(f"{package}: already at latest version {new_version}")
            else:
                print(f"{package}: not found in dependencies")
        
        if updated:
            # Write updated content
            with open(package_json_path, 'w') as f:
                json.dump(data, f, indent=2)
                f.write('\n')  # Add final newline
            print(f"Updated {package_json_path}")
            return True
        else:
            print("No updates needed")
            # Remove backup if no changes were made
            backup_path.unlink()
            return True
            
    except Exception as e:
        print(f"Error updating {package_json_path}: {e}")
        # Restore from backup
        if backup_path.exists():
            with open(backup_path, 'r') as f:
                original_content = f.read()
            with open(package_json_path, 'w') as f:
                f.write(original_content)
            print(f"Restored from backup: {backup_path}")
        return False


def main() -> int:
    """Main function to update CLI versions."""
    # Find the package.json file
    package_json_path = Path(__file__).parent / "package.json"

    if not package_json_path.exists():
        print(f"Error: package.json not found at {package_json_path}")
        return 1

    print(f"Checking CLI versions in {package_json_path}")

    # Get current versions
    current_versions = get_current_versions(package_json_path)
    print(f"Current versions: {current_versions}")

    # Get latest versions from npm
    latest_versions = {}
    updates_needed = {}

    for package in current_versions.keys():
        print(f"Checking latest version for {package}...")
        latest_version = get_latest_npm_version(package)
        if latest_version:
            latest_versions[package] = latest_version
            current = current_versions[package]
            # Remove ^ or ~ prefix for comparison
            current_clean = current.lstrip('^~')
            latest_clean = latest_version.lstrip('^~')

            if current_clean != latest_clean:
                updates_needed[package] = latest_version
            else:
                print(f"{package}: already at latest available version")
        else:
            print(f"Could not fetch latest version for {package}")

    print(f"Latest versions: {latest_versions}")

    if updates_needed:
        print(f"Updates needed: {updates_needed}")

        # Only update if --auto-update is provided (analysis by default)
        if '--auto-update' in sys.argv:
            # Ask for confirmation unless --force is provided
            if '--force' not in sys.argv:
                if not confirm(f"Update package.json with these versions?\n{updates_needed}", "Confirm Update"):
                    print("Update cancelled")
                    return 0

            # Update package.json
            success = update_package_json(package_json_path, updates_needed)
            if success:
                print("Successfully updated package.json")
                print("Run 'make setup-all' to install the new versions in your environment.")
                return 0
            else:
                print("Failed to update package.json")
                return 1
        else:
            print("\nAnalysis complete. No changes made.")
            print("To apply these updates, run with --auto-update flag:")
            print(f"  ami-run {__file__} --auto-update")
            return 0
    else:
        print("All packages are already at latest versions")
        return 0


if __name__ == "__main__":
    sys.exit(main())