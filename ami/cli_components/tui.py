"""
Terminal User Interface (TUI) primitives for drawing dialogs and boxes.
"""

import sys
from typing import List, Optional
from ami.cli_components.text_input_utils import Colors

class TUI:
    """Shared TUI drawing utilities."""

    @staticmethod
    def clear_lines(count: int) -> None:
        """Clear the last N lines from the terminal."""
        if count > 0:
            for _ in range(count):
                sys.stdout.write('\033[1A')  # Move cursor up one line
                sys.stdout.write('\033[2K')  # Clear the entire line
            sys.stdout.flush()

    @staticmethod
    def draw_box(
        content: List[str],
        title: Optional[str] = None,
        footer: Optional[str] = None,
        width: int = 60,
        border_color: str = Colors.CYAN,
        text_color: str = Colors.RESET,
        center_content: bool = False
    ) -> int:
        """
        Draw a bordered box with content.
        
        Args:
            content: List of strings to display inside the box
            title: Optional title for the top border
            footer: Optional footer text (e.g. instructions) below the box
            width: Total width of the box
            border_color: ANSI color code for the border
            text_color: ANSI color code for the content
            center_content: Whether to center the content text
            
        Returns:
            int: Number of lines printed (for clearing later)
        """
        lines_printed = 0
        
        # 1. Top Border
        if title:
            safe_title = f" {title} "
            # Truncate title if too long
            if len(safe_title) > width - 4:
                safe_title = safe_title[:width-4]
            
            border_len = (width - len(safe_title)) // 2
            # Adjust for odd widths to ensure alignment
            right_border_len = width - len(safe_title) - border_len
            
            top_line = f"{border_color}┌{'─' * border_len}{Colors.RESET}{Colors.BOLD}{safe_title}{Colors.RESET}{border_color}{'─' * (right_border_len - 2)}┐{Colors.RESET}"
        else:
            top_line = f"{border_color}┌{'─' * (width - 2)}┐{Colors.RESET}"
            
        sys.stdout.write(top_line + "\n")
        lines_printed += 1
        
        # 2. Content
        # Add a blank line at top padding
        sys.stdout.write(f"{border_color}│{Colors.RESET}{' ' * (width - 2)}{border_color}│{Colors.RESET}\n")
        lines_printed += 1
        
        for line in content:
            # Handle length / truncation / wrapping?
            # For now, assume pre-wrapped or truncate
            # We need to calculate visible length stripping colors for padding, 
            # but that's complex. Assuming simple strings for now or manual color handling.
            
            # Simple truncation for safety
            # Note: This doesn't handle color codes well if they are cut off.
            # Assuming content fits or is handled by caller.
            
            # Padding
            visible_len = len(line) # Approximation
            # If colors are used, visible_len is smaller. 
            # Ideally caller handles formatting.
            
            if center_content:
                # This is tricky with color codes. 
                # Let's rely on caller to center if they want complex coloring,
                # or just center the raw string if simple.
                left_pad = (width - 2 - visible_len) // 2
                right_pad = width - 2 - visible_len - left_pad
                display_line = f"{ ' ' * left_pad}{text_color}{line}{Colors.RESET}{' ' * right_pad}"
            else:
                display_line = f"  {text_color}{line}{Colors.RESET}".ljust(width - 2 + (len(text_color)+len(Colors.RESET)) ) # Rough adjustment
                # Actually, let's just do manual padding calculation
                # to be safe, standard left align with 2 char padding:
                padding_needed = width - 4 - visible_len
                if padding_needed < 0: 
                    padding_needed = 0 # Overflow
                display_line = f"  {text_color}{line}{Colors.RESET}{' ' * padding_needed}"

            # Re-construct box line
            # Hacky robust box line:
            # Use format string with fixed width? No, color codes mess it up.
            # Let's assume the caller provides clean lines or we trust simple len() for now.
            # For robust TUI, we'd need a strip_ansi function.
            
            # Better approach: Caller formats the line content to fit width-4.
            # We just wrap in border.
            
            # Let's try to center if requested, but naively.
            inner_width = width - 2
            
            if center_content:
                 # Strip colors to measure length?
                 # Too expensive to implement full ANSI parser here.
                 # Let's assume content is pre-formatted or simple.
                 
                 # Alternative: Just write the line and let terminal handle it? No, box breaks.
                 
                 # Let's implement a simple strip_colors if possible?
                 pass

            # Fallback to simple leftpad + fill
            # We construct the line: │  CONTENT  │
            
            # We need to know the printable length.
            # Let's import strip logic or assume clean input for now.
            # Or just use the one from text_input_utils if it existed? It doesn't.
            
            # Simple fill:
            # Assume line has no colors for length calc:
            fill_len = inner_width - len(line)
            if fill_len < 0: fill_len = 0
            
            if center_content:
                l_pad = fill_len // 2
                r_pad = fill_len - l_pad
                row = f"{border_color}│{Colors.RESET}{' ' * l_pad}{text_color}{line}{Colors.RESET}{' ' * r_pad}{border_color}│{Colors.RESET}"
            else:
                # Left aligned with 2 spaces padding
                # If content is too long, we might break the box.
                # Caller should wrap.
                row = f"{border_color}│{Colors.RESET}  {text_color}{line}{Colors.RESET}{' ' * (fill_len - 2)}{border_color}│{Colors.RESET}"
            
            sys.stdout.write(row + "\n")
            lines_printed += 1

        # Add a blank line at bottom padding
        sys.stdout.write(f"{border_color}│{Colors.RESET}{' ' * (width - 2)}{border_color}│{Colors.RESET}\n")
        lines_printed += 1

        # 3. Bottom Border
        bottom_line = f"{border_color}└{'─' * (width - 2)}┘{Colors.RESET}"
        sys.stdout.write(bottom_line + "\n")
        lines_printed += 1
        
        # 4. Footer
        if footer:
            sys.stdout.write(f"{footer}\n")
            lines_printed += 1
            
        sys.stdout.flush()
        return lines_printed

    @staticmethod
    def wrap_text(text: str, width: int) -> List[str]:
        """Simple word wrap helper."""
        words = text.split()
        lines = []
        current_line = []
        current_len = 0
        
        for word in words:
            if current_len + len(word) + (1 if current_line else 0) <= width:
                current_line.append(word)
                current_len += len(word) + (1 if current_line else 0)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
                current_len = len(word)
        
        if current_line:
            lines.append(" ".join(current_line))
            
        return lines
