#!/usr/bin/env python3
"""
Simple FastAPI server to serve palio.json data
"""

import json
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

app = FastAPI(title="Palio API", description="Simple API to serve palio.json data", version="1.0.0")

# Add CORS middleware to allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Path to palio.json file
PALIO_FILE_PATH = Path(__file__).parent / "palio.json"

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

@app.get("/")
async def root():
    """
    Root endpoint with API information
    """
    return {
        "message": "Palio API",
        "version": "1.0.0",
        "endpoints": {
            "/palio": "GET - Returns complete palio.json data"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)