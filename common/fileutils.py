import os
import json


def load_json_file(file_path: str):
    try:
        with open(os.path.join(os.path.dirname(__file__), file_path), 'r', encoding='utf-8') as f:
            json_dict = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"JSON file not found: {file_path}")
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON format in file: {file_path}")
    return json_dict


