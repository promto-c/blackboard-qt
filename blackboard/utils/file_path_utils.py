# Type Checking Imports
# ---------------------
from typing import TYPE_CHECKING, Dict, List, Generator, Optional, Tuple, Union, Callable, Iterable, Set
if TYPE_CHECKING:
    from pathlib import Path

# Standard Library Imports
# ------------------------
import glob, os, datetime, re
from itertools import product
from enum import Enum
from collections import defaultdict

if os.name == 'nt':
    import win32security
else:
    import pwd

# Local Imports
# -------------
from blackboard.utils.path_utils import PathPattern


# Class Definitions
# -----------------
class FileUtil:
    """Utilities for working with files.
    """
    # Units for formatting file sizes
    DEFAULT_DATE_TIME_FORMAT = '%Y-%m-%d %H:%M:%S'
    UNITS = ['bytes', 'kB', 'MB', 'GB', 'TB', 'PB']
    FILE_INFO_FIELDS = ['file_name', 'file_path', 'file_size', 'file_extension', 'last_modified', 'file_owner']

    @staticmethod
    def extract_file_info(file_path: str, date_time_format: str = DEFAULT_DATE_TIME_FORMAT) -> Dict[str, str]:
        """Extract detailed information about a file.

        Args:
            file_path (str): Path to the file for extracting information.
            date_time_format (str): The format for the last modified timestamp.

        Returns:
            Dict[str, str]: A dictionary containing detailed file information, including:
                - file_name: The base name of the file.
                - file_path: The full path to the file.
                - file_size: File size in a human-readable format.
                - file_extension: The file extension.
                - last_modified: The last modification timestamp in the specified format.
                - file_owner: The owner of the file.
        """
        try:
            # Retrieve file statistics and details: file info, owner, last modified time, extension, and formatted size
            file_info = os.stat(file_path)
            owner = FileUtil.get_file_owner(file_path)
            modified_time = FileUtil.get_modified_time(file_info, date_time_format=date_time_format)
            extension = FileUtil.get_file_extension(file_path)
            readable_size = FileUtil.format_size(file_info.st_size)

        except FileNotFoundError:
            # NOTE: Handle the case of an invalid symlink file path
            owner = 'N/A'
            modified_time = 'N/A'
            extension = FileUtil.get_file_extension(file_path)
            readable_size = '0 bytes'

        # Compile the file details into a dictionary
        details = {
            "file_name": os.path.basename(file_path),
            "file_path": file_path,
            "file_size": readable_size,
            "file_extension": extension,
            "last_modified": modified_time,
            "file_owner": owner,
        }

        return details

    @classmethod
    def get_file_extension(cls, file_path: str, normalized: bool = False) -> str:
        """Get the file extension of a file.

        Args:
            file_path (str): Path to the file.
            normalized (bool, optional): Whether to return the extension in a normalized format 
                                         (lowercase, without a leading dot). Defaults to False.

        Returns:
            str: The file extension, or an empty string if the file has no extension.

        Examples:
            >>> FileUtil.get_file_extension("document.TXT")
            'TXT'
            >>> FileUtil.get_file_extension("document.TXT", normalized=True)
            'txt'
            >>> FileUtil.get_file_extension("archive.tar.gz")
            'gz'
            >>> FileUtil.get_file_extension("no_extension")
            ''
        """
        ext = file_path.rsplit('.', 1)[-1] if '.' in file_path else ''
        return cls.normalize_extension(ext) if normalized else ext

    @staticmethod
    def get_file_owner(file_path: str) -> str:
        """Get the owner of a file.

        Args:
            file_path (str): Path to the file.

        Returns:
            str: The name of the file owner.
        """
        if os.name == 'nt':
            sd = win32security.GetFileSecurity(file_path, win32security.OWNER_SECURITY_INFORMATION)
            owner_sid = sd.GetSecurityDescriptorOwner()
            name, domain, _type = win32security.LookupAccountSid(None, owner_sid)
            return f"{domain}\\{name}"
        else:
            file_info = os.stat(file_path)
            return pwd.getpwuid(file_info.st_uid).pw_name

    @staticmethod
    def get_modified_time(file_info: Union[str, os.stat_result], date_time_format: str = DEFAULT_DATE_TIME_FORMAT) -> str:
        """Get the last modification time of a file.
        """
        if isinstance(file_info, str):
            file_info = os.stat(file_info)

        return datetime.datetime.fromtimestamp(file_info.st_mtime).strftime(date_time_format)

    @staticmethod
    def format_size(size: int, precision: int = 2) -> str:
        """Convert a file size to a human-readable form with adjustable precision.

        Args:
            size (int): The size of the file in bytes.
            precision (int, optional): The number of decimal places for the formatted size. Defaults to 2.

        Returns:
            str: File size in a human-readable format, such as '1.23 MB'.
        """
        # Loop through each unit until the size is smaller than 1024
        for unit in FileUtil.UNITS:
            if size < 1024:
                # Use the appropriate format string based on the unit
                formatted_size = f"{size:.{precision}f} {unit}" if unit != 'bytes' else f"{size} {unit}"
                return formatted_size
            
            # Divide the size by 1024 to move to the next unit
            size /= 1024
        
        # Handle extremely large sizes that exceed petabytes
        return f"{size:.{precision}f} PB"

    @staticmethod
    def normalize_extension(extension: str) -> str:
        """Normalize a single file extension by stripping whitespace, removing any leading dot,
        and converting it to lowercase.

        Args:
            extension (str): The file extension string (e.g., '.TXT', ' py ', 'Md').

        Returns:
            str: The normalized file extension without a leading dot.

        Examples:
            >>> FileUtil.normalize_extension('.TXT')
            'txt'
            >>> FileUtil.normalize_extension(' py ')
            'py'
            >>> FileUtil.normalize_extension('Md')
            'md'
        """
        return extension.strip().lstrip('.').lower()

    @classmethod
    def normalize_extensions(cls, extensions: Set[str]) -> Set[str]:
        """Normalize a set of file extensions by stripping whitespace, converting to lowercase,
        and removing any leading dot.

        Args:
            extensions (Optional[Set[str]]): A set of file extension strings (e.g., {'.txt', ' py ', ' .Md'}).

        Returns:
            Optional[Set[str]]: A set of normalized extensions without a leading dot, or None if input is None.
        """
        return {cls.normalize_extension(ext) for ext in extensions}

    @classmethod
    def filter_files(cls, file_paths: List[str], included_extensions=None, excluded_extensions=None) -> List[str]:
        """Filters a list of file paths based on inclusion and exclusion criteria for file extensions.

        The file extension is determined by the portion of the file name after the last dot. Comparisons
        are case-insensitive, and the provided extensions are normalized (removing any leading dot and
        converting to lowercase).

        Filtering behavior:
            - If `included_extensions` is provided, only files with an extension in this set are included.
            - If `excluded_extensions` is provided, any file with an extension in this set is excluded.
            - If both are provided, a file must have an extension in `included_extensions` and not in `excluded_extensions`.

        Args:
            file_paths (List[str]): List of file paths to filter.
            included_extensions (Optional[Iterable[str]]): Extensions to include (e.g., {'.txt', 'py'}).
            excluded_extensions (Optional[Iterable[str]]): Extensions to exclude (e.g., {'zip', '.png'}).

        Returns:
            List[str]: A list of file paths that meet the filtering criteria.

        Examples:
            >>> files = ['document.txt', 'image.PNG', 'archive.zip', 'script.py']
            >>> FileUtil.filter_files(files, included_extensions={'.txt', '.py'})
            ['document.txt', 'script.py']
            >>> FileUtil.filter_files(files, excluded_extensions={'zip', '.png'})
            ['document.txt', 'script.py']
            >>> FileUtil.filter_files(files)
            ['document.txt', 'image.PNG', 'archive.zip', 'script.py']
        """
        # Normalize provided extension sets if they are not None.
        if included_extensions is not None:
            included_extensions = cls.normalize_extensions(included_extensions)
        if excluded_extensions is not None:
            excluded_extensions = cls.normalize_extensions(excluded_extensions)
        
        filtered_file_paths = []
        for file_path in file_paths:
            # Extract the extension and convert it to lowercase.
            ext = cls.get_file_extension(file_path, normalized=True)
            # If included_extensions is provided and the file's extension is not in it, skip the file.
            if included_extensions and ext not in included_extensions:
                continue
            # If excluded_extensions is provided and the file's extension is in it, skip the file.
            if excluded_extensions and ext in excluded_extensions:
                continue
            filtered_file_paths.append(file_path)
            
        return filtered_file_paths


