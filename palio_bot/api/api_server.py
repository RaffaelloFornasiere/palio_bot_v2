#!/usr/bin/env python3
"""
Simple FastAPI server to serve palio data files
"""

import json
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

app = FastAPI(title="Palio API", description="Simple API to serve palio data files", version="1.0.0")

# Add CORS middleware to allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Path to palio.json file - now relative to the package root
PALIO_FILE_PATH = Path(__file__).parent.parent.parent / "data" / "palio.json"

# Path to data directory for additional JSON files
DATA_DIR_PATH = Path(__file__).parent.parent.parent / "data"

# Path to React build directory - now relative to the package root
REACT_BUILD_PATH = Path(__file__).parent.parent.parent / "website" / "build"

@app.get("/palio")
async def get_palio_data():
    """
    Returns the complete palio.json data
    """
    try:
        if not PALIO_FILE_PATH.exists():
            raise HTTPException(status_code=404, detail="palio.json file not found")
        
        with open(PALIO_FILE_PATH, 'r', encoding='utf-8') as f:
            palio_data = json.load(f)
        
        return palio_data
    
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid JSON in palio.json")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading palio.json: {str(e)}")

@app.get("/leaderboard")
async def get_leaderboard_data():
    """
    Returns the leaderboard.json data
    """
    try:
        leaderboard_path = DATA_DIR_PATH / "leaderboard.json"
        if not leaderboard_path.exists():
            raise HTTPException(status_code=404, detail="leaderboard.json file not found")
        
        with open(leaderboard_path, 'r', encoding='utf-8') as f:
            leaderboard_data = json.load(f)
        
        return leaderboard_data
    
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid JSON in leaderboard.json")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading leaderboard.json: {str(e)}")

@app.get("/palio_games_status")
async def get_palio_games_status():
    """
    Returns the palio_games_status.json data
    """
    try:
        games_status_path = DATA_DIR_PATH / "palio_games_status.json"
        if not games_status_path.exists():
            raise HTTPException(status_code=404, detail="palio_games_status.json file not found")
        
        with open(games_status_path, 'r', encoding='utf-8') as f:
            games_status_data = json.load(f)
        
        return games_status_data
    
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid JSON in palio_games_status.json")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading palio_games_status.json: {str(e)}")

# Mount static files from React build
if REACT_BUILD_PATH.exists() and REACT_BUILD_PATH.is_dir():
    # Serve static assets (JS, CSS, images, etc.)
    app.mount("/static", StaticFiles(directory=str(REACT_BUILD_PATH / "static")), name="static")
    
    # Serve the React app's index.html for the root path
    @app.get("/")
    async def serve_root():
        """
        Serve the React app at the root path
        """
        index_path = REACT_BUILD_PATH / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        else:
            raise HTTPException(status_code=404, detail="React app not found")
    
    # Catch-all route to serve the React app's index.html for client-side routing
    @app.get("/{full_path:path}")
    async def serve_react_app(full_path: str):
        """
        Serve the React app for all routes not matching API endpoints
        """
        # Don't serve React app for API routes
        if full_path.startswith(("palio", "leaderboard", "palio_games_status")):
            raise HTTPException(status_code=404, detail="Not found")
        
        index_path = REACT_BUILD_PATH / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        else:
            raise HTTPException(status_code=404, detail="React app not found")

def main():
    """Main entry point for the API server"""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()