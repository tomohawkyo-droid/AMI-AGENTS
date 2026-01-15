"""Editor saving utilities."""

def save_content(lines: list[str], _cursor_line: int) -> str:
    """Save content from editor lines.
    
    Args:
        lines: List of strings representing lines.
        _cursor_line: Unused cursor line argument (kept for compatibility).
        
    Returns:
        Joined content string.
    """
    return "\n".join(lines)

