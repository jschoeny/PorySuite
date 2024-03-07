from PySide6.QtWidgets import QTreeWidget


class DeselectableTreeWidget(QTreeWidget):
    """
    A QTreeWidget that deselects all items when the user clicks on an empty area.
    """

    def mousePressEvent(self, event):
        """
        Deselect all items if the user clicks on an empty area.
        """
        if not self.itemAt(event.pos()):
            self.clearSelection()
        super().mousePressEvent(event)