class FormatStyle(Enum):
    """Enum for different placeholder formats for file sequences.
    """
    HASH = 'hash'                                           # '#'
    PERCENT = 'percent'                                     # '%0Nd'
    BRACKETS = 'brackets'                                   # '[0-9]'
    BRACES = 'braces'                                       # '{0..9}'
    HASH_WITH_RANGE = 'hash_with_range'                     # '####.ext 0-9'
    PERCENT_WITH_RANGE = 'percent_with_range'               # '%0Nd.ext 0-9'
    BRACKETS_SEPARATE_RANGES = 'brackets_separate_ranges'   # '[0-4,6-7,9]'

    def requires_range(self) -> bool:
        """Determine if the format style requires a range of frame numbers."""
        return self in {FormatStyle.BRACKETS, FormatStyle.BRACES, FormatStyle.HASH_WITH_RANGE, FormatStyle.PERCENT_WITH_RANGE}

    def requires_separate_ranges(self) -> bool:
        """Determine if the format style requires separate ranges."""
        return self == FormatStyle.BRACKETS_SEPARATE_RANGES


class SequenceFileUtil(FileUtil):
    """Utilities for working with sequence files."""

    DEFAULT_PADDING = 4

    FILE_INFO_FIELDS = {
        *FileUtil.FILE_INFO_FIELDS,
        'sequence_range',
        'sequence_count',
    }

    FORMAT_TO_REGEX = {
        # NOTE: FormatStyle.HASH_WITH_RANGE and FormatStyle.PERCENT_WITH_RANGE
        # should be ordered before FormatStyle.HASH and FormatStyle.PERCENT to ensure
        # that the more specific patterns with ranges are matched first.
        FormatStyle.HASH_WITH_RANGE: re.compile(r"(?P<base_name>.*)\.(?P<hashes>#+)\.(?P<extension>\w+) (?P<start_frame>\d+)-(?P<end_frame>\d+)"),
        FormatStyle.PERCENT_WITH_RANGE: re.compile(r"(?P<base_name>.*)\.%0(?P<padding>\d+)d\.(?P<extension>\w+) (?P<start_frame>\d+)-(?P<end_frame>\d+)"),
        FormatStyle.HASH: re.compile(r"(?P<base_name>.*)\.(?P<hashes>#+)\.(?P<extension>\w+)"),
        FormatStyle.PERCENT: re.compile(r"(?P<base_name>.*)\.%0(?P<padding>\d+)d\.(?P<extension>\w+)"),
        FormatStyle.BRACKETS: re.compile(r"(?P<base_name>.*)\.\[(?P<start_frame>\d+)-(?P<end_frame>\d+)\]\.(?P<extension>\w+)"),
        FormatStyle.BRACES: re.compile(r"(?P<base_name>.*)\.\{(?P<start_frame>\d+)\.\.(?P<end_frame>\d+)\}\.(?P<extension>\w+)"),
        FormatStyle.BRACKETS_SEPARATE_RANGES: re.compile(r"(?P<base_name>.*)\.\[(?P<ranges>[0-9,\-]+)\]\.(?P<extension>\w+)"),
    }

    FORMAT_TO_PADDING_RULES = {
        FormatStyle.HASH: lambda match_data: len(match_data['hashes']),
        FormatStyle.PERCENT: lambda match_data: int(match_data['padding']),
        FormatStyle.BRACKETS: lambda match_data: len(match_data['start_frame']),
        FormatStyle.BRACES: lambda match_data: len(match_data['start_frame']),
        FormatStyle.HASH_WITH_RANGE: lambda match_data: len(match_data['hashes']),
        FormatStyle.PERCENT_WITH_RANGE: lambda match_data: int(match_data['padding']),
        FormatStyle.BRACKETS_SEPARATE_RANGES: lambda match_data: len(match_data['ranges'].split(',')[0].split('-')[0]),
    }

    FORMAT_TO_STRING_PATTERNS = {
        FormatStyle.HASH: "{base_name}.{range_str}.{extension}",
        FormatStyle.PERCENT: "{base_name}.%0{padding}d.{extension}",
        FormatStyle.BRACKETS: "{base_name}.[{start_frame:0{padding}}-{end_frame:0{padding}}].{extension}",
        FormatStyle.BRACES: "{base_name}.{{{start_frame:0{padding}}..{end_frame:0{padding}}}}.{extension}",
        FormatStyle.HASH_WITH_RANGE: "{base_name}.{range_str}.{extension} {start_frame}-{end_frame}",
        FormatStyle.PERCENT_WITH_RANGE: "{base_name}.%0{padding}d.{extension} {start_frame}-{end_frame}",
        FormatStyle.BRACKETS_SEPARATE_RANGES: "{base_name}.[{range_str}].{extension}",
    }

    @staticmethod
    def extract_sequence_details(sequence_path_format: str, format_style: Optional['FormatStyle'] = None) -> Dict[str, str]:
        """Extract groups from the sequence path format.

        Args:
            sequence_path_format (str): The sequence path format.
            format_style (Optional[FormatStyle]): The format style to use, if not provided, it will be detected.

        Returns:
            Dict[str, str]: The extracted groups from the sequence path format.
        """
        format_style = format_style or SequenceFileUtil.detect_sequence_format(sequence_path_format)
        if not format_style:
            raise ValueError("Unsupported format style")

        match = SequenceFileUtil.FORMAT_TO_REGEX[format_style].match(sequence_path_format)
        if not match:
            raise ValueError("Invalid format")
        
        return match.groupdict()

    @staticmethod
    def get_padding(input_data: Union[Dict[str, str], str], format_style: Optional[FormatStyle] = None) -> int:
        """Determine the padding for sequence numbers based on the format style and match groups or sequence path format.

        Args:
            input_data (Union[dict, str]): The match groups from the regex or the sequence path format.
            format_style (Optional[FormatStyle]): The format style to use, if not provided, it will be detected.

        Returns:
            int: The number of digits to pad the sequence numbers.
        """
        # Detect format style and extract sequence details if input_data is a sequence path format string
        if isinstance(input_data, str):
            format_style = format_style or SequenceFileUtil.detect_sequence_format(input_data)
            sequence_data = SequenceFileUtil.extract_sequence_details(input_data, format_style)
        # Use input_data directly if it's already a dictionary of sequence details
        elif isinstance(input_data, dict):
            sequence_data = input_data
        else:
            raise TypeError("input_data must be a dict or str")

        # Ensure the format style is valid
        if not format_style:
            raise ValueError("Unsupported format style")

        # Determine and return the padding based on the format style and sequence details
        return SequenceFileUtil.FORMAT_TO_PADDING_RULES.get(format_style, lambda _: SequenceFileUtil.DEFAULT_PADDING)(sequence_data)

    @staticmethod
    def construct_sequence_file_path(format_style: 'FormatStyle', base_name: str, frame_numbers: List[str], extension: str,
                                     padding: int = DEFAULT_PADDING) -> str:
        """Construct the formatted sequence file path based on the specified format style using cached patterns.

        Args:
            format_style (FormatStyle): The format style to use, determining the pattern applied to the sequence.
            base_name (str): The base name of the sequence.
            frame_numbers (List[str]): The list of frame numbers to be included in the sequence.
            extension (str): The file extension to be appended to the formatted sequence.
            padding (int, optional): The number of digits to pad the sequence numbers. Default is 4.

        Returns:
            str: The formatted sequence file path based on the provided parameters and format style.

        Raises:
            ValueError: If the provided format style is unsupported.

        Examples:
            >>> SequenceFileUtil.construct_sequence_file_path(FormatStyle.HASH, 'image', ['1', '2', '3'], 'jpg', 4)
            'image.####.jpg'
            >>> SequenceFileUtil.construct_sequence_file_path(FormatStyle.HASH_WITH_RANGE, 'image', ['1', '2', '3'], 'jpg', 4)
            'image.####.jpg 1-3'
            >>> SequenceFileUtil.construct_sequence_file_path(FormatStyle.PERCENT, 'image', ['1', '2', '3'], 'jpg', 4)
            'image.%04d.jpg'
            >>> SequenceFileUtil.construct_sequence_file_path(FormatStyle.BRACKETS_SEPARATE_RANGES, 'project/shot/comp_v1', ['988', '1001', '1002', '1011'], 'jpg', 4)
            'project/shot/comp_v1.[0988,1001-1002,1011].jpg'
        """
        # Get the string pattern corresponding to the format style
        string_pattern = SequenceFileUtil.FORMAT_TO_STRING_PATTERNS.get(format_style)

        # Raise an error if the format style is unsupported
        if string_pattern is None:
            raise ValueError(f"Unsupported format style: {format_style}")

        # Initialize variables for range string, minimum, and maximum numbers
        range_str = None
        start_frame = None
        end_frame = None

        # Check if the format style requires a range and get the sequence range if true
        if format_style.requires_range():
            start_frame, end_frame = SequenceFileUtil.get_sequence_range(frame_numbers)

        # Handle specific format styles that require pre-processing of the string.
        if format_style in (FormatStyle.HASH, FormatStyle.HASH_WITH_RANGE):
            range_str = '#' * padding
        elif format_style.requires_separate_ranges():
            ranges = SequenceFileUtil.get_sequence_ranges(frame_numbers, padding)
            range_str = ','.join(ranges)

        # Construct and return the formatted sequence file path
        return string_pattern.format(
            base_name=base_name,
            padding=padding,
            extension=extension,
            start_frame=start_frame,
            end_frame=end_frame,
            range_str=range_str,
        )

    @staticmethod
    def is_sequence_file(file_name: str) -> bool:
        """Check if a file name follows the sequence file pattern (e.g., 'image.####.ext').

        Args:
            file_name (str): The file name to check.

        Returns:
            bool: True if the file name follows the sequence pattern, False otherwise.
        """
        parts = file_name.split('.')
        if len(parts) < 3:
            return False
        return parts[-2].isdigit()

    @staticmethod
    def detect_sequence_format(sequence_path_format: str) -> Optional['FormatStyle']:
        """Detect the format of the sequence path format.

        Args:
            sequence_path_format (str): The sequence path format.

        Returns:
            Optional[FormatStyle]: The detected format style, or None if no match is found.

        Examples:
            >>> SequenceFileUtil.detect_sequence_format('project/shot/comp_v1.######.exr')
            <FormatStyle.HASH: 'hash'>

            >>> SequenceFileUtil.detect_sequence_format('project/shot/comp_v1.%04d.exr')
            <FormatStyle.PERCENT: 'percent'>

            >>> SequenceFileUtil.detect_sequence_format('project/shot/comp_v1.[001001-001012].exr')
            <FormatStyle.BRACKETS: 'brackets'>

            >>> SequenceFileUtil.detect_sequence_format('project/shot/comp_v1.{1001..1002}.exr')
            <FormatStyle.BRACES: 'braces'>

            >>> SequenceFileUtil.detect_sequence_format('project/shot/comp_v1.[1001,1001-1002,1011-1012].exr')
            <FormatStyle.BRACKETS_SEPARATE_RANGES: 'brackets_separate_ranges'>

            >>> SequenceFileUtil.detect_sequence_format('project/shot/comp_v1.####.exr 0-9')
            <FormatStyle.HASH_WITH_RANGE: 'hash_with_range'>

            >>> SequenceFileUtil.detect_sequence_format('project/shot/comp_v1.%04d.exr 0-9')
            <FormatStyle.PERCENT_WITH_RANGE: 'percent_with_range'>
        """
        return next((style for style, pattern in SequenceFileUtil.FORMAT_TO_REGEX.items() if pattern.match(sequence_path_format)), None)

    @staticmethod
    def construct_file_paths(base_name: str, frames: List[int], extension: str, padding: int = 0) -> List[str]:
        """Construct file paths based on the base name, list of frames, and extension.

        Args:
            base_name (str): The base name of the sequence.
            frames (List[int]): A list of frame numbers.
            extension (str): The file extension.
            padding (int): The number of digits in the frame number.

        Returns:
            List[str]: A list of constructed file paths.
        """
        return [f"{base_name}.{frame:0{padding}}.{extension}" for frame in frames]

    @staticmethod
    def generate_frame_path(sequence_path_format: str, frame: int, format_style: Optional['FormatStyle'] = None) -> str:
        """Generate the file path for a specific frame number based on the given sequence path format and format style.

        Args:
            sequence_path_format (str): The sequence path format.
            frame (int): The frame number to generate the path for.
            format_style (Optional[FormatStyle]): The format style to use, if not provided, it will be detected.

        Returns:
            str: The generated file path for the specified frame.
        """
        # Detect the format style if not provided
        format_style = format_style or SequenceFileUtil.detect_sequence_format(sequence_path_format)
        if not format_style:
            raise ValueError("Unsupported format style")

        # Extract sequence details from the format
        sequence_data = SequenceFileUtil.extract_sequence_details(sequence_path_format, format_style=format_style)
        base_name = sequence_data['base_name']
        extension = sequence_data['extension']
        padding = SequenceFileUtil.get_padding(sequence_data, format_style=format_style)

        if not isinstance(frame, int):
            # Convert frame to integer to maintain consistency in formatting
            frame = int(frame)

        # Construct the file path
        return f"{base_name}.{frame:0{padding}}.{extension}"

    @staticmethod
    def extract_paths_from_format(sequence_path_format: str, sequence_range: Optional[Tuple[int, int]] = None, format_style: Optional['FormatStyle'] = None) -> List[str]:
        """Extract individual file paths from a sequence path format.

        Args:
            sequence_path_format (str): The sequence path format.
            sequence_range (Optional[Tuple[int, int]]): An optional range of sequence numbers (start, end).
            format_style (Optional[FormatStyle]): The format style to use, if not provided, it will be detected.

        Returns:
            List[str]: A list of individual file paths.
        """
        # Detect the format style if not provided
        format_style = format_style or SequenceFileUtil.detect_sequence_format(sequence_path_format)
        if not format_style:
            raise ValueError("Unsupported format style")

        # Initialize file paths list
        file_paths = []

        # Extract details from the sequence path format
        sequence_data = SequenceFileUtil.extract_sequence_details(sequence_path_format, format_style=format_style)
        base_name = sequence_data['base_name']
        extension = sequence_data['extension']
        padding = SequenceFileUtil.get_padding(sequence_data, format_style=format_style)

        # Handle formats that include a range of frames
        if format_style.requires_range():
            start_frame = int(sequence_data['start_frame'])
            end_frame = int(sequence_data['end_frame'])
            file_paths = SequenceFileUtil.construct_file_paths(base_name, range(start_frame, end_frame + 1), extension, padding)
        
        # Handle formats that include separate ranges
        elif format_style.requires_separate_ranges():
            ranges = sequence_data['ranges'].split(',')
            frames = SequenceFileUtil.ranges_to_sequence_numbers(ranges)
            file_paths = SequenceFileUtil.construct_file_paths(base_name, frames, extension, padding)
        
        # Handle other formats
        else:
            # If a sequence range is provided, use it
            if sequence_range:
                start_frame, end_frame = sequence_range
                file_paths = SequenceFileUtil.construct_file_paths(base_name, range(start_frame, end_frame + 1), extension, padding)

            # Otherwise, determine the sequence range from the files on disk
            else:
                # Replace format placeholders with '?' for glob pattern
                if format_style == FormatStyle.HASH:
                    pattern = sequence_path_format.replace('#', '?')
                elif format_style == FormatStyle.PERCENT:
                    pattern = sequence_path_format.replace(f'%0{padding}d', '?' * padding)
                else:
                    raise ValueError("Sequence range must be provided for this format style")

                # Use glob to find matching files
                file_paths = glob.glob(pattern)

        return sorted(file_paths)

    @staticmethod
    def parse_sequence_file_name(file_name: str) -> Tuple[str, str, str]:
        """Parse sequence information from a file name.

        Args:
            file_name (str): The file name to extract information from.

        Returns:
            Tuple[str, str, str]: A tuple containing the base name, sequence number, and extension
                if the file name follows the sequence pattern, otherwise a tuple of Nones.
        """
        parts = file_name.rsplit('.', 2)
        if len(parts) == 3 and parts[1].isdigit():
            return tuple(parts)
        else:
            return None, None, None

    @staticmethod
    def get_sequence_range(sequence_numbers: List[str]) -> Tuple[int, int]:
        """Get the range of sequence numbers from a list of sequence numbers.

        Args:
            sequence_numbers (List[str]): A list of sequence numbers.

        Returns:
            Tuple[int, int]: The minimum and maximum sequence numbers in the list.
        """
        # Convert all sequence numbers to integers and return the minimum and maximum sequence numbers
        sequence_numbers = [int(num) for num in sequence_numbers if num.isdigit()]
        return min(sequence_numbers), max(sequence_numbers)

    @staticmethod
    def get_sequence_ranges(sequence_numbers: List[str], padding: int = 0) -> List[str]:
        """Get the ranges of sequence numbers from a list of sequence numbers.

        Args:
            sequence_numbers (List[str]): A list of sequence numbers.
            padding (int, optional): The number of digits to pad the sequence numbers. If not set, no padding is added.

        Returns:
            List[str]: A list of ranges in the format 'start-end' or individual numbers as strings.

        Examples:
            >>> SequenceFileUtil.get_sequence_ranges(["988", "989", "1003", "1007", "1008", "1006"])
            ['988-989', '1003', '1006-1008']
            >>> SequenceFileUtil.get_sequence_ranges(["999", "1000", "1001", "1002", "1003", "1007", "1008", "1010"], padding=4)
            ['0999-1003', '1007-1008', '1010']
            >>> SequenceFileUtil.get_sequence_ranges([], padding=0)
            []
        """
        # Initialize an empty list to store the resulting ranges
        ranges = []

        # Return early with empty ranges if the input list is empty
        if not sequence_numbers:
            return ranges

        # Sort the sequence numbers, remove duplicates, and add a sentinel value (None) at the end
        sorted_numbers = sorted(set(map(int, sequence_numbers))) + [None]
        range_start = sorted_numbers[0]

        # Iterate through pairs of previous and current numbers in the sorted list
        for previous_num, current_num in zip(sorted_numbers, sorted_numbers[1:]):
            # Continue the loop if the current number is consecutive to the previous number
            if previous_num + 1 == current_num:
                continue

            # If the range start is the same as the previous number, add it as a single number
            # Otherwise, add the range from the start to the previous number
            if range_start == previous_num:
                ranges.append(f'{range_start:0{padding}}')
            else:
                ranges.append(f'{range_start:0{padding}}-{previous_num:0{padding}}')

            # Update the range start to the current number
            range_start = current_num

        return ranges

    @staticmethod
    def ranges_to_sequence_numbers(ranges: List[str]) -> List[int]:
        """Convert ranges in the format 'start-end' or individual numbers as strings to a list of integers.

        Args:
            ranges (List[str]): The ranges to convert.

        Returns:
            List[int]: A list of sequence numbers.
        """
        # Initialize the list to hold sequence numbers
        sequence_numbers = []

        # Process each part of the ranges
        for part in ranges:
            if '-' in part:
                start, end = map(int, part.split('-'))
                sequence_numbers.extend(range(start, end + 1))
            else:
                sequence_numbers.append(int(part))

        # Return the list of sequence numbers
        return sequence_numbers

    @staticmethod
    def convert_to_sequence_format(file_paths: Iterable[str], format_style: 'FormatStyle' = FormatStyle.HASH,
                                   use_unique_padding: bool = True, is_skip_hidden: bool = True
                                  ) -> Generator[str, None, None]:
        """Convert a list of file paths to a list with sequence path formats.

        Args:
            file_paths (Iterable[str]): An iterable of file paths.
            format_style (FormatStyle): The format style to use for padding.
            use_unique_padding (bool): Whether to include distinct formats for each sequence length.
            is_skip_hidden (bool): Whether to skip hidden files.

        Yields:
            Generator[str, None, None]: A generator yielding file paths with sequence path formats.

        Examples:
            >>> file_paths = [
            ... 'project/shot/comp_v1.001001.exr',
            ... 'project/shot/comp_v1.001011.exr',
            ... 'project/shot/comp_v1.001012.exr',
            ... 'project/shot/comp_v1.1001.exr',
            ... 'project/shot/comp_v1.1002.exr',
            ... 'project/shot/comp_v1.1001.jpg',
            ... 'project/shot/comp_v1.1002.jpg',
            ... 'project/shot/comp_v2.1005.jpg',
            ... 'project/shot/reference_image.png',
            ... 'project/shot/notes.txt'
            ... ]
            >>> sorted(SequenceFileUtil.convert_to_sequence_format(file_paths))
            ['project/shot/comp_v1.######.exr', 'project/shot/comp_v1.####.exr', 'project/shot/comp_v1.####.jpg', 'project/shot/comp_v2.1005.jpg', 'project/shot/notes.txt', 'project/shot/reference_image.png']

            >>> sorted(SequenceFileUtil.convert_to_sequence_format(file_paths, use_unique_padding=False))
            ['project/shot/comp_v1.######.exr', 'project/shot/comp_v1.####.jpg', 'project/shot/comp_v2.1005.jpg', 'project/shot/notes.txt', 'project/shot/reference_image.png']

            >>> sorted(SequenceFileUtil.convert_to_sequence_format(file_paths, format_style=FormatStyle.PERCENT))
            ['project/shot/comp_v1.%04d.exr', 'project/shot/comp_v1.%04d.jpg', 'project/shot/comp_v1.%06d.exr', 'project/shot/comp_v2.1005.jpg', 'project/shot/notes.txt', 'project/shot/reference_image.png']

            >>> sorted(SequenceFileUtil.convert_to_sequence_format(file_paths, format_style=FormatStyle.BRACKETS))
            ['project/shot/comp_v1.[001001-001012].exr', 'project/shot/comp_v1.[1001-1002].exr', 'project/shot/comp_v1.[1001-1002].jpg', 'project/shot/comp_v2.1005.jpg', 'project/shot/notes.txt', 'project/shot/reference_image.png']

            >>> sorted(SequenceFileUtil.convert_to_sequence_format(file_paths, format_style=FormatStyle.BRACES))
            ['project/shot/comp_v1.{001001..001012}.exr', 'project/shot/comp_v1.{1001..1002}.exr', 'project/shot/comp_v1.{1001..1002}.jpg', 'project/shot/comp_v2.1005.jpg', 'project/shot/notes.txt', 'project/shot/reference_image.png']

            >>> sorted(SequenceFileUtil.convert_to_sequence_format(file_paths, format_style=FormatStyle.BRACKETS_SEPARATE_RANGES))
            ['project/shot/comp_v1.[001001,001011-001012].exr', 'project/shot/comp_v1.[1001-1002].exr', 'project/shot/comp_v1.[1001-1002].jpg', 'project/shot/comp_v2.1005.jpg', 'project/shot/notes.txt', 'project/shot/reference_image.png']

            >>> sorted(SequenceFileUtil.convert_to_sequence_format(file_paths, format_style=FormatStyle.BRACKETS_SEPARATE_RANGES, use_unique_padding=False))
            ['project/shot/comp_v1.[001001-001002,001011-001012].exr', 'project/shot/comp_v1.[1001-1002].jpg', 'project/shot/comp_v2.1005.jpg', 'project/shot/notes.txt', 'project/shot/reference_image.png']
        """
        # Initialize dictionary to store sequences and results
        sequence_dict: Dict[Tuple[str, str], List[str]] = defaultdict(list)

        # Parse each file path and categorize them into sequences
        for file_path in file_paths:
            # Skip hidden files if is_skip_hidden is True
            if is_skip_hidden and os.path.basename(file_path).startswith('.'):
                continue

            # Extract the base name, sequence number, and extension from the file path
            base_name, sequence_number, extension = SequenceFileUtil.parse_sequence_file_name(file_path)
            if all([base_name, sequence_number, extension]):
                sequence_dict[(base_name, extension)].append(sequence_number)
            # If the file path does not match the sequence pattern, add it directly to the formatted paths
            else:
                yield file_path

        # Process each sequence to generate formatted paths
        for (base_name, extension), sequence_numbers in sequence_dict.items():
            # Handle the case where there is only one frame in the sequence
            if len(sequence_numbers) == 1:
                yield f"{base_name}.{sequence_numbers[0]}.{extension}"
                continue

            # Handle unique padding for each sequence length if specified
            if use_unique_padding:
                # Group sequences by their padding length
                padding_to_sequences = defaultdict(list)
                for seq in sequence_numbers:
                    padding_to_sequences[len(seq)].append(seq)

                # Generate sequence formats for each padding length
                sequence_format_set = {
                    SequenceFileUtil.construct_sequence_file_path(
                        format_style=format_style,
                        base_name=base_name,
                        frame_numbers=sequences,
                        extension=extension,
                        padding=padding,
                    ) for padding, sequences in padding_to_sequences.items()
                }

                yield from sequence_format_set

            else:
                # Generate a single sequence path format for all sequences
                sequence_path_format = SequenceFileUtil.construct_sequence_file_path(
                    format_style=format_style,
                    base_name=base_name,
                    frame_numbers=sequence_numbers, 
                    extension=extension,
                    padding=len(max(sequence_numbers, key=len)),
                )

                yield sequence_path_format

    @staticmethod
    def calculate_total_size(sequence_path_format: str) -> int:
        """Calculate the total size of the files in bytes.

        Args:
            sequence_path_format (str): The path to the sequence file.

        Returns:
            int: The total size of the files in bytes.
        """
        file_paths = SequenceFileUtil.extract_paths_from_format(sequence_path_format)

        return sum(map(os.path.getsize, file_paths))

    @staticmethod
    def extract_frame_number(file_name: str) -> Optional[str]:
        """Extract the frame number from a sequence file name.

        Args:
            file_name (str): The file name to extract the frame number from.

        Returns:
            Optional[str]: The frame number if the file name follows the sequence pattern, otherwise None.
        """
        _, frame_number, _ = SequenceFileUtil.parse_sequence_file_name(file_name)
        return frame_number

    @staticmethod
    def extract_file_info(file_path: str, date_time_format: str = FileUtil.DEFAULT_DATE_TIME_FORMAT) -> Dict[str, str]:
        """Extract detailed information about a file, supporting sequence files.

        Args:
            file_path (str): Path to the file or sequence path format for extracting information.
            date_time_format (str): The format for the last modified timestamp.

        Returns:
            Dict[str, str]: A dictionary containing detailed file information, including:
                - file_name: The base name of the file.
                - file_path: The full path to the file.
                - file_size: File size in a human-readable format or total size for sequences.
                - file_extension: The file extension.
                - last_modified: The last modification timestamp in the specified format.
                - file_owner: The owner of the file.
                - sequence_range: The range of sequence numbers if the file is part of a sequence, as a string in the format 'start-end'.
        """
        # Detect the format style of the sequence file path
        format_style = SequenceFileUtil.detect_sequence_format(file_path)
        # If the format style is not detected, handle it as a regular file and extract info
        if not format_style:
            return FileUtil.extract_file_info(file_path)

        # Extract sequence files from the file path
        sequence_files = SequenceFileUtil.extract_paths_from_format(file_path, format_style=format_style)

        # If there's only one file, handle it as a regular file
        if len(sequence_files) == 1:
            return FileUtil.extract_file_info(file_path, date_time_format)

        try:
            # Calculate the total size of the sequence files
            total_size = sum(map(os.path.getsize, sequence_files))
            latest_file = max(sequence_files, key=lambda f: os.stat(f).st_mtime)

            # Retrieve file statistics and details: file info, owner, last modified time, extension, and formatted size
            file_info = os.stat(latest_file)
            owner = FileUtil.get_file_owner(latest_file)
            modified_time = FileUtil.get_modified_time(file_info, date_time_format=date_time_format)
            extension = FileUtil.get_file_extension(latest_file)
            readable_size = FileUtil.format_size(total_size)

        except FileNotFoundError:
            # NOTE: Handle the case of an invalid symlink file path
            owner = 'N/A'
            modified_time = 'N/A'
            extension = FileUtil.get_file_extension(sequence_files[0])
            readable_size = '0 bytes'

        # Get the sequence ranges from the sequence files
        sequence_numbers = [SequenceFileUtil.extract_frame_number(file_path) for file_path in sequence_files]
        sequence_ranges = SequenceFileUtil.get_sequence_ranges(sequence_numbers)

        # Compile the details into a dictionary
        details = {
            "file_name": os.path.basename(latest_file),
            "file_path": file_path,
            "file_size": readable_size,
            "file_extension": extension,
            "last_modified": modified_time,
            "file_owner": owner,
            "sequence_range": ', '.join(sequence_ranges),
            "sequence_count": len(sequence_numbers),
        }
        return details


