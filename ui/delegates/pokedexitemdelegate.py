from PySide6.QtWidgets import QStyledItemDelegate


class PokedexItemDelegate(QStyledItemDelegate):
    """
    A delegate class for customizing the appearance of items in a Pokédex list.

    This class extends the QStyledItemDelegate class and provides a custom implementation
    of the initStyleOption method to modify the style options for Pokédex items.

    Example usage:
        delegate = PokedexItemDelegate()
        view.setItemDelegate(delegate)
    """

    def initStyleOption(self, option, index):
        """
        Initializes the style option for the given index.

        Args:
            option (QStyleOptionViewItem): The style option to initialize.
            index (QModelIndex): The model index.
        """
        super().initStyleOption(option, index)
        if index.parent().row() == -1:
            option.text = f"#{str(index.row() + 1).zfill(3)} |  {option.text}"
