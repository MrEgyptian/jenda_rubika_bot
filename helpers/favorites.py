import json
from pathlib import Path
from typing import List, Dict, Optional


DB_DIR = Path(__file__).resolve().parents[1] / "db"


def _get_user_db_path(user_id: str) -> Path:
    """Get the path to a user's favorites database file."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    return DB_DIR / f"{user_id}.json"


def _load_user_favorites(user_id: str) -> Dict:
    """Load a user's favorites from their JSON file."""
    db_path = _get_user_db_path(user_id)
    if not db_path.exists():
        return {"user_id": user_id, "favorites": []}
    
    try:
        with open(db_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"user_id": user_id, "favorites": []}


def _save_user_favorites(user_id: str, data: Dict) -> bool:
    """Save a user's favorites to their JSON file."""
    db_path = _get_user_db_path(user_id)
    try:
        with open(db_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except IOError as e:
        print(f"Error saving favorites for user {user_id}: {e}")
        return False


def add_favorite(user_id: str, url: str, title: Optional[str] = None) -> bool:
    """Add a URL to a user's favorites."""
    user_data = _load_user_favorites(user_id)
    
    favorite = {
        "url": url,
        "title": title or url,
        "added_at": str(Path.cwd())  # Just a simple timestamp reference
    }
    
    # Check if URL already in favorites
    for fav in user_data.get("favorites", []):
        if fav.get("url") == url:
            return False  # Already exists
    
    user_data["favorites"].append(favorite)
    return _save_user_favorites(user_id, user_data)


def remove_favorite(user_id: str, url: str) -> bool:
    """Remove a URL from a user's favorites."""
    user_data = _load_user_favorites(user_id)
    original_count = len(user_data.get("favorites", []))
    
    user_data["favorites"] = [
        fav for fav in user_data.get("favorites", [])
        if fav.get("url") != url
    ]
    
    if len(user_data["favorites"]) < original_count:
        return _save_user_favorites(user_id, user_data)
    
    return False  # URL not found


def get_user_favorites(user_id: str) -> List[Dict]:
    """Get all favorites for a user."""
    user_data = _load_user_favorites(user_id)
    return user_data.get("favorites", [])


def get_favorites_text(user_id: str) -> str:
    """Format user's favorites as readable text."""
    favorites = get_user_favorites(user_id)
    
    if not favorites:
        return "You have no saved favorites yet. Use /add_favorite <url> to save one!"
    
    text = "⭐ Your Favorites:\n\n"
    for i, fav in enumerate(favorites, 1):
        url = fav.get("url", "Unknown")
        title = fav.get("title", url)
        text += f"{i}. {title}\n   {url}\n\n"
    
    return text
