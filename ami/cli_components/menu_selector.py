"""
Reusable menu selector with arrow key navigation and scrolling support.
Proxies to ami.cli_components.dialogs.SelectionDialog.
"""

from typing import Generic, TypeVar, cast

from ami.cli_components.dialogs import SelectionDialog, SelectionDialogConfig
from ami.cli_components.selection_dialog import DialogItem

T = TypeVar("T")


class MenuItem(Generic[T]):
    """Represents a single menu item that implements SelectableItem protocol.

    Uses **kwargs to stay under 5 positional args limit while supporting protocol.
    """

    __slots__ = ("description", "disabled", "id", "is_header", "label", "value")

    def __init__(
        self, id: str, label: str, value: T | None = None, **kwargs: object
    ) -> None:
        self.id = id
        self.label = label
        self.value: T | str = value if value is not None else id
        self.description: str = str(kwargs.get("description", ""))
        self.is_header: bool = bool(kwargs.get("is_header", False))
        self.disabled: bool = bool(kwargs.get("disabled", False))


class MenuSelector(Generic[T]):
    """A reusable menu selector with arrow key navigation and scrolling."""

    def __init__(
        self,
        items: list[MenuItem[T]],
        title: str = "Menu",
        allow_multiple: bool = False,
        max_visible_items: int = 10,
    ):
        self._items = items
        config = SelectionDialogConfig(
            title=title,
            width=80,
            multi=allow_multiple,
            max_height=max_visible_items,
        )
        # MenuItem implements SelectableItem protocol structurally
        dialog_items = cast(list[DialogItem], items)
        self.dialog: SelectionDialog = SelectionDialog(dialog_items, config)

    def run(self) -> list[MenuItem[T]] | None:
        """Run the menu selector and return selected items."""
        result = self.dialog.run()
        if result is None:
            return None
        # Result items are the same MenuItem instances we passed in
        if isinstance(result, list):
            return cast(list[MenuItem[T]], result)
        return cast(list[MenuItem[T]], [result])


def simple_menu_select(items: list[str], title: str = "Select an option") -> str | None:
    """Simple menu selector that works with a list of strings."""
    menu_items = [MenuItem[str](str(i), item, item) for i, item in enumerate(items)]
    menu: MenuSelector[str] = MenuSelector(menu_items, title, allow_multiple=False)
    result = menu.run()
    if result and len(result) > 0:
        value = result[0].value
        return str(value) if value is not None else None
    return None


def multi_menu_select(
    items: list[str], title: str = "Select options"
) -> list[str] | None:
    """Multiple selection menu selector that works with a list of strings."""
    menu_items = [MenuItem[str](str(i), item, item) for i, item in enumerate(items)]
    menu: MenuSelector[str] = MenuSelector(menu_items, title, allow_multiple=True)
    result = menu.run()
    if result:
        return [str(item.value) for item in result if item.value is not None]
    return None
