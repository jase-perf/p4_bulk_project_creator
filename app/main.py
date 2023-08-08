import sys
import csv
import re
import os
from collections import defaultdict

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
    QDialog,
    QLineEdit,
    QProgressBar,
)
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QRunnable, pyqtSlot, QThreadPool

import p4_utils

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
        self.next_button = QPushButton("Preview")
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

        group_users = defaultdict(lambda: {"Users": [], "Owners": []})
        for row in self.shared_data.table_data:
            if row[3] == "True":
                group_users[row[2]]["Owners"].append(row[1].split("@")[0])
            group_users[row[2]]["Users"].append(row[1].split("@")[0])
        self.shared_data.groups_to_create = [
            {
                "Group": group,
                "Users": group_users[group]["Users"],
                "Owners": group_users[group]["Owners"],
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
            f"This will create/update <b>{len(self.shared_data.groups_to_create)}</b> groups.",
            f"This will create/update <b>{len(self.shared_data.depots_to_create)}</b> depots.",
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


class Signals(QObject):
    finished = pyqtSignal()
    progress = pyqtSignal(int)


class Creator(QRunnable):
    def __init__(self, func, list_to_create):
        super(Creator, self).__init__()

        self.func = func
        self.list_to_create = list_to_create
        self.signals = Signals()

    @pyqtSlot()
    def run(self):
        self.func(self.list_to_create, self.signals.progress)
        self.signals.finished.emit()


class CreationWindow(QWidget):
    def __init__(self, shared_data, parent=None):
        super().__init__(parent=parent)
        self.shared_data = shared_data
        self.threadpool = QThreadPool()

        # Set up the main Vertical Layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(QLabel("Hello Creation!"))
        main_layout.addWidget(
            QLabel(f"Creating {len(self.shared_data.users_to_create)} Users:")
        )
        self.user_progress = QProgressBar(self)
        self.user_progress.setMaximum(len(self.shared_data.users_to_create))
        if not self.shared_data.users_to_create:
            self.user_progress.setMaximum(1)
            self.user_progress.setValue(1)
        main_layout.addWidget(self.user_progress)
        main_layout.addWidget(
            QLabel(f"Creating {len(self.shared_data.groups_to_create)} Groups:")
        )
        self.group_progress = QProgressBar(self)
        self.group_progress.setMaximum(len(self.shared_data.groups_to_create))
        main_layout.addWidget(self.group_progress)
        main_layout.addWidget(QLabel(f"{self.shared_data.template_depot}"))
        main_layout.addWidget(
            QLabel(f"Creating {len(self.shared_data.depots_to_create)} Depots:")
        )
        self.depot_progress = QProgressBar(self)
        self.depot_progress.setMaximum(len(self.shared_data.depots_to_create))
        main_layout.addWidget(self.depot_progress)
        main_layout.addWidget(
            QLabel(f"Populating {len(self.shared_data.depots_to_create)} Depots:")
        )
        self.populate_progress = QProgressBar(self)
        self.populate_progress.setMaximum(len(self.shared_data.depots_to_create))
        main_layout.addWidget(self.populate_progress)
        main_layout.addWidget(
            QLabel(
                f"Creating {len(self.shared_data.permissions_to_create)} Permissions:"
            )
        )
        self.permission_progress = QProgressBar(self)
        self.permission_progress.setMaximum(1)  # This is done in a single step
        main_layout.addWidget(self.permission_progress)

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

        self.create_users()

    def create_users_worker(self, users_to_create, progress_callback):
        for i, user in enumerate(users_to_create):
            p4_utils.create_user(user)
            progress_callback.emit(i + 1)

    def create_users(self):
        print("Create users was called.")
        if not self.shared_data.users_to_create:
            self.create_groups()
            return
        worker = Creator(self.create_users_worker, self.shared_data.users_to_create)
        worker.signals.progress.connect(self.user_progress.setValue)
        worker.signals.finished.connect(self.create_groups)
        self.threadpool.start(worker)

    def create_groups_worker(self, groups_to_create, progress_callback):
        for i, group in enumerate(groups_to_create):
            p4_utils.create_group(group)
            progress_callback.emit(i + 1)

    def create_groups(self):
        print("Create groups was called")
        worker = Creator(self.create_groups_worker, self.shared_data.groups_to_create)
        worker.signals.progress.connect(self.group_progress.setValue)
        worker.signals.finished.connect(self.create_depots)
        self.threadpool.start(worker)

    def create_depots_worker(self, depots_to_create, progress_callback):
        depot_type = self.shared_data.template_depot["type"]
        for i, depot_name in enumerate(depots_to_create):
            p4_utils.create_depot(depot_name, depot_type)
            streams_to_create = p4_utils.get_streams(
                self.shared_data.template_depot["name"], depot_name
            )
            for stream in streams_to_create:
                p4_utils.create_stream(stream)
            progress_callback.emit(i + 1)

    def create_depots(self):
        print("Create depots was called")
        worker = Creator(self.create_depots_worker, self.shared_data.depots_to_create)
        worker.signals.progress.connect(self.depot_progress.setValue)
        worker.signals.finished.connect(self.populate_depots)
        self.threadpool.start(worker)

    def populate_depots_worker(self, depots_to_create, progress_callback):
        for i, depot_name in enumerate(depots_to_create):
            try:
                p4_utils.populate_new_depot(
                    self.shared_data.template_depot["name"], depot_name
                )
            except p4_utils.P4Exception as e:
                print(f"Error populating depot {depot_name}: {e}")
            progress_callback.emit(i + 1)

    def populate_depots(self):
        print("Populate depots was called")
        worker = Creator(self.populate_depots_worker, self.shared_data.depots_to_create)
        worker.signals.progress.connect(self.populate_progress.setValue)
        worker.signals.finished.connect(self.create_permissions)
        self.threadpool.start(worker)

    def create_permissions_worker(self, permissions_to_create, progress_callback):
        p4_utils.create_permissions(permissions_to_create)
        progress_callback.emit(1)

    def create_permissions(self):
        print("Called create permissions")
        worker = Creator(
            self.create_permissions_worker, self.shared_data.permissions_to_create
        )
        worker.signals.progress.connect(self.permission_progress.setValue)
        worker.signals.finished.connect(self.complete)
        self.threadpool.start(worker)

    def complete(self):
        print("Complete!")
        self.next_button.setEnabled(True)


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


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super(LoginDialog, self).__init__(parent)

        self.setWindowTitle("Login")
        self.resize(500, 300)

        self.layout = QVBoxLayout()
        self.p4port = QLineEdit()
        self.p4port.setText(os.environ.get("P4PORT", ""))
        self.username = QLineEdit()
        self.username.setText(os.environ.get("P4USER", ""))
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.login_button = QPushButton("Login")
        self.login_button.setDefault(True)

        self.layout.addWidget(QLabel("P4PORT:"))
        self.layout.addWidget(self.p4port)
        self.layout.addWidget(QLabel("Username:"))
        self.layout.addWidget(self.username)
        self.layout.addWidget(QLabel("Password:"))
        self.layout.addWidget(self.password)
        self.layout.addWidget(self.login_button)

        self.setLayout(self.layout)

        # Connect the clicked signal of the button to your authentication method
        self.login_button.clicked.connect(self.authenticate_user)

    def authenticate_user(self):
        try:
            p4_utils.init(
                username=self.username.text(),
                port=self.p4port.text(),
                password=self.password.text(),
            )
        except p4_utils.P4PasswordException as e:
            QMessageBox.warning(
                None, "Incorrect password", "Please re-enter password and try again."
            )
            return
        except p4_utils.P4Exception as e:
            QMessageBox.warning(
                None,
                "Login Failed",
                f"""Login failed.

Check your port, username, and password and try again.


Error message: {e.errors}""",
            )
            return
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self, shared_data, parent=None):
        super().__init__(parent=parent)
        self.shared_data = shared_data
        self.setWindowTitle("Create Projects from CSV")
        self.resize(1200, 800)
        self.stacked_widget = StackedWidget()
        self.setCentralWidget(self.stacked_widget)
        self.login()
        # Start with just our first widget
        self.stacked_widget.push(LoadCsvWindow(shared_data))

    def login(self):
        try:
            p4_utils.init()
        except p4_utils.P4Exception:
            login_dialog = LoginDialog(self)
            result = login_dialog.exec()
            if result == QDialog.DialogCode.Rejected:
                self.close()
                sys.exit()
            return

        print("Logged in!")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    shared_data = SharedData()
    window = MainWindow(shared_data)
    window.show()
    sys.exit(app.exec())
