import logging
import os
import shutil
from typing import List, Dict, Tuple, Optional
import re

logger = logging.getLogger("mac_rename")

# Constants
FLOOR_TYPES = ["Keller", "EG", "1. OG", "2. OG", "3. OG"]
EXTERNAL_TYPES = ["Außenansicht", "Umgebung", "Ausblick", "Grundstück", "Garten", "Treppenhaus"]

def sanitize_filename(name: str) -> str:
    """
    Sanitize a string to be safe for use in filenames.
    
    Args:
        name (str): The input string to sanitize.
    
    Returns:
        str: A sanitized string safe for filenames.
    """
    # Replace problematic characters with underscores
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
    # Remove leading/trailing whitespace and dots
    sanitized = sanitized.strip(' .')
    # Replace multiple consecutive spaces/underscores with single underscore
    sanitized = re.sub(r'[_\s]+', '_', sanitized)
    return sanitized if sanitized else "Custom_Room"

def get_drives() -> List[str]:
    """
    Get list of available drives (Desktop + external volumes).
    
    Returns:
        List[str]: List of drive names.
    """
    try:
        logger.debug("Scanning for available drives")
        drives = ["Desktop"]
        if os.path.exists("/Volumes"):
            external_drives = [d for d in os.listdir("/Volumes") if d != "Macintosh HD"]
            drives.extend(sorted(external_drives))
        logger.debug(f"Found drives: {drives}")
        return drives
    except Exception as e:
        logger.error(f"Error scanning drives: {str(e)}")
        return ["Desktop"]

def get_folders_with_arw(drive: str) -> List[str]:
    """
    Get list of folders containing .ARW files for a given drive.
    
    Args:
        drive (str): Drive name ("Desktop" or external drive name).
    
    Returns:
        List[str]: List of folder paths containing .ARW files.
    """
    logger.debug(f"Scanning for folders with ARW files on drive: {drive}")
    
    # Determine the base path
    if drive == "Desktop":
        base_path = os.path.expanduser("~/Desktop")
        logger.info(f"Scanning Desktop: {base_path}")
    else:
        base_path = f"/Volumes/{drive}"
        logger.info(f"Scanning drive: {base_path}")
    
    if not os.path.exists(base_path):
        logger.warning(f"Drive path does not exist: {base_path}")
        return []
    
    parent_folders = set()
    for root, _, files in os.walk(base_path):
        if "EXPORT" in root:
            continue
        if any(file.endswith(".ARW") for file in files):
            logger.debug(f"Found folder with ARW files: {root}")
            parent_folders.add(root)
    
    result = sorted(list(parent_folders))
    logger.info(f"Found {len(result)} folders with ARW files")
    return result

def bracket_files(folder: str) -> List[List[str]]:
    """
    Identify bracketed sets of .ARW files based on timestamps.
    Only return brackets with exactly 3 files.

    Args:
        folder (str): Path to the folder.

    Returns:
        List[List[str]]: List of bracketed file groups.
    """
    logger.info(f"Identifying bracketed sets in: {folder}")
    files = [f for f in os.listdir(folder) if f.endswith(".ARW")]
    logger.debug(f"Found {len(files)} ARW files")
    
    if not files:
        logger.warning("No ARW files found in folder")
        return []

    # Get file paths and timestamps
    file_info = [(f, os.path.getmtime(os.path.join(folder, f))) for f in files]
    file_info.sort(key=lambda x: x[1])  # Sort by timestamp
    logger.debug("Sorted files by timestamp")

    brackets = []
    current_bracket = []
    invalid_brackets = 0
    
    for file, timestamp in file_info:
        if not current_bracket:
            current_bracket.append(file)
        else:
            last_time = os.path.getmtime(os.path.join(folder, current_bracket[-1]))
            if timestamp - last_time < 30:  # 30-second threshold for bracketing
                current_bracket.append(file)
            else:
                # End of current bracket
                if len(current_bracket) == 3:
                    logger.debug(f"Found valid bracket: {current_bracket}")
                    brackets.append(current_bracket)
                else:
                    logger.warning(f"Invalid bracket with {len(current_bracket)} files: {', '.join(current_bracket)}")
                    invalid_brackets += 1
                current_bracket = [file]  # Start a new bracket
            
            # If we've reached 3 files, add the bracket and start fresh
            if len(current_bracket) == 3:
                logger.debug(f"Found valid bracket: {current_bracket}")
                brackets.append(current_bracket)
                current_bracket = []
    
    # Handle any remaining files
    if current_bracket:
        if len(current_bracket) == 3:
            logger.debug(f"Found valid bracket: {current_bracket}")
            brackets.append(current_bracket)
        else:
            logger.warning(f"Discarding final incomplete bracket with {len(current_bracket)} files: {', '.join(current_bracket)}")
            invalid_brackets += 1
    
    if not brackets:
        logger.error("No valid bracketed sets identified")
    elif invalid_brackets > 0:
        logger.warning(f"Found {invalid_brackets} incomplete bracketed sets")
    
    logger.info(f"Identified {len(brackets)} valid bracketed sets")
    # Log the full list of valid brackets at DEBUG level
    if brackets:
        logger.debug("Full list of valid brackets:")
        for i, bracket in enumerate(brackets, 1):
            logger.debug(f"Bracket {i}: {', '.join(bracket)}")
    
    return brackets

