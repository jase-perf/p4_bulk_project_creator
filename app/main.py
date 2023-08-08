import sys
import csv
import re

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QPushButton,
    QFileDialog,
    QLabel,
    QComboBox,
    QMessageBox,
)
from PyQt6.QtCore import Qt

import p4_utils

# TODO: Remove this and run the whole thing from inside P4V or an environment with these set.
p4_utils.init(username="jadmin", port="ssl:p4.argonautcreations.com:1666")

# r"[^@]+\.[^@]+" will match any standard 2-part domain name for email.
# EMAIL_DOMAIN can be customized to require a specific domain like, "myuniversity.edu"
EMAIL_DOMAIN = r"[^@]+\.[^@]+"
CSV_FIELDS = [
    {"label": "Name", "validation": lambda s: s or None},
    {
        "label": "E-mail",
        "validation": lambda s: s
        if bool(re.match(rf"[^@]+@{EMAIL_DOMAIN}", s))
        else None,
    },
    {
        "label": "Group",
        "validation": lambda s: s
        if bool(
            re.match(r"^(?!-)[\w]+$", s, re.UNICODE)
            and not s.isnumeric()
            and all(c not in "/,.*%" for c in s)
        )
        else None,
    },
    {
        "label": "Owner",
        "validation": lambda s: bool(s and s.lower() not in ["false", "no", "f", "n"]),
    },
]


class CSV_VALIDATION_ERROR(Exception):
    pass


def validate_csv_row(i: int, row: list) -> list:
    formatted_row = []
    for column, data in enumerate(row):
        print(
            f"Checking [{i},{column}] {data} against {CSV_FIELDS[column]['label']} validation function..."
        )
        formatted_data = CSV_FIELDS[column]["validation"](data.strip())
        if formatted_data is None:
            raise CSV_VALIDATION_ERROR(
                f"Validation failed in csv data for row {i}: \n{row} \nValue: '{data}' failed validation for field type '{CSV_FIELDS[column]['label']}'."
            )
        formatted_row.append(formatted_data)
    return formatted_row


class SharedData:
    def __init__(self):
        self.table_data = []
        self.template_depot = None


class LoadCsvWindow(QWidget):
    def __init__(self, shared_data, parent=None):
        super().__init__(parent=parent)
        self.shared_data = shared_data
        # Set up the main Vertical Layout
        main_layout = QVBoxLayout()

        csv_label = QLabel(
            "CSV file must match fields in the table below and pass validation."
        )
        main_layout.addWidget(csv_label)
        # Add a button to load the CSV file
        load_layout = QHBoxLayout()
        self.load_button = QPushButton("Load CSV file...")
        self.load_button.clicked.connect(self.load_csv_file)
        load_layout.addWidget(self.load_button)
        main_layout.addLayout(load_layout)

        # Set up the table for viewing CSV data
        self.table = QTableWidget()
        self.table.setColumnCount(len(CSV_FIELDS))
        self.table.setHorizontalHeaderLabels([field["label"] for field in CSV_FIELDS])
        main_layout.addWidget(self.table)

        # Select the template Depot:
        main_layout.addWidget(
            QLabel("Select template depot to use for all new depots:")
        )
        main_layout.addWidget(
            QLabel(
                '(Template depots must include "template" in the name to show up here.)'
            )
        )
        self.template_combo = QComboBox(self)
        self.template_depots = p4_utils.get_template_depots()
        self.shared_data.template_depot = (
            self.template_depots[0] if self.template_depots else None
        )
        self.template_combo.addItems([depot["name"] for depot in self.template_depots])
        self.template_combo.currentIndexChanged.connect(self.set_template_depot)
        main_layout.addWidget(self.template_combo)

        # Set up the button box at the bottom of the window
        button_layout = QHBoxLayout()
        self.next_button = QPushButton("Choose Template")
        self.next_button.clicked.connect(self.go_to_preview)
        self.next_button.setEnabled(False)
        self.enable_next_if_ready()
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
        self.shared_data.table_data = []
        with open(filename, "r", encoding="utf-8-sig") as csv_file:
            reader = list(csv.reader(csv_file, delimiter=",", quotechar='"'))
            self.table.setRowCount(0)
            start_index = 0
            if reader[0][0].lower() == CSV_FIELDS[0]["label"].lower():
                print("Skipping header row.")
                start_index = 1
            for row_number, row_data in enumerate(reader[start_index:]):
                print(f"Processing row {row_number}")
                try:
                    row_data = validate_csv_row(row_number, row_data)
                except CSV_VALIDATION_ERROR as e:
                    QMessageBox.warning(None, "Invalid CSV Entry", str(e))
                    print(f"Invalid CSV Entry: {e}")
                    return
                if not row_data:
                    continue
                self.table.insertRow(row_number)
                self.shared_data.table_data.append(row_data)
                for column_number, data in enumerate(row_data):
                    print(f"Row data: {data}", end=" ")
                    self.table.setItem(
                        row_number, column_number, QTableWidgetItem(str(data))
                    )

            # Resize the columns to fit the data
            self.table.resizeColumnsToContents()
            self.enable_next_if_ready()

    def enable_next_if_ready(self):
        if (
            len(self.shared_data.table_data) > 0
            and len(self.shared_data.table_data[0]) == len(CSV_FIELDS)
            and self.shared_data.template_depot
        ):
            self.next_button.setEnabled(True)

    def go_to_preview(self):
        self.shared_data.table_data = []
        for row in range(self.table.rowCount()):
            row_data = []
            for column in range(self.table.columnCount()):
                cell = self.table.item(row, column)
                row_data.append(cell.text())
            self.shared_data.table_data.append(row_data)

        self.parent().push(PreviewWindow(self.shared_data))

    def set_template_depot(self, index):
        self.shared_data.template_depot = self.template_depots[index]
        self.enable_next_if_ready()


