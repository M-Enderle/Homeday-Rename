import logging
import rawpy
from PIL import Image, ImageDraw
import concurrent.futures
import base64
from io import BytesIO
from typing import List
import os
import time

logger = logging.getLogger("mac_rename")

def load_raw(file_path: str) -> Image.Image:
    """
    Load and process a RAW file into a thumbnail with rounded corners.

    Args:
        file_path (str): Path to the RAW file.

    Returns:
        Image.Image: Processed PIL image.
    """
    try:
        logger.debug(f"Loading RAW file: {file_path}")
        with rawpy.imread(file_path) as raw:
            rgb = raw.postprocess()
        image = Image.fromarray(rgb)
        image.thumbnail((300, 200))

        mask = Image.new("L", image.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle([(0, 0), image.size], radius=15, fill=255)
        image.putalpha(mask)
        
        logger.debug(f"Successfully loaded and processed RAW file: {file_path}")
        return image
    except Exception as e:
        logger.error(f"Error loading RAW file {file_path}: {str(e)}")
        raise

def load_preview_image(file_path: str) -> str:
    """
    Load a RAW file and return it as base64-encoded PNG.

    Args:
        file_path (str): Path to the RAW file.

    Returns:
        str: Base64-encoded PNG image.
    """
    try:
        start = time.time()
        image = load_raw(file_path)
        
        # Convert to PNG and encode as base64
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        base64_image = base64.b64encode(buffer.getvalue()).decode()
        
        elapsed = time.time() - start
        logger.debug(f"Successfully encoded preview for: {os.path.basename(file_path)} ({elapsed:.2f}s)")
        return f"data:image/png;base64,{base64_image}"
    except Exception as e:
        logger.error(f"Error processing preview image {file_path}: {str(e)}")
        raise

def load_previews_threaded(folder: str, bracketed_files: List[List[str]]) -> List[str]:
    """
    Load previews of images using threading for efficiency.

    Args:
        folder (str): Path to the folder containing the images.
        bracketed_files (List[List[str]]): List of bracketed file groups.

    Returns:
        List[str]: List of base64-encoded preview images.
    """
    logger.debug(f"Loading previews for {len(bracketed_files)} bracketed sets")
    
    file_paths = [os.path.join(folder, bracket[1]) for bracket in bracketed_files]  # Use middle image

    previews = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        previews = list(executor.map(load_preview_image, file_paths))
    
    logger.debug(f"Successfully loaded {len(previews)} previews")
    return previews
