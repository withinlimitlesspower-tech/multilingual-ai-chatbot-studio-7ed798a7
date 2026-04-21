"""
Pixabay API Client for video and image search.
Handles authentication, search, and response processing for Pixabay API.
"""

import os
import logging
from typing import Dict, List, Optional, Any, Union
import requests
from dataclasses import dataclass
from datetime import datetime
import json
from urllib.parse import urlencode

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class PixabayMedia:
    """Data class for Pixabay media items."""
    id: int
    type: str  # 'photo' or 'video'
    preview_url: str
    full_url: str
    tags: List[str]
    views: int
    downloads: int
    likes: int
    user: str
    width: int
    height: int
    duration: Optional[int] = None  # Only for videos
    video_files: Optional[List[Dict]] = None  # Only for videos


class PixabayClient:
    """
    Client for interacting with Pixabay API.
    
    Handles authentication, search requests, and response parsing for both
    images and videos from Pixabay.
    """
    
    BASE_URL = "https://pixabay.com/api/"
    VIDEO_BASE_URL = "https://pixabay.com/api/videos/"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Pixabay client with API key.
        
        Args:
            api_key: Pixabay API key. If not provided, reads from PIXABAY_API_KEY
                    environment variable.
        
        Raises:
            ValueError: If no API key is provided or found in environment.
        """
        self.api_key = api_key or os.getenv("PIXABAY_API_KEY")
        
        if not self.api_key:
            raise ValueError(
                "Pixabay API key is required. "
                "Provide it as argument or set PIXABAY_API_KEY environment variable."
            )
        
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Chatbot-Pixabay-Client/1.0",
            "Accept": "application/json"
        })
        
        logger.info("PixabayClient initialized with API key (first 8 chars): %s", 
                   self.api_key[:8] + "..." if len(self.api_key) > 8 else self.api_key)
    
    def _make_request(
        self, 
        endpoint: str, 
        params: Dict[str, Any],
        is_video: bool = False
    ) -> Dict[str, Any]:
        """
        Make HTTP request to Pixabay API.
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            is_video: Whether this is a video search request
        
        Returns:
            JSON response as dictionary
        
        Raises:
            requests.exceptions.RequestException: For network or HTTP errors
            ValueError: For invalid API responses
        """
        base_url = self.VIDEO_BASE_URL if is_video else self.BASE_URL
        url = f"{base_url}{endpoint}"
        
        # Add API key to parameters
        params["key"] = self.api_key
        
        try:
            logger.debug("Making request to Pixabay API: %s with params: %s", 
                        url, {k: v for k, v in params.items() if k != "key"})
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Validate response structure
            if not isinstance(data, dict):
                raise ValueError("Invalid response format from Pixabay API")
            
            if "hits" not in data:
                logger.warning("No 'hits' in Pixabay API response: %s", data)
                data["hits"] = []
            
            logger.info("Pixabay API request successful. Total hits: %s, Total available: %s",
                       len(data.get("hits", [])), data.get("total", 0))
            
            return data
            
        except requests.exceptions.Timeout:
            logger.error("Pixabay API request timed out")
            raise
        except requests.exceptions.HTTPError as e:
            logger.error("Pixabay API HTTP error: %s - %s", e.response.status_code, e.response.text)
            raise
        except requests.exceptions.RequestException as e:
            logger.error("Pixabay API request failed: %s", str(e))
            raise
        except json.JSONDecodeError as e:
            logger.error("Failed to parse Pixabay API response as JSON: %s", str(e))
            raise ValueError(f"Invalid JSON response from Pixabay API: {str(e)}")
    
    def search_images(
        self,
        query: str,
        category: Optional[str] = None,
        min_width: Optional[int] = None,
        min_height: Optional[int] = None,
        colors: Optional[str] = None,
        orientation: Optional[str] = None,  # 'all', 'horizontal', 'vertical'
        order: str = "popular",
        per_page: int = 20,
        page: int = 1,
        safe_search: bool = True,
        editors_choice: bool = False,
        lang: str = "en"
    ) -> List[PixabayMedia]:
        """
        Search for images on Pixabay.
        
        Args:
            query: Search query string
            category: Image category (e.g., 'backgrounds', 'fashion', 'nature')
            min_width: Minimum image width in pixels
            min_height: Minimum image height in pixels
            colors: Filter by color (e.g., 'grayscale', 'transparent', 'red')
            orientation: Image orientation
            order: Sort order ('popular', 'latest')
            per_page: Results per page (3-200)
            page: Page number
            safe_search: Enable safe search filtering
            editors_choice: Return only editor's choice images
            lang: Language for search results
        
        Returns:
            List of PixabayMedia objects for images
        """
        # Validate parameters
        if not query or not query.strip():
            raise ValueError("Search query cannot be empty")
        
        if per_page < 3 or per_page > 200:
            logger.warning("per_page %s out of range (3-200), using default 20", per_page)
            per_page = 20
        
        # Build query parameters
        params = {
            "q": query.strip(),
            "image_type": "photo",
            "per_page": per_page,
            "page": page,
            "safesearch": "true" if safe_search else "false",
            "editors_choice": "true" if editors_choice else "false",
            "lang": lang,
            "order": order
        }
        
        # Add optional parameters
        if category:
            params["category"] = category
        if min_width:
            params["min_width"] = min_width
        if min_height:
            params["min_height"] = min_height
        if colors:
            params["colors"] = colors
        if orientation and orientation in ["horizontal", "vertical"]:
            params["orientation"] = orientation
        
        try:
            response = self._make_request("", params, is_video=False)
            return self._parse_image_response(response)
            
        except Exception as e:
            logger.error("Failed to search images: %s", str(e))
            return []
    
    def search_videos(
        self,
        query: str,
        category: Optional[str] = None,
        min_width: Optional[int] = None,
        min_height: Optional[int] = None,
        video_type: Optional[str] = None,  # 'all', 'film', 'animation'
        order: str = "popular",
        per_page: int = 20,
        page: int = 1,
        safe_search: bool = True,
        editors_choice: bool = False,
        lang: str = "en"
    ) -> List[PixabayMedia]:
        """
        Search for videos on Pixabay.
        
        Args:
            query: Search query string
            category: Video category
            min_width: Minimum video width in pixels
            min_height: Minimum video height in pixels
            video_type: Type of video
            order: Sort order ('popular', 'latest')
            per_page: Results per page (3-200)
            page: Page number
            safe_search: Enable safe search filtering
            editors_choice: Return only editor's choice videos
            lang: Language for search results
        
        Returns:
            List of PixabayMedia objects for videos
        """
        # Validate parameters
        if not query or not query.strip():
            raise ValueError("Search query cannot be empty")
        
        if per_page < 3 or per_page > 200:
            logger.warning("per_page %s out of range (3-200), using default 20", per_page)
            per_page = 20
        
        # Build query parameters
        params = {
            "q": query.strip(),
            "per_page": per_page,
            "page": page,
            "safesearch": "true" if safe_search else "false",
            "editors_choice": "true" if editors_choice else "false",
            "lang": lang,
            "order": order
        }
        
        # Add optional parameters
        if category:
            params["category"] = category
        if min_width:
            params["min_width"] = min_width
        if min_height:
            params["min_height"] = min_height
        if video_type and video_type in ["film", "animation"]:
            params["video_type"] = video_type
        
        try:
            response = self._make_request("", params, is_video=True)
            return self._parse_video_response(response)
            
        except Exception as e:
            logger.error("Failed to search videos: %s", str(e))
            return []
    
    def _parse_image_response(self, response: Dict[str, Any]) -> List[PixabayMedia]:
        """
        Parse Pixabay image API response.
        
        Args:
            response: Raw API response dictionary
        
        Returns:
            List of parsed PixabayMedia objects
        """
        media_items = []
        
        for hit in response.get("hits", []):
            try:
                media = PixabayMedia(
                    id=hit.get("id", 0),
                    type="photo",
                    preview_url=hit.get("previewURL", ""),
                    full_url=hit.get("largeImageURL", hit.get("webformatURL", "")),
                    tags=[tag.strip() for tag in hit.get("tags", "").split(",") if tag.strip()],
                    views=hit.get("views", 0),
                    downloads=hit.get("downloads", 0),
                    likes=hit.get("likes", 0),
                    user=hit.get("user", "Unknown"),
                    width=hit.get("imageWidth", 0),
                    height=hit.get("imageHeight", 0)
                )
                media_items.append(media)
                
            except KeyError as e:
                logger.warning("Missing key in image response: %s", str(e))
                continue
            except Exception as e:
                logger.warning("Failed to parse image hit: %s", str(e))
                continue
        
        logger.debug("