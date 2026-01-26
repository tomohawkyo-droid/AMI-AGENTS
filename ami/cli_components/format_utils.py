"""
Formatting utilities for CLI display.
"""

# Size constants for human-readable formatting
KB = 1024
MB = KB * 1024
GB = MB * 1024


def format_file_size(size_str: str | int) -> str:
    """
    Format file size in a human-readable way.

    Args:
        size_str: Size as string or integer

    Returns:
        Human-readable size string (e.g., "1.5GB", "500MB")
    """
    if size_str == "Unknown":
        return "Unknown"

    try:
        size_bytes = int(size_str)
        if size_bytes > GB:
            size_str = f"{size_bytes / GB:.1f}GB"
        elif size_bytes > MB:
            size_str = f"{size_bytes / MB:.1f}MB"
        elif size_bytes > KB:
            size_str = f"{size_bytes / KB:.1f}KB"
        else:
            size_str = f"{size_bytes}B"
    except (ValueError, TypeError):
        # If size cannot be converted to int, return as is (converted to string)
        return str(size_str)

    return size_str
