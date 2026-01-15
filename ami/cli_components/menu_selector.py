"""
Reusable menu selector with arrow key navigation and scrolling support.
Proxies to agents.ami.cli_components.dialogs.SelectionDialog.
"""

from typing import List, Optional, Any
from agents.ami.cli_components.dialogs import SelectionDialog

class MenuItem:
    """Represents a single menu item."""
    
    def __init__(self, id: str, label: str, value: Any = None, description: str = ""):
        self.id = id
        self.label = label
        self.value = value if value is not None else id
        self.description = description


class MenuSelector:
    """A reusable menu selector with arrow key navigation and scrolling."""
    
    def __init__(
        self,
        items: List[MenuItem],
        title: str = "Menu",
        allow_multiple: bool = False,
        max_visible_items: int = 10
    ):
        self.dialog = SelectionDialog(items, title, width=80, multi=allow_multiple)
        # SelectionDialog hardcodes max_height to 10 currently, but we could make it configurable
        self.dialog.max_height = max_visible_items
    
    def run(self) -> Optional[List[MenuItem]]:
        """Run the menu selector and return selected items."""
        result = self.dialog.run()
        if result is None:
            return None
        if isinstance(result, list):
            return result
        return [result]


def simple_menu_select(items: List[str], title: str = "Select an option") -> Optional[str]:
    """Simple menu selector that works with a list of strings."""
    menu_items = [MenuItem(str(i), item, item) for i, item in enumerate(items)]
    menu = MenuSelector(menu_items, title, allow_multiple=False)
    result = menu.run()
    return result[0].value if result else None


def multi_menu_select(items: List[str], title: str = "Select options") -> Optional[List[str]]:
    """Multiple selection menu selector that works with a list of strings."""
    menu_items = [MenuItem(str(i), item, item) for i, item in enumerate(items)]
    menu = MenuSelector(menu_items, title, allow_multiple=True)
    result = menu.run()
    return [item.value for item in result] if result else None


if __name__ == "__main__":
    # Demo
    items = [
        MenuItem("1", "Option A", "A", "Description A"),
        MenuItem("2", "Option B", "B", "Description B"),
    ]
    print(f"Selected: {simple_menu_select([i.label for i in items], 'Simple Select')}")