def move_and_rename_images(
    folder: str, 
    classifications: Dict[str, List[Tuple[Optional[str], List[str]]]]
) -> Dict[str, any]:
    """
    Rename and move images to the EXPORT folder.

    Args:
        folder (str): Original folder path.
        classifications (Dict): Mapping of types to (room_name, bracket) tuples.

    Returns:
        Dict: Status information about the operation.
    """
    export_folder = os.path.join(folder, "EXPORT")
    
    # Remove existing export folder if present
    if os.path.exists(export_folder):
        logger.info(f"Removing existing export folder: {export_folder}")
        shutil.rmtree(export_folder, ignore_errors=True)
    
    logger.info(f"Creating export folder: {export_folder}")
    os.makedirs(export_folder, exist_ok=True)

    total_groups = sum(len(entries) for entries in classifications.values())
    logger.info(f"About to process {total_groups} bracketed groups")

    total_files = sum(len(entries) * 3 for entries in classifications.values())
    file_count = 0
    errors = []

    for type_val, entries in classifications.items():
        logger.info(f"Processing {len(entries)} entries of type: {type_val}")
        
        if type_val in FLOOR_TYPES:
            # Group by room name for floors
            room_groups: Dict[str, List[List[str]]] = {}
            for room_name, files in entries:
                if room_name:  # Should always be true for FLOOR_TYPES
                    if room_name not in room_groups:
                        room_groups[room_name] = []
                    room_groups[room_name].append(files)

            # Rename files within each room group
            for room_name, file_groups in room_groups.items():
                logger.info(f"Processing {len(file_groups)} sets for room: {room_name}")
                for group_idx, files in enumerate(file_groups, 1):
                    for shot_idx, file in enumerate(files, 1):
                        new_name = f"{type_val}_{room_name}_{group_idx}_{shot_idx}.ARW"
                        src = os.path.join(folder, file)
                        dst = os.path.join(export_folder, new_name)
                        try:
                            logger.debug(f"Copying: {src} -> {dst}")
                            shutil.copy2(src, dst)
                            file_count += 1
                        except Exception as e:
                            error_msg = f"Error copying {file}: {str(e)}"
                            logger.error(error_msg)
                            errors.append(error_msg)
        else:
            # External types: no room name
            logger.info(f"Processing {len(entries)} sets for external type: {type_val}")
            for group_idx, (_, files) in enumerate(entries, 1):
                for shot_idx, file in enumerate(files, 1):
                    new_name = f"{type_val}_{group_idx}_{shot_idx}.ARW"
                    src = os.path.join(folder, file)
                    dst = os.path.join(export_folder, new_name)
                    try:
                        logger.debug(f"Copying: {src} -> {dst}")
                        shutil.copy2(src, dst)
                        file_count += 1
                    except Exception as e:
                        error_msg = f"Error copying {file}: {str(e)}"
                        logger.error(error_msg)
                        errors.append(error_msg)

    logger.info(f"Successfully processed {file_count} files")
    
    return {
        "total_files": file_count,
        "errors": errors,
        "success": len(errors) == 0
    }