class PreviewWindow(QWidget):
    def __init__(self, shared_data, parent=None):
        super().__init__(parent=parent)
        self.shared_data = shared_data

        print("Setup Data:")
        print(self.shared_data)

        users = [
            {
                "User": row[1].split("@")[0],
                "Email": row[1],
                "FullName": row[0],
            }
            for row in self.shared_data.table_data
        ]
        self.shared_data.users_to_create = p4_utils.check_users(users)
        remaining_licenses = p4_utils.check_remaining_seats()

        group_users = {}
        for row in self.shared_data.table_data:
            group_users[row[2]] = group_users.get(row[2], []) + [row[1].split("@")[0]]
        self.shared_data.groups_to_create = [
            {
                "Group": group,
                "Users": group_users[group],
            }
            for group in group_users
        ]
        unique_depots = list(group_users)
        self.shared_data.depots_to_create = p4_utils.check_depots(unique_depots)

        self.shared_data.permissions_to_create = p4_utils.check_permissions(
            unique_depots
        )

        # Set up the main Vertical Layout
        main_layout = QVBoxLayout()
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Adding label widget - Creation Summary
        heading_label = QLabel("Creation Summary")
        heading_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        main_layout.addWidget(heading_label)

        # Setting up messages
        messages = [
            f"This will create <b>{len(self.shared_data.users_to_create)}</b> new users. (Seats remaining on server: {remaining_licenses})",
            f"This will create/update <b>{len(self.shared_data.groups_to_create)}</b> new groups.",
            f"This will create <b>{len(self.shared_data.depots_to_create)}</b> new depots.",
            f"This will create <b>{len(self.shared_data.permissions_to_create)}</b> new permission lines.",
            f"New depots will be populated from <b>{self.shared_data.template_depot['map']}</b>",
        ]

        # Looping through messages and adding to layout
        for message in messages:
            label = QLabel(message)
            label.setStyleSheet("font-size: 14px; margin-bottom: 10px;")
            main_layout.addWidget(label)

        # Additional information
        label_info = QLabel("Press 'Create All' if this looks correct.")
        label_info.setStyleSheet(
            "font-size: 16px; font-style: italic; margin-top: 20px;"
        )
        main_layout.addWidget(label_info)

        # Set up the button box at the bottom of the window
        main_layout.addStretch(1)

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
        main_layout.addWidget(QLabel(f"{self.shared_data.template_depot}"))

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
