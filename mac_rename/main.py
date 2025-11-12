import streamlit as st
import os
import sys
from typing import List, Optional, Dict, Tuple
import rawpy
from PIL import Image, ImageDraw
import concurrent.futures
import shutil
from tqdm import tqdm
from rich.console import Console
from rich.logging import RichHandler
import logging

# Set fixed log level - change this value to adjust logging verbosity
# Options: "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"
LOG_LEVEL = "DEBUG"

# Configure Rich logging
console = Console()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True)]
)
# Create logger
logger = logging.getLogger("mac_rename")

# Constants
DRIVES = [""] + ["Desktop"] + [d for d in os.listdir("/Volumes") if d != "Macintosh HD"]
FLOOR_TYPES = ["Keller", "EG", "1. OG", "2. OG", "3. OG"]
EXTERNAL_TYPES = ["Außenansicht", "Umgebung", "Ausblick", "Grundstück", "Garten", "Treppenhaus"]
TYPES = FLOOR_TYPES + EXTERNAL_TYPES + ["SKIP"]
ROOM_NAMES = [
    "Ankleidezimmer", "Badezimmer", "Balkon", "Büro", "Dachboden", "Dachterrasse",
    "Elternschlafzimmer", "Esszimmer", "Fitnessraum", "Gästezimmer", "Heizungsanlage",
    "Kinderzimmer", "Küche", "Loggia", "Partykeller", "Pool", "Sauna", "Schlafzimmer",
    "Terrasse", "Toilette", "Wintergarten", "Zimmer", "Wohnzimmer", "Diele", "Custom"
]

def sanitize_filename(name: str) -> str:
    """
    Sanitize a string to be safe for use in filenames.
    
    Args:
        name (str): The input string to sanitize.
    
    Returns:
        str: A sanitized string safe for filenames.
    """
    # Replace problematic characters with underscores
    import re
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
    # Remove leading/trailing whitespace and dots
    sanitized = sanitized.strip(' .')
    # Replace multiple consecutive spaces/underscores with single underscore
    sanitized = re.sub(r'[_\s]+', '_', sanitized)
    return sanitized if sanitized else "Custom_Room"

def main():
    logger.info("Starting RAW-Bracketing Rename application")
    st.title("RAW-Bracketing Rename")

    st.divider()

    folder = folder_select()
    if not folder:
        logger.warning("No folder selected")
        return
    
    logger.info(f"Processing folder: {folder}")
    bracketed_files = bracket_files(folder)
    if not bracketed_files:
        logger.error("No valid bracketed sets found in the selected folder")
        st.error("No valid bracketed sets found in the selected folder.")
        return
    
    # Validate that all brackets have exactly 3 files
    invalid_brackets = [b for b in bracketed_files if len(b) != 3]
    if invalid_brackets:
        logger.error(f"Found {len(invalid_brackets)} bracketed sets that don't have exactly 3 files")
        st.error(f"Found {len(invalid_brackets)} bracketed sets that don't have exactly 3 files. All bracketed sets must have exactly 3 files.")
        return
    
    logger.info(f"Loading previews for {len(bracketed_files)} bracketed sets")
    previews = load_previews(folder, bracketed_files)
    
    st.divider()

    logger.debug("Displaying images for user selection")
    new_filenames = display_images(bracketed_files, previews)
    if not new_filenames:
        logger.warning("Required fields not filled out")
        st.error("Please fill out all required fields before proceeding.")
        return

    # Validate that all brackets in new_filenames have exactly 3 files
    for type_val, entries in new_filenames.items():
        for room_name, files in entries:
            if len(files) != 3:
                logger.error(f"Internal error: Found a bracket with {len(files)} files instead of 3")
                st.error(f"Internal error: Found a bracket with {len(files)} files instead of 3. Please report this issue.")
                return

    st.divider()

    if st.button("Apply", use_container_width=True):
        logger.info("Starting file rename and move operation")
        move_images(folder, new_filenames)
        logger.info("File operations completed successfully")
        st.success("Images renamed and moved successfully!")

@st.cache_data
def load_previews(folder: str, bracketed_files: List[List[str]]) -> List[Image.Image]:
    """
    Load previews of images using threading for efficiency.

    Args:
        folder (str): Path to the folder containing the images.
        bracketed_files (List[List[str]]): List of bracketed file groups.

    Returns:
        List[Image.Image]: List of image previews.
    """
    logger.debug(f"Loading previews for {len(bracketed_files)} bracketed sets")
    
    def process_file(file_path: str) -> Image.Image:
        logger.debug(f"Processing preview for: {os.path.basename(file_path)}")
        return load_raw(file_path)

    image_previews = []
    file_paths = [os.path.join(folder, bracket[1]) for bracket in bracketed_files]  # Use middle image

    with st.spinner("Loading previews..."):
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            image_previews = list(executor.map(process_file, file_paths))
    
    logger.debug(f"Successfully loaded {len(image_previews)} previews")
    return image_previews

