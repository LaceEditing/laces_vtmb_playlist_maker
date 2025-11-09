"""
Manual radio segment database with exact timestamps from analysis
"""

def parse_timestamp(timestamp_str):
    """Convert M:SS.CC format to seconds (float)"""
    if ':' not in timestamp_str:
        return float(timestamp_str)

    parts = timestamp_str.split(':')
    minutes = int(parts[0])
    seconds = float(parts[1])
    return minutes * 60 + seconds


# Manual segment database with exact timestamps
# Format: loop_name -> [(start_time_str, end_time_str, label, segment_type)]
MANUAL_SEGMENTS = {
    'radio_loop_1': [
        ('0:00', '2:49.09', 'Deb 1', 'dialogue'),
        ('2:49.28', '3:47.06', 'Friggen Chicken', 'commercial'),
        ('3:47.25', '4:41.25', 'ATM Machine', 'commercial'),
        ('4:41.44', '5:13.09', 'Yellow Teeth', 'commercial'),
        ('5:13.28', '6:10.18', 'Robert Thorn', 'political'),
        ('6:10.37', None, 'That One Movie', 'commercial'),  # None = end of file
    ],
    'radio_loop_2': [
        ('0:00', '2:14.26', 'Deb 2', 'dialogue'),
        ('2:14.45', '2:45.15', 'Butter', 'commercial'),
        ('2:45.34', '3:17.19', 'ED Pill', 'commercial'),
        ('3:17.38', '4:10.28', 'Space Burger', 'commercial'),
        ('4:10.47', '5:08.11', 'Robert Thorn 2', 'political'),
        ('5:08.30', '5:58.10', 'Guns', 'commercial'),
        ('5:58.29', None, 'American Ale', 'commercial'),
    ],
    'radio_loop_3': [
        ('0:00', '4:33.08', 'Deb 3', 'dialogue'),
        ('4:33.27', '5:18.02', 'Sex Change', 'commercial'),
        ('5:18.21', '6:03.12', 'Internet', 'commercial'),
        ('6:03.31', '7:07.05', 'Action Movie', 'commercial'),
        ('7:07.24', None, 'Reverse Poindexter', 'commercial'),
    ],
    'radio_loop_4': [
        ('0:00', '3:04.23', 'Deb 4', 'dialogue'),
        ('3:04.42', '4:01.28', 'Robert Thorn 3', 'political'),
        ('4:01.47', '4:56.18', 'Virtual Meeting', 'commercial'),
        ('4:56.37', '5:57.17', 'Office Bots', 'commercial'),
        ('5:57.36', None, 'Frankenstein', 'commercial'),
    ],
    'radio_loop_5': [
        ('0:00', '12:36.19', 'Radio Content (Non-editable)', 'radio_content'),
        ('12:36.38', '16:58.25', 'A Smaller God', 'music'),
        ('16:58.44', None, 'Licensed Track 2', 'music'),
    ],
}


def get_manual_segments(loop_name, total_duration_ms):
    """
    Get manually defined segments for a radio loop

    Args:
        loop_name: e.g., 'radio_loop_1'
        total_duration_ms: Total duration of the audio file in milliseconds

    Returns:
        List of dicts with start_sec, end_sec, duration_sec, start_ms, end_ms, label, segment_type
    """
    if loop_name not in MANUAL_SEGMENTS:
        return None

    segments = []
    raw_segments = MANUAL_SEGMENTS[loop_name]

    for i, (start_str, end_str, label, seg_type) in enumerate(raw_segments):
        start_sec = parse_timestamp(start_str)

        # If end is None, use total duration
        if end_str is None:
            end_sec = total_duration_ms / 1000.0
        else:
            end_sec = parse_timestamp(end_str)

        duration_sec = end_sec - start_sec
        start_ms = int(start_sec * 1000)
        end_ms = int(end_sec * 1000)

        segments.append({
            'index': i,
            'start_sec': start_sec,
            'end_sec': end_sec,
            'duration_sec': duration_sec,
            'start_ms': start_ms,
            'end_ms': end_ms,
            'label': label,
            'segment_type': seg_type
        })

    return segments
