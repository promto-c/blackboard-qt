# Type Checking Imports
# ---------------------
from typing import TYPE_CHECKING, Dict, List
if TYPE_CHECKING:
    from numbers import Number

# Standard Imports
# ----------------
import glob, re

# Local imports
# -------------
from blackboard.utils.file_path_utils import FormatStyle, SequenceFileUtil


# Class Definitions
# -----------------
# TODO: Add support more path format
class PathSequence:
    def __init__(self, path: str):
        self.path = str(path)
        self.name_part, self.frame_padding, self.extension = SequenceFileUtil.parse_sequence_file_name(self.path, check_digit=False)
        self.padding_length = len(self.frame_padding)

    def get_frame_range(self):
        # Use glob to get all matching filenames
        matching_files = sorted(glob.glob(self.path.replace("#", "*")))

        if not matching_files:
            return None, None

        # Extracting frame numbers from the first and last filenames
        first_frame = int(matching_files[0].split('.')[-2])
        last_frame = int(matching_files[-1].split('.')[-2])
        
        return first_frame, last_frame
    
    def get_frame_count_from_range(self):
        first_frame, last_frame = self.get_frame_range()

        if first_frame is None or last_frame is None:
            return 0
        
        return last_frame - first_frame + 1
    
    def get_frame_path(self, frame_number: 'Number'):
        return f'{self.name_part}.{int(frame_number):0{self.padding_length}}.{self.extension}'

    def __str__(self):
        return f"Name Part: {self.name_part}, Frame Padding: {self.frame_padding} (Length: {self.padding_length}), Extension: {self.extension}"


if __name__ == '__main__':
    import doctest
    doctest.testmod()