def folder_select() -> Optional[str]:
    """
    Allow user to select a drive and folder containing .ARW files.

    Returns:
        Optional[str]: Selected folder path or None if not selected.
    """
    logger.debug("Starting folder selection")
    cols = st.columns((2, 5))
    drive = cols[0].selectbox("Select a Drive", DRIVES, help="Choose Desktop or an external drive.")
    if not drive:
        return None
    
    # Determine the base path based on the selected drive
    if drive == "Desktop":
        base_path = os.path.expanduser("~/Desktop")
        logger.info(f"Scanning Desktop: {base_path}")
    else:
        base_path = f"/Volumes/{drive}"
        logger.info(f"Scanning drive: {base_path}")
    
    parent_folders = set()
    for root, _, files in os.walk(base_path):
        if "EXPORT" in root:
            continue
        if any(file.endswith(".ARW") for file in files):
            logger.debug(f"Found folder with ARW files: {root}")
            parent_folders.add(root)

    if not parent_folders:
        location_name = "Desktop" if drive == "Desktop" else f"/Volumes/{drive}"
        logger.warning(f"No folders with .ARW files found in {location_name}")
        st.warning(f"No folders with .ARW files found in {location_name}.")
        return None

    folder_options = [""] + sorted(parent_folders)
    folder = cols[1].selectbox("Select a Folder", folder_options, help="Choose a folder with RAW files.")
    if folder:
        logger.info(f"Selected folder: {folder}")
    return folder if folder else None

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
            if timestamp - last_time < 30:  # 60-second threshold for bracketing
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
        st.warning("Could not identify any bracketed sets with exactly 3 files. Files may not be sequential.")
    elif invalid_brackets > 0:
        logger.warning(f"Found {invalid_brackets} incomplete bracketed sets")
        st.warning(f"Found {invalid_brackets} incomplete bracketed sets that don't have exactly 3 files. These have been ignored.")
    
    logger.info(f"Identified {len(brackets)} valid bracketed sets")
    # Log the full list of valid brackets at DEBUG level
    if brackets:
        logger.debug("Full list of valid brackets:")
        for i, bracket in enumerate(brackets, 1):
            logger.debug(f"Bracket {i}: {', '.join(bracket)}")
    
    return brackets

