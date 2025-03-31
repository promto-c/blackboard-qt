# Type Checking Imports
# ---------------------
from typing import Tuple, Optional, List, Union, Dict, Iterable

# Standard Library Imports
# ------------------------
import subprocess
import re
import os
import configparser
from enum import Enum

# Third Party Imports
# -------------------
from qtpy import QtCore, QtGui, QtWidgets


# Class Definitions
# -----------------
class ApplicationSection(Enum):
    DEFAULT = 'default'
    REGISTERED = 'registered'
    RECOMMENDED = 'recommended'

    def __str__(self):
        return self.value

class ApplicationUtil:
    """Utility class for handling application-related operations.

    This class provides static methods to interact with MIME types, find associated
    applications, and manage .desktop files for applications.
    """
    # Class constants for common paths
    APPLICATIONS_PATH = '/usr/share/applications/'
    USER_APPLICATIONS_PATH = os.path.expanduser('~/.local/share/applications/')

    # Class constants for regex patterns used in MIME type associations
    MIME_TYPE_TO_ASSOCIATION_REGEX = {
        ApplicationSection.DEFAULT: re.compile(r'Default application for “.+?”: (.+)'),
        ApplicationSection.REGISTERED: re.compile(r'Registered applications:\n((?:\s+.+\.desktop\n)+)'),
        ApplicationSection.RECOMMENDED: re.compile(r'Recommended applications:\n((?:\s+.+\.desktop\n)+)'),
    }

    @staticmethod
    def get_mime_type(file_path: str) -> str:
        """Get the MIME type of the specified file.

        Args:
            file_path (str): The path to the file for which to get the MIME type.

        Returns:
            str: The MIME type of the file.
        """
        if os.name == 'nt':
            import mimetypes
            mime_type, _ = mimetypes.guess_type(file_path)
        else:
            mime_type = subprocess.check_output(['file', '--mime-type', '-b', file_path]).decode().strip()
        return mime_type

    @staticmethod
    def get_mime_type_associations(mime_type: str) -> Dict[str, Union[str, List[str]]]:
        """Retrieve MIME type associations using the 'gio mime' command.

        Args:
            mime_type (str): The MIME type to search for associated applications.

        Returns:
            dict: A dictionary with keys 'default', 'registered', 'recommended' and their associated applications.
        """
        # Initialize the dictionary to hold the associations
        data = {'default': None, 'registered': [], 'recommended': []}

        # If the MIME type is empty, return the initialized dictionary
        if not mime_type:
            return data

        # Run the 'gio mime' command to get the associations for the MIME type
        result = subprocess.check_output(['gio', 'mime', mime_type]).decode().strip()

        # Iterate through the regex patterns and match them against the command output
        for key, pattern in ApplicationUtil.MIME_TYPE_TO_ASSOCIATION_REGEX.items():
            match = pattern.search(result)
            if not match:
                continue

            # If the key is 'default', store the single default application
            if key == ApplicationSection.DEFAULT:
                data[key.value] = match.group(1).strip()
            # For 'registered' and 'recommended', store the list of applications
            else:
                data[key.value] = [app.strip() for app in match.group(1).strip().split('\n')]

        return data

    @staticmethod
    def get_associated_apps(mime_type: str, section: Union[ApplicationSection, str] = ApplicationSection.DEFAULT) -> Union[str, List[str]]:
        """List applications associated with a given MIME type.

        Args:
            mime_type (str): The MIME type to search for associated applications.
            section (Union[ApplicationSection, str]): The section of applications to return ('default', 'registered', 'recommended').

        Returns:
            Union[str, List[str]]: The path to the default application or a list of paths to the registered or recommended applications.

        Raises:
            ValueError: If the provided section is invalid.
        """
        # Convert section to ApplicationSection if it's a string
        if isinstance(section, str):
            try:
                section = ApplicationSection(section.lower())
            except ValueError:
                raise ValueError(f"Invalid section '{section}'. Choose from 'default', 'registered', 'recommended'.")
        elif section not in ApplicationSection:
            raise ValueError(f"Invalid section '{section.value}'. Choose from 'default', 'registered', 'recommended'.")

        # Fetch the associated applications data for the given MIME type
        parsed_data = ApplicationUtil.get_mime_type_associations(mime_type)

        # Return the appropriate data based on the section
        if section == ApplicationSection.DEFAULT:
            return ApplicationUtil.find_desktop_file(parsed_data[section.value])
        else:
            return ApplicationUtil.find_desktop_files(parsed_data[section.value])

    @staticmethod
    def parse_desktop_file(desktop_file: str) -> Tuple[Optional[str], Optional[str]]:
        """Parse the .desktop file to extract the application name and icon path.

        Args:
            desktop_file (str): Path to the .desktop file.

        Returns:
            Tuple[Optional[str], Optional[str]]: The application name and icon path, or None if not found.
        """
        config = configparser.ConfigParser()
        config.read(desktop_file)

        name = config.get('Desktop Entry', 'Name', fallback=None)
        icon = config.get('Desktop Entry', 'Icon', fallback=None)

        return name, icon

    @staticmethod
    def find_desktop_file(app_name: str) -> Optional[str]:
        """Find the full path of the .desktop file for the specified application.

        Args:
            app_name (str): The name of the application for which to find the .desktop file.

        Returns:
            Optional[str]: The full path to the .desktop file, or None if not found.
        """
        search_paths = [ApplicationUtil.APPLICATIONS_PATH, ApplicationUtil.USER_APPLICATIONS_PATH]
        for path in search_paths:
            desktop_file = os.path.join(path, app_name)
            if os.path.isfile(desktop_file):
                return desktop_file
        return None

    @staticmethod
    def find_desktop_files(app_names: List[str]) -> List[Optional[str]]:
        """Find the full paths of .desktop files for a list of specified applications.

        Args:
            app_names (List[str]): A list of application names for which to find .desktop files.

        Returns:
            List[Optional[str]]: A list of full paths to the .desktop files. The list will be empty if no .desktop files are found.
        """
        return [ApplicationUtil.find_desktop_file(app) for app in app_names if ApplicationUtil.find_desktop_file(app)]

    @staticmethod
    def open_file_with_application(file_path: str, desktop_file: str):
        """Open the file with the specified application.

        Args:
            file_path (str): The path to the file to be opened.
            desktop_file (str): The path to the .desktop file of the application to use.

        Raises:
            ValueError: If no .desktop file is found for the selected application.
        """
        if desktop_file:
            subprocess.run(['gio', 'launch', desktop_file, file_path])
        else:
            print("No .desktop file found for the selected application.")

    # @staticmethod
    # def open_directory_in_terminal(path: str) -> None:
    #     """Opens the specified directory in a new terminal window.

    #     Args:
    #         path (str): The path to open in the terminal.
    #     """
    #     if not os.path.isdir(path):
    #         path = os.path.dirname(path)

    #     if os.name == 'nt':  # Windows
    #         os.startfile(path)
    #     elif os.name == 'posix':  # macOS or Linux
    #         subprocess.Popen(['xdg-open', path])
    #     else:
    #         raise NotImplementedError(f"Unsupported operating system: {os.name}")

    @staticmethod
    def open_containing_folder(file_paths: Union[str, Iterable[str]]):
        """Open the folder containing the specified file or files.

        Args:
            file_paths (Union[str, Iterable[str]]): The path or paths to the file(s) whose containing folder(s) is to be opened.
        """
        # Ensure file_paths is an iterable
        if isinstance(file_paths, str):
            file_paths = [file_paths]

        # Extract folders
        folders = {(os.path.isfile(file_path) and os.path.dirname(file_path)) or file_path for file_path in file_paths}

        # Open each folder
        for folder in folders:
            ApplicationUtil.open_file(folder)

    @staticmethod
    def open_file(file_path: str):
        """Open the specified file using the default application for its type.

        Args:
            file_path (str): The path to the file to be opened.
        """
        if os.name == 'nt':  # Windows
            os.startfile(file_path)
        elif os.name == 'posix':  # macOS or Linux
            subprocess.run(['xdg-open', file_path])
        else:
            raise NotImplementedError(f"Unsupported operating system: {os.name}")

    @staticmethod
    def open_directory_in_terminal(directories: Union[str, List[str]]):
        """Open directories in Terminal. If one directory, open in new Terminal; otherwise, open in tabs.

        Args:
            directories (Union[str, List[str]]): The path(s) to open in the terminal.
        """
        directories = [directories] if isinstance(directories, str) else directories
        directories = list({os.path.dirname(directory) if os.path.isfile(directory) else directory for directory in directories})

        if len(directories) == 1:
            # Prepare command to open in new Terminal for one directory
            commands = ['gnome-terminal', f'--working-directory={directories[0]}']
        else:
            # Prepare command to open in new Terminal with tabs for multiple directories
            commands = ['gnome-terminal']
            for directory in directories:
                commands.extend(['--tab', f'--working-directory={directory}'])

        # Call subprocess to launch Terminal
        subprocess.Popen(commands)


class QApplicationUtils:
    """Utility class for handling QApplication-related operations.
    """

    @staticmethod
    def forward_mouse_event(event: QtCore.QEvent, target: QtWidgets.QWidget) -> bool:
        """Forwards a mouse event to a specified target widget.

        This function maps the global position of the mouse event to the local
        coordinate system of the target widget and sends the event to the target.

        Args:
            event (QtCore.QEvent): The mouse event to be forwarded. Typically an instance
                of `QtGui.QMouseEvent`.
            target (QtWidgets.QWidget): The target widget to which the event should be forwarded.

        Returns:
            bool: True if the event was successfully sent and handled by the target widget,
                False otherwise.
        """
        if isinstance(event, QtGui.QMouseEvent):
            mapped_event = QtGui.QMouseEvent(
                event.type(),
                target.mapFromGlobal(event.globalPos()),
                event.button(),
                event.buttons(),
                event.modifiers(),
            )
        else:
            # Use the original event as fallback (not recommended for all types)
            mapped_event = event

        return QtWidgets.QApplication.sendEvent(target, mapped_event)