class FilePathWalker:

    @staticmethod
    def traverse_directories(root: str, target_depth: Optional[int] = None, is_skip_hidden: bool = True,
                             is_return_relative: bool = False, excluded_folders: List[str] = list(),
                            ) -> Generator[str, None, None]:
        """Traverse directory paths from a root directory, optionally returning relative paths.

        If a target_depth is specified, only directories at that depth are yielded.

        Args:
            root (str): A string specifying the root directory path.
            target_depth (Optional[int]): An optional integer specifying the target depth to yield directories from.
                   If not specified, all directories are yielded.
            is_skip_hidden (bool): A boolean indicating whether to skip hidden directories (those starting with '.').
            is_return_relative (bool): A boolean indicating whether to return relative paths instead of absolute paths.
            excluded_folders (List[str]): A list of folder names to be excluded from the traversal.

        Yields:
            Generator[str, None, None]: Directory paths from the root, either absolute or relative.
            If target_depth is specified, only directories at that depth are yielded.
        """
        # Normalize the root directory path to ensure a consistent format
        root = os.path.normpath(root)
        root_len = len(root) + 1

        def _traverse(directory: str, current_depth: int = 0) -> Generator[str, None, None]:
            """Helper function to recursively traverse directories.

            Args:
                directory (str): The current directory path.
                current_depth (int): The current depth level of traversal.

            Yields:
                Generator[str, None, None]: Directory paths based on the specified criteria.
            """
            # Determine the path to yield (relative or absolute)
            path = directory[root_len:] if is_return_relative else directory

            # Check if the current depth matches the target depth
            if target_depth is None and current_depth:
                yield path
            elif current_depth == target_depth:
                yield path
                return

            # Check if the directory can be accessed, skip if not 
            if not os.access(directory, os.R_OK):
                return

            # Continue traversal for subdirectories
            for entry in os.scandir(directory):
                # Skip non-directories, hidden directories, and excluded folders
                if not entry.is_dir() or FilePathWalker._is_skip_directory(entry.name, is_skip_hidden, excluded_folders):
                    continue

                yield from _traverse(entry.path, current_depth + 1)

        yield from _traverse(root)

    @staticmethod
    def traverse_files(root: Union['Path', str], is_skip_hidden: bool = True, is_return_relative: bool = False,
                       excluded_folders: Optional[List[str]] = None, excluded_extensions: Optional[List[str]] = None,
                       use_sequence_format: bool = False, max_depth: Optional[int] = None,
                       sort_key: Optional[Callable[[os.DirEntry], any]] = None, reverse_sort: bool = False,
                      ) -> Generator[str, None, None]:
        """Traverse file paths from a root directory, optionally returning relative paths and supporting depth limit.

        Args:
            root (str): A string specifying the root directory path.
            is_skip_hidden (bool): A boolean indicating whether to skip hidden files and directories (those starting with '.').
            is_return_relative (bool): A boolean indicating whether to return relative paths instead of absolute paths.
            excluded_folders (List[str]): A list of folder names to be excluded from the traversal.
            excluded_extensions (List[str]): A list of file extensions to be excluded from the traversal.
            use_sequence_format (bool): A boolean indicating whether to convert files to sequence formats.
            max_depth (Optional[int]): Maximum depth of directory traversal. None for no limit.
            sort_key (Optional[Callable[[os.DirEntry], any]]): A callable to extract a sort key from a directory entry.
            reverse_sort (bool): A boolean indicating whether to sort in reverse order. Default is False.

        Yields:
            Generator[str, None, None]: File paths from the root, either absolute or relative.
        """
        # Normalize the root directory path to ensure a consistent format
        root = os.path.normpath(root)
        root_len = len(root) + 1

        def _traverse(directory: str, current_depth: int = 0) -> Generator[str, None, None]:
            """Helper function to recursively traverse files.

            Args:
                directory (str): The current directory path.
                current_depth (int): The current depth of the traversal.

            Yields:
                Generator[str, None, None]: File paths based on the specified criteria.
            """
            # Initialize a list to collect file paths if sequence format is used
            file_paths = []

            # Check if the directory can be accessed, skip if not 
            if not os.access(directory, os.R_OK):
                return

            # Retrieve and optionally sort directory entries
            if sort_key:
                entries = sorted(os.scandir(directory), key=sort_key, reverse=reverse_sort)
            else:
                entries = os.scandir(directory)

            # Iterate over each directory entry
            for entry in entries:
                # Skip hidden files/directories and excluded folders
                if FilePathWalker._is_skip_directory(entry.name, is_skip_hidden, excluded_folders):
                    continue

                if entry.is_dir():
                    # Check if the max depth limit is reached
                    if max_depth is not None and current_depth >= max_depth:
                        continue
                    # Recurse into subdirectories
                    yield from _traverse(entry.path, current_depth + 1)

                else:
                    # Check file extension
                    if FilePathWalker._is_skip_file(entry.name, is_skip_hidden, excluded_extensions):
                        continue

                    # Determine the path to yield (relative or absolute)
                    path = entry.path[root_len:] if is_return_relative else entry.path

                    # If using sequence format, collect file paths to process later
                    if use_sequence_format:
                        file_paths.append(path)
                        continue

                    yield path

            # Convert and yield the formatted file paths if applicable
            if use_sequence_format:
                yield from SequenceFileUtil.convert_to_sequence_format(file_paths)

        yield from _traverse(root)

    @staticmethod
    def traverse_files_walk(search_root: str, is_skip_hidden: bool = True, use_sequence_format: bool = False,
                            excluded_folders: Optional[List[str]] = None, included_extensions: Optional[List[str]] = None,
                            excluded_extensions: Optional[List[str]] = None, max_depth: Optional[int] = None,
                            sort_key: Optional[Callable[[str], any]] = None, reverse_sort: bool = False,
                           ) -> Generator[str, None, None]:
        """Traverse file paths from a root directory using os.walk, optionally converting to sequence formats.

        Args:
            search_root (str): A string specifying the root directory path.
            is_skip_hidden (bool): A boolean indicating whether to skip hidden files and directories (those starting with '.').
            use_sequence_format (bool): A boolean indicating whether to convert files to sequence formats.
            excluded_folders (List[str]): A list of folder names to be excluded from the traversal.
            included_extensions (Optional[List[str]]): A list of file extensions to be included in the traversal.
            excluded_extensions (Optional[List[str]]): A list of file extensions to be excluded from the traversal.
            max_depth (Optional[int]): Maximum depth of directory traversal. None for no limit.
            sort_key (Optional[Callable[[str], Any]]): A callable to specify a key for sorting file names.
            reverse_sort (bool): A boolean indicating whether to sort the file names in reverse order.

        Yields:
            Generator[str, None, None]: File paths from the root. If `use_sequence_format` is True,
                files are converted to sequence formats before yielding.
        """
        # Normalize the root directory path to ensure a consistent format
        search_root = os.path.normpath(search_root)
        root_depth = search_root.count(os.sep)

        # Traverse the root directory
        for root, dir_names, file_names in os.walk(search_root):
            current_depth = root.count(os.sep) - root_depth

            if max_depth is not None and current_depth >= max_depth:
                # If max depth is reached, do not traverse into subdirectories
                dir_names[:] = []
            else:
                # Update the dir_names list in place to skip hidden directories and excluded folders
                dir_names[:] = [
                    dir_name for dir_name in dir_names 
                    if not FilePathWalker._is_skip_directory(
                        dir_name, is_skip_hidden=is_skip_hidden, 
                        excluded_folders=excluded_folders
                    )
                ]

            # Convert file names to sequence format if required
            file_names = SequenceFileUtil.convert_to_sequence_format(file_names) if use_sequence_format else file_names

            # Sort file and directory names if a sort key is provided
            if sort_key:
                dir_names.sort(key=sort_key, reverse=reverse_sort)
                file_names.sort(key=sort_key, reverse=reverse_sort)

            # Yield file paths that are not skipped based on the specified criteria
            yield from (
                # Construct the full path for each file name
                os.path.join(root, file_name) for file_name in file_names
                # Check if the file should be skipped based on the criteria
                if not FilePathWalker._is_skip_file(
                    file_name, is_skip_hidden=is_skip_hidden, 
                    excluded_extensions=excluded_extensions, 
                    included_extensions=included_extensions,
                )
            )

    @staticmethod
    def _is_skip_file(file_name: str, is_skip_hidden: bool = False,
                      excluded_extensions: Optional[List[str]] = None,
                      included_extensions: Optional[List[str]] = None) -> bool:
        """Check if a file should be skipped based on hidden status or extension filters.

        Args:
            file_name (str): The name of the file to check.
            is_skip_hidden (bool): Whether to skip hidden files (starting with '.').
            excluded_extensions (Optional[List[str]]): File extensions to exclude.
            included_extensions (Optional[List[str]]): File extensions to include.

        Returns:
            bool: True if the file should be skipped, False otherwise.
        """
        file_extension = FileUtil.get_file_extension(file_name)
        return (
            (is_skip_hidden and file_name.startswith('.')) or 
            (excluded_extensions and file_extension in excluded_extensions) or
            (included_extensions and file_extension not in included_extensions)
        )

    @staticmethod
    def _is_skip_directory(dir_name: str, is_skip_hidden: bool = False, 
                           excluded_folders: Optional[List[str]] = None) -> bool:
        """Check if a directory should be skipped based on its name.

        Args:
            dir_name (str): The name of the directory to check.
            is_skip_hidden (bool): Whether to skip hidden directories (starting with '.').
            excluded_folders (Optional[List[str]]): Specific folder names to exclude.

        Returns:
            bool: True if the directory should be skipped, False otherwise.
        """
        return (
            (is_skip_hidden and dir_name.startswith('.')) or
            (excluded_folders and dir_name in excluded_folders)
        )


