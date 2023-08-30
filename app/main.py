import sys
import csv
import re
import os
import logging
import configparser
import argparse
from datetime import datetime
from pathlib import Path
from collections import defaultdict

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
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


# Create a custom logger
logger = logging.getLogger("main")
logger.setLevel(logging.DEBUG)

LOG_FILE = "log.txt"
UNDO_FILE = datetime.now().strftime("undo_commands_%Y-%m-%d_%H-%M-%S.txt")
CONFIG_FILE = Path("config.ini")


def setup_logger(console_level=logging.INFO, file_level=logging.DEBUG):
    # Create handlers
    c_handler = logging.StreamHandler()
    f_handler = logging.FileHandler(LOG_FILE)

    # Set level of logging
    c_handler.setLevel(console_level)
    f_handler.setLevel(file_level)

    # Create formatters and add it to handlers
    c_format = logging.Formatter("[%(levelname)s]: %(message)s")
    f_format = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    c_handler.setFormatter(c_format)
    f_handler.setFormatter(f_format)

    # Add handlers to the logger
    logger.addHandler(c_handler)
    logger.addHandler(f_handler)


def read_config(parameter, fallback=None):
    if CONFIG_FILE.exists():
        logger.debug(f"Reading config file {CONFIG_FILE}")
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE)
        result = config.get("DEFAULT", parameter, fallback=fallback)
        logger.debug(f"{parameter} = '{result or fallback}'")
        return result or fallback
    logger.debug(f"No config file found. Using fallback: {fallback}")
    return fallback


# r"[^@]+\.[^@]+" will match any standard 2-part domain name for email.
# EMAIL_DOMAIN can be customized to require a specific domain like, "myuniversity.edu"
EMAIL_DOMAIN = r"[^@]+\.[^@]+"
DEFAULT_PASSWORD = "ChangeMe123!"
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
        logger.debug(
            f"Checking [{i},{column}] {data} against {CSV_FIELDS[column]['label']} validation function..."
        )
        formatted_data = CSV_FIELDS[column]["validation"](data.strip())
        if formatted_data is None:
            raise CSV_VALIDATION_ERROR(
                f"CSV row invalid: \n{row} \n\n'{data}' is not a valid '{CSV_FIELDS[column]['label']}'."
            )
        formatted_row.append(formatted_data)
    return formatted_row


class SharedData:
    def __init__(self):
        self.table_data = []
        self.template_depot = None
        self.undo_commands = []


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
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
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
        self.next_button = QPushButton("Go to Creation Page")
        self.next_button.clicked.connect(self.go_to_creation)
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
                logger.debug("Skipping header row.")
                start_index = 1
            for row_number, row_data in enumerate(reader[start_index:]):
                try:
                    row_data = validate_csv_row(row_number, row_data)
                    logger.debug(f"Row {row_number}: {row_data}")
                except CSV_VALIDATION_ERROR as e:
                    QMessageBox.warning(None, "Invalid CSV Entry", str(e))
                    logger.error(f"Invalid CSV Entry: {e}")
                    return
                if not row_data:
                    continue
                self.table.insertRow(row_number)
                self.shared_data.table_data.append(row_data)
                for column_number, data in enumerate(row_data):
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

    def go_to_creation(self):
        self.shared_data.table_data = []
        for row in range(self.table.rowCount()):
            row_data = []
            for column in range(self.table.columnCount()):
                cell = self.table.item(row, column)
                row_data.append(cell.text())
            self.shared_data.table_data.append(row_data)

        self.parent().push(CombinedWindow(self.shared_data))

    def set_template_depot(self, index):
        self.shared_data.template_depot = self.template_depots[index]
        self.enable_next_if_ready()


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


