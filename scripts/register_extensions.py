#!/usr/bin/env python3
"""
Script to register extensions in .bashrc
"""

import subprocess
from pathlib import Path

import yaml


def register_extensions() -> None:
    """Register extensions in .bashrc"""
    home_dir = Path.home()
    bashrc_path = home_dir / ".bashrc"

    # Read extensions configuration
    ext_config_path = Path("ami/config/extensions.yaml")
    if not ext_config_path.exists():
        print("[INFO]  Extensions configuration not found, nothing to register.")
        return

    with open(ext_config_path) as f:
        config_data = yaml.safe_load(f)

    extensions = config_data.get("extensions", [])

    if not extensions:
        print("[INFO]  No extensions found to register.")
        return

    # Process extensions to get their shell setup commands
    new_block_content = ""
    for ext in extensions:
        # Execute the extension command to get the shell setup string
        # This mimics the original bash script behavior
        try:
            # Run the extension command and capture its output
            result = subprocess.run(
                ext,
                shell=True,
                capture_output=True,
                text=True,
                cwd=Path.cwd(),
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                # Add the output as a new line in the bashrc block
                new_block_content += result.stdout.strip() + "\n"
            elif result.stderr.strip():
                print(
                    f"⚠️  Extension command '{ext}' produced error: {result.stderr.strip()}"
                )
        except Exception as e:
            print(f"⚠️  Error executing extension command '{ext}': {e}")

    if not new_block_content.strip():
        print(
            "[INFO]  No extensions found to register or extension commands produced no output."
        )
        return

    # Create the bashrc modification block
    marker_start = "# --- AMI AGENT EXTENSIONS START ---"
    marker_end = "# --- AMI AGENT EXTENSIONS END ---"

    # Read current .bashrc content
    if bashrc_path.exists():
        with open(bashrc_path) as f:
            bashrc_content = f.read()
    else:
        bashrc_content = ""

    # Remove existing block if it exists
    if marker_start in bashrc_content and marker_end in bashrc_content:
        start_idx = bashrc_content.find(marker_start)
        end_idx = bashrc_content.find(marker_end) + len(marker_end)
        bashrc_content = bashrc_content[:start_idx] + bashrc_content[end_idx:]

    # Create new block with extensions
    new_block = f"{marker_start}\n{new_block_content}{marker_end}\n"

    # Append new block to bashrc content
    bashrc_content += "\n" + new_block

    # Write back to .bashrc
    with open(bashrc_path, "w") as f:
        f.write(bashrc_content)

    print("✅ Added/Updated extensions in ~/.bashrc")
    print("🔄 Source ~/.bashrc or restart your shell to apply changes.")


if __name__ == "__main__":
    register_extensions()