class FilePatternQuery:
    """Query files matching a specified pattern.
    """

    # Initialization and Setup
    # ------------------------
    def __init__(self, pattern: str) -> None:
        """Initialize a FilePatternQuery instance.

        Args:
            pattern (str): The pattern to match files with.
        """
        # Store the arguments
        self.pattern = pattern

    # Public Methods
    # --------------
    def format_for_glob(self, values: List[str]) -> str:
        """Format a string with named placeholders for use with glob.iglob.
        
        Args:
            values (List[str]): Arguments to fill the placeholders, provided by index.
        
        Returns:
            str: The formatted string prepared for glob search.
        """
        # Use str.format with the modified pattern
        return PathPattern.format_by_index(self.pattern, values)

    def extract_variables(self, path: str) -> Dict[str, str]:
        """Extract variables from a given path based on a specified string pattern.

        Args:
            path: The path string from which to extract variable values.

        Returns:
            Dict[str, str]: A dictionary of variable names and their corresponding values if the path matches the pattern,
                or an empty dictionary if there is no match.
        """
        return PathPattern.extract_variables(self._regex_pattern, path, is_regex=True)

    def construct_search_paths(self, filters: Dict[str, List[str]] = None) -> Generator[str, None, None]:
        """Construct and yield search paths based on provided filters and the pattern.

        Args:
            filters (Dict[str, List[str]], optional): A dictionary where keys are field names extracted from the pattern, 
                and values are lists of strings that specify the filter values for each field. Defaults to None.

        Yields:
            Generator[str, None, None]: Paths to files that match the constructed search patterns.
        """
        if not filters:
            # No filters provided, short-circuit to wildcard search
            wildcard_values = ['*'] * len(re.findall(PathPattern.VARIABLE_PLACEHOLDER_PATTERN, self.pattern))
            yield from glob.iglob(self.format_for_glob(wildcard_values))
            return

        # Construct combinations using specific filter values or wildcard '*' for each field
        values_combinations = [filters[field] if field in filters and filters[field] else ['*'] for field in self.fields]

        # Generate all possible paths based on combinations of field values
        all_value_combinations = product(*values_combinations)
        # Using map to apply format for glob for each combination of values
        search_paths = map(self.format_for_glob, all_value_combinations)

        # Iterate through search paths and yield matching files
        for search_path in search_paths:
            yield from glob.iglob(search_path)

    def query_files(self, filters: Optional[Dict[str, List[str]]] = None, use_sequence_format: bool = False, 
                    excluded_extensions: Optional[List[str]] = None, is_skip_hidden: bool = True
                   ) -> Generator[Dict[str, str], None, None]:
        """Query files matching the pattern and filters, returning their info.

        Args:
            filters (Dict[str, List[str]]): Filters for querying files.
            use_sequence_format (bool): Whether to use the sequence format. Defaults to False.
            excluded_extensions (List[str]): A list of file extensions to be excluded from the results.
            is_skip_hidden (bool): Whether to skip hidden files. Defaults to True.

        Yields:
            Generator[Dict[str, str], None, None]: File information for each matching file.
        """
        # Construct search paths based on the filters
        search_paths = self.construct_search_paths(filters)

        # Iterate over the paths and extract file information
        for search_path in search_paths:
            file_paths = FilePathWalker.traverse_files(
                search_path, use_sequence_format=use_sequence_format, 
                excluded_extensions=excluded_extensions, is_skip_hidden=is_skip_hidden
            )
            for file_path in file_paths:
                file_path = os.path.normpath(file_path)

                # Extract file information dict from the path
                file_info = SequenceFileUtil.extract_file_info(file_path) if use_sequence_format else FileUtil.extract_file_info(file_path)

                # Extract variables from the path based on the pattern and merge it with file information
                data_dict = self.extract_variables(file_path)
                data_dict.update(file_info)

                yield data_dict

    # Class Properties
    # ----------------
    @property
    def fields(self) -> List[str]:
        """Return the list of fields extracted from the pattern.
        """
        return PathPattern.extract_variable_names(self._pattern) + FileUtil.FILE_INFO_FIELDS

    @property
    def pattern(self) -> str:
        """Return the pattern used to query files.
        """
        return self._pattern
    
    @pattern.setter
    def pattern(self, value: str) -> None:
        """Set the pattern used to query files.
        """
        # Normalize the pattern and store the regex pattern for matching files
        self._pattern = os.path.normpath(value) + '/'
        self._regex_pattern = PathPattern.convert_pattern_to_regex(self._pattern)
    
    @property
    def regex_pattern(self) -> str:
        """Return the regular expression pattern used to query files.
        """
        return self._regex_pattern


if __name__ == '__main__':
    import doctest
    doctest.testmod()