class CombinedWindow(QWidget):
    def __init__(self, shared_data, parent=None):
        super().__init__(parent=parent)
        self.shared_data = shared_data
        self.threadpool = QThreadPool()

        self.prepare_data()

        # Set up the main Vertical Layout
        self.main_layout = QVBoxLayout()

        # Adding label widget - Creation Summary
        heading_label = QLabel("Creation Summary")
        heading_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.main_layout.addWidget(heading_label)

        # Add message about log and undo files
        undo_label = QLabel(f"Undo commands will be written to <code>{Path(UNDO_FILE).absolute()}</code>")
        self.main_layout.addWidget(undo_label)
        log_label = QLabel(f"Log file location: <code>{Path(LOG_FILE).absolute()}</code>")
        self.main_layout.addWidget(log_label)

        # __USERS__
        self.user_button, self.user_progress = self.create_widgets(
            label_text=f"Create <b>{len(self.shared_data.users_to_create)}</b> new users. (Seats remaining on server: {self.shared_data.remaining_licenses})",
            button_text="Create Users",
            button_method=self.create_users,
            item_count=len(self.shared_data.users_to_create),
        )

        # __GROUPS__
        self.group_button, self.group_progress = self.create_widgets(
            label_text=f"Creating/Updating {len(self.shared_data.groups_to_process)} Groups:",
            button_text="Update Groups",
            button_method=self.create_groups,
            item_count=len(self.shared_data.groups_to_process),
        )

        # __PERMISSIONS__
        self.permission_button, self.permission_progress = self.create_widgets(
            label_text=f"Creating {len(self.shared_data.permissions_to_create)} Permissions:",
            button_text="Create Permissions",
            button_method=self.create_permissions,
            item_count=1 if self.shared_data.permissions_to_create else 0,
        )

        # __DEPOTS__
        self.depot_button, self.depot_progress = self.create_widgets(
            label_text=f"Creating {len(self.shared_data.depots_to_create)} Depots:",
            button_text="Create Depots",
            button_method=self.create_depots,
            item_count=len(self.shared_data.depots_to_create),
        )

        # __POPULATE DEPOTS__
        self.populate_button, self.populate_progress = self.create_widgets(
            label_text=f"Populating {len(self.shared_data.depots_to_create)} Depots:",
            button_text="Awaiting Depots",
            button_method=self.populate_depots,
            item_count=len(self.shared_data.depots_to_create),
        )
        self.populate_button.setEnabled(False)

        # Set up the button box at the bottom of the window
        button_layout = QHBoxLayout()
        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(lambda: self.parent().pop())
        button_layout.addWidget(self.back_button)
        self.next_button = QPushButton("Close")
        self.next_button.clicked.connect(QApplication.instance().quit)
        button_layout.addWidget(self.next_button)
        self.main_layout.addLayout(button_layout)

        # Set the main layout of the window
        self.setLayout(self.main_layout)

    def prepare_data(self):
        logger.debug("Preparing Data:")

        # ____________USERS____________
        users = [
            {
                "User": row[1].split("@")[0],
                "Email": row[1],
                "FullName": row[0],
            }
            for row in self.shared_data.table_data
        ]
        self.shared_data.users_to_create = p4_utils.check_users(users)
        logger.debug(f"Users to create: {self.shared_data.users_to_create}")
        try:
            self.shared_data.remaining_licenses = p4_utils.check_remaining_seats()
        except p4_utils.P4Exception as e:
            logger.error(f"Unable to check remaining seats: {e}")
            self.shared_data.remaining_licenses = 0

        # ____________GROUPS____________
        existing_groups = p4_utils.get_existing_groups()
        group_users = defaultdict(lambda: {"Users": [], "Owners": []})
        for row in self.shared_data.table_data:
            if row[3] == "True":
                group_users[row[2]]["Owners"].append(row[1].split("@")[0])
            group_users[row[2]]["Users"].append(row[1].split("@")[0])
        self.shared_data.groups_to_process = [
            {
                "Group": group,
                "Users": group_users[group]["Users"],
                "Owners": group_users[group]["Owners"],
            }
            for group in group_users
        ]
        self.shared_data.groups_to_create = [
            group
            for group in self.shared_data.groups_to_process
            if not any(eg for eg in existing_groups if eg["Group"] == group["Group"])
        ]
        self.shared_data.groups_to_modify = [
            group
            for group in self.shared_data.groups_to_process
            if any(eg for eg in existing_groups if eg["Group"] == group["Group"])
        ]
        logger.debug(f"Groups to create: {self.shared_data.groups_to_create}")
        logger.debug(f"Groups to modify: {self.shared_data.groups_to_modify}")

        # _________DEPOTS__________
        unique_depots = list(group_users)
        self.shared_data.depots_to_create = p4_utils.check_depots(unique_depots)
        logger.debug(f"Depots to create: {self.shared_data.depots_to_create}")

        # _________PERMISSIONS__________
        self.shared_data.permissions_to_create = p4_utils.check_permissions(
            unique_depots
        )
        logger.debug(f"Permissions to create: {self.shared_data.permissions_to_create}")

    def create_widgets(self, label_text, button_text, button_method, item_count):
        # Add label
        self.main_layout.addWidget(QLabel(label_text))

        # Create layout for button and progress bar
        operation_layout = QHBoxLayout()

        # Add button
        operation_button = QPushButton(button_text if item_count > 0 else "Done")
        operation_button.clicked.connect(button_method)
        if item_count == 0:
            operation_button.setEnabled(False)
        operation_layout.addWidget(operation_button)

        # Add progress bar
        operation_progress = QProgressBar(self)
        operation_progress.setMaximum(item_count if item_count > 0 else 1)
        operation_progress.setValue(0 if item_count > 0 else 1)
        operation_layout.addWidget(operation_progress)

        # Add layout to main layout
        self.main_layout.addLayout(operation_layout)

        return operation_button, operation_progress

    def create_users(self):
        logger.debug("Create users was called.")
        self.user_button.setEnabled(False)
        if not self.shared_data.users_to_create:
            logger.debug("No users to create.")
            self.user_button.setText("Done")
            return
        worker = Creator(self.create_users_worker, self.shared_data.users_to_create)
        worker.signals.progress.connect(self.user_progress.setValue)
        worker.signals.finished.connect(self.users_complete)
        self.threadpool.start(worker)

    def create_users_worker(self, users_to_create, progress_callback):
        for i, user in enumerate(users_to_create):
            logger.debug(f"User ({i+1}/{len(users_to_create)}) {user}")
            p4_utils.create_user(user)
            pw_res = p4_utils.set_initial_password(user["User"], DEFAULT_PASSWORD)
            logger.debug(f"Password set: {pw_res}")
            progress_callback.emit(i + 1)

    def users_complete(self):
        self.user_button.setText("Done")
        self.user_button.setEnabled(False)
        undo_commands = [
            f"p4 user -df {user['User']}" for user in self.shared_data.users_to_create
        ]
        self.shared_data.undo_commands.extend(undo_commands)
        self.write_undo_file()
        undo_commands_str = "\n".join(undo_commands)
        logger.debug(f"Users created. Undo commands below:\n{undo_commands_str}")

    def create_groups(self):
        logger.debug("Create groups was called")
        self.group_button.setEnabled(False)
        worker = Creator(self.create_groups_worker, self.shared_data.groups_to_process)
        worker.signals.progress.connect(self.group_progress.setValue)
        worker.signals.finished.connect(self.groups_complete)
        self.threadpool.start(worker)

    def create_groups_worker(self, groups_to_create, progress_callback):
        for i, group in enumerate(groups_to_create):
            p4_utils.create_group(group)
            progress_callback.emit(i + 1)

    def groups_complete(self):
        self.group_button.setText("Done")
        self.group_button.setEnabled(False)
        undo_commands = [
            f"p4 group -dF {group['Group']}"
            for group in self.shared_data.groups_to_process
        ]
        undo_commands_str = "\n".join(undo_commands)
        self.shared_data.undo_commands.extend(undo_commands)
        self.write_undo_file()
        logger.debug(f"Groups created. Undo commands below:\n{undo_commands_str}")

    def create_permissions(self):
        logger.debug("Called create permissions")
        self.permission_button.setEnabled(False)
        worker = Creator(
            self.create_permissions_worker, self.shared_data.permissions_to_create
        )
        worker.signals.progress.connect(self.permission_progress.setValue)
        worker.signals.finished.connect(self.permissions_complete)
        self.threadpool.start(worker)

    def create_permissions_worker(self, permissions_to_create, progress_callback):
        p4_utils.create_permissions(permissions_to_create)
        progress_callback.emit(1)

    def permissions_complete(self):
        self.permission_button.setText("Done")
        self.permission_button.setEnabled(False)
        added_lines = "\n".join(self.shared_data.permissions_to_create)
        logger.debug(
            f"Permissions created. New lines below. Deleting groups with -dF command should remove permissions lines:\n{added_lines}"
        )

    def create_depots(self):
        logger.debug("Create depots was called")
        self.depot_button.setEnabled(False)
        worker = Creator(self.create_depots_worker, self.shared_data.depots_to_create)
        worker.signals.progress.connect(self.depot_progress.setValue)
        worker.signals.finished.connect(self.depots_complete)
        self.threadpool.start(worker)

    def create_depots_worker(self, depots_to_create, progress_callback):
        depot_type = self.shared_data.template_depot["type"]
        self.depot_undo = {}
        for i, depot_name in enumerate(depots_to_create):
            p4_utils.create_depot(depot_name, depot_type)
            streams_to_create = p4_utils.get_streams(
                self.shared_data.template_depot["name"], depot_name
            )
            for stream in streams_to_create:
                p4_utils.create_stream(stream)
            created_streams = [stream["Stream"] for stream in streams_to_create]
            logger.debug(f"Created depot {depot_name} with streams {created_streams}")
            self.depot_undo[depot_name] = reversed(created_streams)
            progress_callback.emit(i + 1)

    def depots_complete(self):
        self.depot_button.setText("Done")
        self.depot_button.setEnabled(False)
        self.populate_button.setText("Populate Depots")
        self.populate_button.setEnabled(True)
        undo_commands = []
        for depot_name, streams in self.depot_undo.items():
            undo_commands.extend(
                f"p4 stream --obliterate -y {stream}" for stream in streams
            )
            undo_commands.extend(
                (
                    f"p4 obliterate -y //{depot_name}/...",
                    f"p4 depot -d {depot_name}",
                )
            )
        self.shared_data.undo_commands.extend(undo_commands)
        self.write_undo_file()
        undo_commands_str = "\n".join(undo_commands)
        logger.debug(f"Depots created. Undo commands below:\n{undo_commands_str}")

    def populate_depots(self):
        logger.debug("Populate depots was called")
        self.populate_button.setEnabled(False)
        worker = Creator(self.populate_depots_worker, self.shared_data.depots_to_create)
        worker.signals.progress.connect(self.populate_progress.setValue)
        worker.signals.finished.connect(self.populate_complete)
        self.threadpool.start(worker)

    def populate_depots_worker(self, depots_to_create, progress_callback):
        for i, depot_name in enumerate(depots_to_create):
            try:
                p4_utils.populate_new_depot(
                    self.shared_data.template_depot["name"], depot_name
                )
            except p4_utils.P4Exception as e:
                logger.warning(f"Error populating depot {depot_name}: {e}")
            progress_callback.emit(i + 1)

    def populate_complete(self):
        self.populate_button.setText("Done")
        self.populate_button.setEnabled(False)

    def write_undo_file(self):
        with open(UNDO_FILE, "w") as f:
            f.write("\n".join(self.shared_data.undo_commands))


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
        self.resize(900, 600)
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

        logger.debug("Logged in!")


def main():
    global EMAIL_DOMAIN
    global DEFAULT_PASSWORD
    parser = argparse.ArgumentParser(
        description="Bulk create users, groups, depots, permissions, and populate from a template depot."
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging in console.",
    )
    args = parser.parse_args()
    setup_logger(logging.DEBUG if args.verbose else logging.INFO)

    logger.info(f"Log file location: {Path(LOG_FILE).absolute()}")
    logger.info(f"UNDO file location: {Path(UNDO_FILE).absolute()}")

    EMAIL_DOMAIN = read_config("EMAIL_DOMAIN", fallback=EMAIL_DOMAIN)
    DEFAULT_PASSWORD = read_config("DEFAULT_PASSWORD", fallback=DEFAULT_PASSWORD)

    app = QApplication(sys.argv)
    shared_data = SharedData()
    window = MainWindow(shared_data)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
