import logging
import time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional, Tuple
from ..core import file_manager, image_processor

logger = logging.getLogger("mac_rename")

router = APIRouter(prefix="/api", tags=["api"])

# Constants
FLOOR_TYPES = ["Keller", "EG", "1. OG", "2. OG", "3. OG"]
EXTERNAL_TYPES = ["Außenansicht", "Umgebung", "Ausblick", "Grundstück", "Garten", "Treppenhaus"]
TYPES = FLOOR_TYPES + EXTERNAL_TYPES + ["SKIP"]
ROOM_NAMES = [
    "Ankleidezimmer", "Badezimmer", "Balkon", "Büro", "Dachboden", "Dachterrasse",
    "Elternschlafzimmer", "Esszimmer", "Fitnessraum", "Gästezimmer", "Heizungsanlage",
    "Kinderzimmer", "Küche", "Loggia", "Partykeller", "Pool", "Sauna", "Schlafzimmer",
    "Terrasse", "Toilette", "Wintergarten", "Zimmer", "Wohnzimmer", "Diele", "Custom"
]

# Request/Response Models
class DrivesResponse(BaseModel):
    drives: List[str]

class FoldersRequest(BaseModel):
    drive: str

class FoldersResponse(BaseModel):
    folders: List[str]

class BracketsRequest(BaseModel):
    folder: str

class BracketsResponse(BaseModel):
    brackets: List[List[str]]
    count: int

class PreviewsRequest(BaseModel):
    folder: str
    brackets: List[List[str]]

class PreviewsResponse(BaseModel):
    previews: List[str]

class TypesResponse(BaseModel):
    types: List[str]
    floor_types: List[str]
    external_types: List[str]

class RoomsResponse(BaseModel):
    rooms: List[str]

class ClassificationEntry(BaseModel):
    room_name: Optional[str]
    files: List[str]

class ClassifyRequest(BaseModel):
    folder: str
    brackets: List[List[str]]
    classifications: Dict[str, List[ClassificationEntry]]

class ExportRequest(BaseModel):
    folder: str
    classifications: Dict[str, List[ClassificationEntry]]

class ExportResponse(BaseModel):
    success: bool
    total_files: int
    errors: List[str]

# Endpoints

@router.get("/drives", response_model=DrivesResponse)
async def get_drives():
    """Get list of available drives."""
    try:
        drives = file_manager.get_drives()
        logger.debug(f"Returning {len(drives)} drives")
        return DrivesResponse(drives=drives)
    except Exception as e:
        logger.error(f"Error getting drives: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/folders", response_model=FoldersResponse)
async def get_folders(request: FoldersRequest):
    """Get folders with .ARW files for a given drive."""
    try:
        logger.debug(f"Getting folders for drive: {request.drive}")
        folders = file_manager.get_folders_with_arw(request.drive)
        logger.debug(f"Found {len(folders)} folders")
        return FoldersResponse(folders=folders)
    except Exception as e:
        logger.error(f"Error getting folders: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/brackets", response_model=BracketsResponse)
async def get_brackets(request: BracketsRequest):
    """Get bracketed sets for a given folder."""
    try:
        start_time = time.time()
        logger.debug(f"Getting brackets for folder: {request.folder}")
        brackets = file_manager.bracket_files(request.folder)
        elapsed = time.time() - start_time
        
        if not brackets:
            logger.warning("No valid bracketed sets found")
            raise HTTPException(status_code=400, detail="No valid bracketed sets found in folder")
        
        logger.debug(f"Found {len(brackets)} brackets (took {elapsed:.2f}s)")
        return BracketsResponse(brackets=brackets, count=len(brackets))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting brackets: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/previews", response_model=PreviewsResponse)
async def get_previews(request: PreviewsRequest):
    """Get preview images for brackets."""
    try:
        start_time = time.time()
        logger.debug(f"Getting previews for {len(request.brackets)} brackets")
        previews = image_processor.load_previews_threaded(request.folder, request.brackets)
        elapsed = time.time() - start_time
        logger.debug(f"Generated {len(previews)} previews (took {elapsed:.2f}s)")
        return PreviewsResponse(previews=previews)
    except Exception as e:
        logger.error(f"Error getting previews: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/types", response_model=TypesResponse)
async def get_types():
    """Get available classification types."""
    logger.debug("Returning available types")
    return TypesResponse(
        types=TYPES,
        floor_types=FLOOR_TYPES,
        external_types=EXTERNAL_TYPES
    )

@router.get("/rooms", response_model=RoomsResponse)
async def get_rooms():
    """Get available room names."""
    logger.debug("Returning available rooms")
    return RoomsResponse(rooms=ROOM_NAMES)

@router.post("/export", response_model=ExportResponse)
async def export_images(request: ExportRequest):
    """Export and rename classified images."""
    try:
        logger.info(f"Starting export for folder: {request.folder}")
        
        # Convert ClassificationEntry objects to tuples for file_manager
        classifications_dict: Dict[str, List[Tuple[Optional[str], List[str]]]] = {}
        for type_val, entries in request.classifications.items():
            classifications_dict[type_val] = [
                (entry.room_name, entry.files) for entry in entries
            ]
        
        result = file_manager.move_and_rename_images(request.folder, classifications_dict)
        logger.info(f"Export completed: {result['total_files']} files processed")
        
        return ExportResponse(
            success=result["success"],
            total_files=result["total_files"],
            errors=result["errors"]
        )
    except Exception as e:
        logger.error(f"Error exporting images: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
