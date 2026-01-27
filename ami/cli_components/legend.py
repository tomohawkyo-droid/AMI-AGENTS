"""Reusable TUI legend component for displaying icon/label pairs."""

import re
import unicodedata

C_DIM = "\033[2m"
C_RESET = "\033[0m"

# Emoji that render as 2 cells in terminal
WIDE_EMOJI = frozenset(
    [
        "🟢",
        "🟡",
        "🔴",
        "⚪",
        "🐳",
        "🐋",
        "🚀",
        "💤",
        "♻️",
        "♻",
        "🩹",
        "🚫",
        "⚡",
        "🐏",
        "💿",
        "📁",
        "⚙️",
        "⚙",
        "📚",
        "🌐",
        "🗄️",
        "📧",
        "📦",
        "🔐",
        "🔍",
        "⚠️",
        "⚠",
    ]
)


def get_visual_width(text: str) -> int:
    """Calculate the visual width of a string in terminal cells."""
    # Strip ANSI escape codes
    clean_text = re.sub(r"\033\[[0-9;]*m", "", text)

    width = 0
    i = 0
    while i < len(clean_text):
        char = clean_text[i]

        # Check for emoji with variation selector (2 chars)
        if i + 1 < len(clean_text):
            two_char = clean_text[i : i + 2]
            if two_char in WIDE_EMOJI:
                width += 2
                i += 2
                continue

        # Check single char emoji
        if char in WIDE_EMOJI:
            width += 2
            i += 1
            continue

        # East Asian wide/fullwidth characters
        if unicodedata.east_asian_width(char) in ("W", "F"):
            width += 2
        else:
            width += 1
        i += 1

    return width


def pad_center(text: str, target_width: int) -> str:
    """Center text accounting for visual width of emoji."""
    current_width = get_visual_width(text)
    if current_width >= target_width:
        return text
    pad_total = target_width - current_width
    pad_left = pad_total // 2
    pad_right = pad_total - pad_left
    return " " * pad_left + text + " " * pad_right


class LegendItem:
    """Single legend item with icon and label."""

    __slots__ = ("icon", "label")

    def __init__(self, icon: str, label: str):
        self.icon = icon
        self.label = label


class Legend:
    """Renders a centered legend with icons and labels on separate rows.

    Usage:
        legend = Legend([
            [LegendItem("🟢", "ok"), LegendItem("🔴", "fail")],
            [LegendItem("🚀", "boot"), LegendItem("💤", "manual")],
        ])
        icons_line, labels_line = legend.render(width=80)
        print(icons_line)
        print(labels_line)
    """

    def __init__(
        self,
        groups: list[list[LegendItem]],
        separator: str = "│",
        dim: bool = True,
    ):
        """Initialize legend.

        Args:
            groups: List of groups, each group is a list of LegendItems.
            separator: Character to separate groups.
            dim: Whether to apply dim styling.
        """
        self.groups = groups
        self.separator = separator
        self.dim = dim

    def render(self, width: int) -> tuple[str, str]:
        """Render legend as two lines: icons and labels, centered.

        Args:
            width: Total width to center within.

        Returns:
            Tuple of (icons_line, labels_line).
        """
        icon_parts: list[str] = []
        label_parts: list[str] = []

        for group in self.groups:
            # Build icons and labels for this group
            icons: list[str] = []
            labels: list[str] = []

            for item in group:
                icon_width = get_visual_width(item.icon)
                label_width = len(item.label)
                col_width = max(icon_width, label_width)

                # Pad icon and label to same visual width
                icons.append(pad_center(item.icon, col_width))
                labels.append(pad_center(item.label, col_width))

            group_icons = " ".join(icons)
            group_labels = " ".join(labels)

            # Ensure group icons and labels have same visual width
            icons_width = get_visual_width(group_icons)
            labels_width = get_visual_width(group_labels)
            group_width = max(icons_width, labels_width)

            icon_parts.append(pad_center(group_icons, group_width))
            label_parts.append(pad_center(group_labels, group_width))

        sep = f" {self.separator} "
        icons_line = sep.join(icon_parts)
        labels_line = sep.join(label_parts)

        # Center both lines within the given width
        content_width = width - 4  # Account for box borders

        icons_centered = pad_center(icons_line, content_width)
        labels_centered = pad_center(labels_line, content_width)

        if self.dim:
            return (
                f"{C_DIM}{icons_centered}{C_RESET}",
                f"{C_DIM}{labels_centered}{C_RESET}",
            )
        return icons_centered, labels_centered
