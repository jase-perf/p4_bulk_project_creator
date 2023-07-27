import sys
import csv

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTabWidget,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QPushButton,
    QFileDialog,
    QLabel,
)


class SharedData:
    def __init__(self):
        self.table_data = []
        self.template_data = {}


class LoadCsvWindow(QWidget):
    def __init__(self, shared_data, parent=None):
        super().__init__(parent=parent)
        self.shared_data = shared_data
        # Set up the main Vertical Layout
        main_layout = QVBoxLayout()

        # Add a button to load the CSV file
        load_layout = QHBoxLayout()
        self.load_button = QPushButton("Load CSV file...")
        self.load_button.clicked.connect(self.load_csv_file)
        load_layout.addWidget(self.load_button)
        main_layout.addLayout(load_layout)

        # Set up the table for viewing CSV data
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Name", "E-mail", "Group"])
        main_layout.addWidget(self.table)

        # Set up the button box at the bottom of the window
        button_layout = QHBoxLayout()
        self.next_button = QPushButton("Choose Template")
        self.next_button.clicked.connect(self.go_to_setup)
        if self.table.rowCount() == 0:
            self.next_button.setEnabled(False)
        button_layout.addWidget(self.next_button)
        main_layout.addLayout(button_layout)

        # Set the main layout of the window
        self.setLayout(main_layout)

    def load_csv_file(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Open CSV", "", "CSV Files (*.csv)"
        )
        if filename:
            self.load_csv_data(filename)

    def load_csv_data(self, filename):
        with open(filename) as csv_file:
            reader = csv.reader(csv_file, delimiter=",", quotechar='"')
            self.table.setRowCount(0)
            for row_number, row_data in enumerate(reader):
                print(f"Processing row {row_number}", end=" ")
                self.table.insertRow(row_number)
                for column_number, data in enumerate(row_data):
                    print(f"Row data: {data}", end=" ")
                    self.table.setItem(
                        row_number, column_number, QTableWidgetItem(data)
                    )

            # Resize the columns to fit the data
            self.table.resizeColumnsToContents()
            if self.table.columnCount() > 0:
                self.next_button.setEnabled(True)

    def go_to_setup(self):
        self.shared_data.table_data = []
        for row in range(self.table.rowCount()):
            row_data = []
            for column in range(self.table.columnCount()):
                cell = self.table.item(row, column)
                row_data.append(cell.text())
            self.shared_data.table_data.append(row_data)

        self.parent().push(TemplateSetupWindow(self.shared_data))


class TemplateSetupWindow(QWidget):
    # Create simple hello world label
    def __init__(self, shared_data, parent=None):
        super().__init__(parent=parent)
        self.shared_data = shared_data

        print("Table Data:")
        print("\n".join([str(row) for row in self.shared_data.table_data]))

        # Set up the main Vertical Layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(QLabel("Hello Template Setup!"))
        main_layout.addWidget(QLabel(f"{self.shared_data.table_data}"))

        # Set up the button box at the bottom of the window
        button_layout = QHBoxLayout()
        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(lambda: self.parent().pop())
        button_layout.addWidget(self.back_button)
        self.next_button = QPushButton("Summarize")
        self.next_button.clicked.connect(self.go_to_preview)
        if not self.shared_data.template_data:
            self.next_button.setEnabled(False)
        button_layout.addWidget(self.next_button)
        main_layout.addLayout(button_layout)

        # Set the main layout of the window
        self.setLayout(main_layout)

    def go_to_preview(self):
        self.parent().push(PreviewWindow(self.shared_data))


class PreviewWindow(QWidget):
    def __init__(self, shared_data, parent=None):
        super().__init__(parent=parent)
        self.shared_data = shared_data

        print("Template Data:")
        print(self.shared_data.template_data)

        # Set up the main Vertical Layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(QLabel("Hello Summary!"))
        main_layout.addWidget(QLabel(f"{self.shared_data.table_data}"))
        main_layout.addWidget(QLabel(f"{self.shared_data.template_data}"))

        # Set up the button box at the bottom of the window
        button_layout = QHBoxLayout()
        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(lambda: self.parent().pop())
        button_layout.addWidget(self.back_button)
        self.next_button = QPushButton("Create All")
        self.next_button.clicked.connect(self.go_to_creation)
        button_layout.addWidget(self.next_button)
        main_layout.addLayout(button_layout)

        # Set the main layout of the window
        self.setLayout(main_layout)

    def go_to_creation(self):
        self.parent().push(CreationWindow(self.shared_data))


class CreationWindow(QWidget):
    def __init__(self, shared_data, parent=None):
        super().__init__(parent=parent)
        self.shared_data = shared_data

        # Set up the main Vertical Layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(QLabel("Hello Creation!"))
        main_layout.addWidget(QLabel(f"{self.shared_data.table_data}"))
        main_layout.addWidget(QLabel(f"{self.shared_data.template_data}"))

        # Set up the button box at the bottom of the window
        button_layout = QHBoxLayout()
        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(lambda: self.parent().pop())
        button_layout.addWidget(self.back_button)
        self.next_button = QPushButton("Close")
        self.next_button.clicked.connect(QApplication.instance().quit)
        button_layout.addWidget(self.next_button)
        main_layout.addLayout(button_layout)

        # Set the main layout of the window
        self.setLayout(main_layout)


class StackedWidget(QStackedWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.widget_stack = []

    def push(self, widget):
        self.widget_stack.append(widget)
        self.addWidget(widget)
        self.setCurrentWidget(widget)

    def pop(self):
        if self.widget_stack:
            widget_to_remove = self.widget_stack.pop()
            self.removeWidget(widget_to_remove)
        if self.widget_stack:
            self.setCurrentWidget(self.widget_stack[-1])


class MainWindow(QMainWindow):
    def __init__(self, shared_data, parent=None):
        super().__init__(parent=parent)
        self.shared_data = shared_data
        self.setWindowTitle("Create Projects from CSV")
        self.resize(1200, 800)
        self.stacked_widget = StackedWidget()
        self.setCentralWidget(self.stacked_widget)

        # Start with just our first widget
        self.stacked_widget.push(LoadCsvWindow(shared_data))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    shared_data = SharedData()
    window = MainWindow(shared_data)
    window.show()
    sys.exit(app.exec())