def load_raw(file: str) -> Image.Image:
    """
    Load and process a RAW file into a thumbnail with rounded corners.

    Args:
        file (str): Path to the RAW file.

    Returns:
        Image.Image: Processed PIL image.
    """
    try:
        with rawpy.imread(file) as raw:
            rgb = raw.postprocess()
        image = Image.fromarray(rgb)
        image.thumbnail((300, 200))

        mask = Image.new("L", image.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle([(0, 0), image.size], radius=15, fill=255)
        image.putalpha(mask)
        
        return image
    except Exception as e:
        logger.error(f"Error loading RAW file {file}: {str(e)}")
        raise

def display_images(bracketed_files: List[List[str]], previews: List[Image.Image]) -> Optional[Dict[str, List[Tuple[Optional[str], List[str]]]]]:
    """
    Display images with type and conditional room name selection.

    Args:
        bracketed_files (List[List[str]]): List of bracketed file groups.
        previews (List[Image.Image]): List of image previews.

    Returns:
        Optional[Dict]: New filename structure or None if invalid.
    """
    logger.info(f"Displaying {len(previews)} images for user classification")
    new_filenames: Dict[str, List[Tuple[Optional[str], List[str]]]] = {t: [] for t in TYPES}
    error = False

    cols_per_row = 4
    for row in range((len(bracketed_files) + cols_per_row - 1) // cols_per_row):
        cols = st.columns(cols_per_row)
        for col_idx, col in enumerate(cols):
            idx = row * cols_per_row + col_idx
            if idx >= len(bracketed_files):
                break
            col.image(previews[idx], use_container_width=True)

            # Add copy button
            if idx > 0:
                copy_key = f"copy_{idx}"
                if col.button("Copy", key=copy_key, use_container_width=True):
                    # Copy the values from the previous image
                    prev_type_key = f"type_{idx - 1}"
                    prev_room_key = f"room_{idx - 1}"
                    prev_custom_room_key = f"custom_room_{idx - 1}"
                    
                    if prev_type_key in st.session_state:
                        st.session_state[f"type_{idx}"] = st.session_state[prev_type_key]
                    if prev_room_key in st.session_state:
                        st.session_state[f"room_{idx}"] = st.session_state[prev_room_key]
                    if prev_custom_room_key in st.session_state:
                        st.session_state[f"custom_room_{idx}"] = st.session_state[prev_custom_room_key]

                    logger.debug(f"Copied values from image {idx-1} to image {idx}")
                    st.rerun()

            # First select box: Type (Keller to 3. OG, Außenansicht)
            type_key = f"type_{idx}"
            type_val = col.selectbox("Select Type", [""] + TYPES, key=type_key, label_visibility="collapsed")
            if not type_val:
                logger.debug(f"No type selected for image {idx}")
                error = True
                continue

            # Second select box: Room name (only for floor types)
            room_name: Optional[str] = None
            if type_val in FLOOR_TYPES:
                room_key = f"room_{idx}"
                room_val = col.selectbox("Select Room", [""] + ROOM_NAMES, key=room_key, label_visibility="collapsed")
                if not room_val:
                    logger.debug(f"No room selected for floor type image {idx}")
                    error = True
                    continue
                
                # If "Custom" is selected, show text input
                if room_val == "Custom":
                    custom_room_key = f"custom_room_{idx}"
                    custom_room_val = col.text_input("Enter custom room name", key=custom_room_key, label_visibility="collapsed", placeholder="Enter room name...")
                    if not custom_room_val:
                        logger.debug(f"No custom room name entered for image {idx}")
                        error = True
                        continue
                    room_name = sanitize_filename(custom_room_val)
                    logger.debug(f"Custom room name '{custom_room_val}' sanitized to '{room_name}'")
                else:
                    room_name = room_val

            # Store the selection
            if type_val and type_val != "SKIP":
                logger.debug(f"Image {idx} classified as {type_val}{' - ' + room_name if room_name else ''}")
                new_filenames[type_val].append((room_name, bracketed_files[idx]))

    if error:
        logger.warning("Some required fields are not filled out")
        return None
    
    logger.info("All images successfully classified")
    return new_filenames

def move_images(folder: str, new_filenames: Dict[str, List[Tuple[Optional[str], List[str]]]]):
    """
    Rename and move images to the EXPORT folder.

    Args:
        folder (str): Original folder path.
        new_filenames (Dict): Mapping of types to (name, bracket) tuples.
    """
    export_folder = os.path.join(folder, "EXPORT")
    if os.path.exists(export_folder):
        logger.info(f"Removing existing export folder: {export_folder}")
        shutil.rmtree(export_folder, ignore_errors=True)
    
    logger.info(f"Creating export folder: {export_folder}")
    os.makedirs(export_folder, exist_ok=True)

    total_groups = sum(len(entries) for entries in new_filenames.values())
    logger.info(f"About to process {total_groups} bracketed groups")

    with st.spinner("Renaming and moving images..."):
        total_files = sum(len(entries) * 3 for entries in new_filenames.values())  # Each entry has 3 files
        progress_bar = st.progress(0)
        file_count = 0

        for type_val, entries in new_filenames.items():
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
                    for group_idx, files in enumerate(file_groups, 1):  # Fix: Iterate over file_groups directly
                        for shot_idx, file in enumerate(files, 1):
                            new_name = f"{type_val}_{room_name}_{group_idx}_{shot_idx}.ARW"
                            src = os.path.join(folder, file)
                            dst = os.path.join(export_folder, new_name)
                            logger.debug(f"Copying: {src} -> {dst}")
                            shutil.copy2(src, dst)
                            file_count += 1
                            progress_value = min(file_count / total_files, 1.0)  # Clamp progress value to 1.0
                            progress_bar.progress(progress_value)
            else:
                # External types: no room name
                logger.info(f"Processing {len(entries)} sets for external type: {type_val}")
                for group_idx, (_, files) in enumerate(entries, 1):
                    for shot_idx, file in enumerate(files, 1):
                        new_name = f"{type_val}_{group_idx}_{shot_idx}.ARW"
                        src = os.path.join(folder, file)
                        dst = os.path.join(export_folder, new_name)
                        logger.debug(f"Copying: {src} -> {dst}")
                        shutil.copy2(src, dst)
                        file_count += 1
                        progress_value = min(file_count / total_files, 1.0)  # Clamp progress value to 1.0
                        progress_bar.progress(progress_value)

        logger.info(f"Successfully processed {file_count} files")

if __name__ == "__main__":
    logger.debug(f"Starting application with log level: {LOG_LEVEL}")
    main()