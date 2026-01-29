#!/usr/bin/env python3
"""System information display with progress bars."""

import sys

import psutil

from ami.types.results import ColorPair

# ANSI Color IDs for gradient logic (Standard 256-color palette)
COLOR_IDS = {
    "green": (34, 22),  # Mid Green, Deep Green
    "lime": (112, 28),  # Mid Lime, Dark Forest
    "yellow": (178, 94),  # Gold, Dark Orange/Brown
    "orange": (166, 52),  # Deep Orange, Dark Red/Brown
    "red": (124, 16),  # Deep Red, Near Black
}

RESET = "\033[0m"
BOLD = "\033[1m"
WHITE_FG = "\033[38;5;231m"

# Progress bar color thresholds (percentage)
THRESHOLD_GREEN = 40
THRESHOLD_YELLOW = 60
THRESHOLD_ORANGE = 80

# Size conversion constants
BYTES_PER_UNIT = 1024.0


class ProgressBar:
    def __init__(self, width: int, filled_char: str = "█"):
        self.width = width
        self.filled_char = filled_char

    def get_color_pair(self, percent: float) -> ColorPair:
        if percent < THRESHOLD_GREEN:
            return ColorPair(*COLOR_IDS["green"])
        elif percent < THRESHOLD_YELLOW:
            return ColorPair(*COLOR_IDS["yellow"])
        elif percent < THRESHOLD_ORANGE:
            return ColorPair(*COLOR_IDS["orange"])
        else:
            return ColorPair(*COLOR_IDS["red"])

    def render(
        self, percent: float, label: str, value: str, label_width: int = 20
    ) -> str:
        """
        Renders a fixed-width progress bar.
        Structure: Label(20) + Bar(Dynamic) + Space(1) + Value(Variable)
        Target Longest Row: 77 characters (to match banner delimiters)
        """
        percent = max(0.0, min(100.0, percent))
        filled_len = int(self.width * percent / 100)
        main_id, dim_id = self.get_color_pair(percent)

        pct_str = f" {percent:.1f}% "
        pct_len = len(pct_str)

        if self.width > pct_len:
            text_start = (self.width - pct_len) // 2
            text_end = text_start + pct_len
        else:
            text_start = text_end = 0

        bar_content = ""
        for i in range(self.width):
            is_filled = i < filled_len
            color_id = main_id if is_filled else dim_id

            if text_start <= i < text_end:
                char = pct_str[i - text_start]
                bg_code = f"\033[48;5;{color_id}m"
                bar_content += f"{bg_code}{WHITE_FG}{BOLD}{char}"
            else:
                fg_code = f"\033[38;5;{color_id}m"
                bar_content += f"{RESET}{fg_code}{self.filled_char}"

        # Label(20) + Bar + Space(1) + Value
        return f"{label:<{label_width}}{bar_content}{RESET} {value}"


def get_size_str(bytes_val: int) -> str:
    value = float(bytes_val)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if value < BYTES_PER_UNIT:
            return f"{value:.1f}{unit}"
        value /= BYTES_PER_UNIT
    return f"{value:.1f}PB"


def main() -> None:
    try:

        class _Item:
            __slots__ = ("label", "percent", "value")

            def __init__(self, label: str, percent: float, value: str) -> None:
                self.label = label
                self.percent = percent
                self.value = value

        items: list[_Item] = []
        # Data collection
        disk = psutil.disk_usage(".")
        items.append(
            _Item(
                label="  > Storage (Root)",
                percent=disk.percent,
                value=f"{get_size_str(disk.used)} / {get_size_str(disk.total)}",
            )
        )

        mem = psutil.virtual_memory()
        items.append(
            _Item(
                label="  > Memory (RAM)",
                percent=mem.percent,
                value=f"{get_size_str(mem.used)} / {get_size_str(mem.total)}",
            )
        )

        cpu_pct = psutil.cpu_percent(interval=0.1)
        items.append(
            _Item(
                label="  > CPU Usage",
                percent=cpu_pct,
                value=f"{psutil.cpu_count()} Cores",
            )
        )

        # Layout Calculation (Standardize to 80 chars)
        BANNER_WIDTH = 80
        LABEL_WIDTH = 20
        SPACING = 1

        max_val_len = max(len(item.value) for item in items)

        # BarWidth = 80 - 20 - 1 - max_val_len
        common_bar_width = BANNER_WIDTH - LABEL_WIDTH - SPACING - max_val_len

        common_bar_width = max(common_bar_width, 10)

        bar_renderer = ProgressBar(width=common_bar_width)
        print(f"{BOLD}\033[38;5;33m📊 System Status:{RESET}\n")
        for item in items:
            print(
                bar_renderer.render(item.percent, item.label, item.value, LABEL_WIDTH)
            )
        print()

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
