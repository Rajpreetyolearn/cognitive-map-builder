import os
from fastapi import FastAPI, Request, Form, UploadFile, File, Query
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Optional
import uvicorn
from dotenv import load_dotenv
import base64

from app.services.generator import MindMapGenerator
from app.services.rag_service import RAGService
from app.utils.schema import MindMapRequest, MindMapResponse

load_dotenv()

app = FastAPI(title="Cognitive Map Builder")

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Initialize services
rag_service = RAGService()
mindmap_generator = MindMapGenerator(rag_service)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/generate-mindmap")
async def generate_mindmap(
    curriculum: str = Form(...),
    grade: str = Form(...),
    subject: str = Form(...),
    topic: str = Form(...),
    style: Optional[str] = Form("cognitive"),
    language: Optional[str] = Form("English"),
    curriculum_file: Optional[UploadFile] = File(None)
):
    """Generate a cognitive map based on input parameters"""
    
    # Process curriculum file if provided
    curriculum_text = None
    if curriculum_file:
        content = await curriculum_file.read()
        curriculum_text = content.decode("utf-8")
    
    # Create request object
    request = MindMapRequest(
        curriculum=curriculum,
        grade=grade,
        subject=subject,
        topic=topic,
        style="cognitive",  # Always use cognitive style
        language=language,
        curriculum_text=curriculum_text
    )
    
    # Generate cognitive map
    result = mindmap_generator.generate(request)
    
    # Add base64 encoded versions of the images
    svg_path = f"app/static/img/mindmaps/{result.mindmap_id}.svg"
    png_path = f"app/static/img/mindmaps/{result.mindmap_id}.png"
    
    # Add base64 encoded data if files exist
    if os.path.exists(svg_path):
        with open(svg_path, "rb") as svg_file:
            svg_base64 = base64.b64encode(svg_file.read()).decode()
            result.svg_base64 = f"data:image/svg+xml;base64,{svg_base64}"
    
    if os.path.exists(png_path):
        with open(png_path, "rb") as png_file:
            png_base64 = base64.b64encode(png_file.read()).decode()
            result.png_base64 = f"data:image/png;base64,{png_base64}"
    
    return result

@app.get("/api/mindmap/{mindmap_id}")
async def get_mindmap(
    mindmap_id: str,
    format: str = Query("svg", description="File format (svg or png)"),
    response_type: str = Query("file", description="Response type (file or base64)")
):
    """Retrieve a generated cognitive map by ID"""
    if format not in ["svg", "png"]:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid format. Use 'svg' or 'png'"}
        )
        
    file_path = f"app/static/img/mindmaps/{mindmap_id}.{format}"
    
    if not os.path.exists(file_path):
        return JSONResponse(
            status_code=404,
            content={"error": "Cognitive map not found"}
        )
    
    if response_type == "base64":
        try:
            with open(file_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode()
                
            mime_type = "image/svg+xml" if format == "svg" else "image/png"
            data_url = f"data:{mime_type};base64,{encoded_string}"
            
            return {
                "mindmap_id": mindmap_id,
                "format": format,
                "base64_data": encoded_string,
                "data_url": data_url
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": f"Failed to encode image: {str(e)}"}
            )
    
    return FileResponse(file_path)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True) 