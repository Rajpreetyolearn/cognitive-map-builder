from pydantic import BaseModel
from typing import Optional, List, Dict, Union

class MindMapNode:
    """A node in the mind map"""
    def __init__(
        self, 
        id: str, 
        text: str, 
        parent_id: Optional[str] = None,
        children: List["MindMapNode"] = None,
        attributes: Dict[str, str] = None
    ):
        self.id = id
        self.text = text
        self.parent_id = parent_id
        self.children = children or []
        self.attributes = attributes or {}
    
    def add_child(self, child: "MindMapNode"):
        """Add a child node to this node"""
        self.children.append(child)
        
    def to_dict(self):
        """Convert node to dictionary for serialization"""
        return {
            "id": self.id,
            "text": self.text,
            "children": [child.to_dict() for child in self.children],
            "attributes": self.attributes
        }

class MindMapRequest(BaseModel):
    """Request model for mind map generation"""
    curriculum: str
    grade: str
    subject: str
    topic: str
    style: str = "cognitive"
    language: str = "English"
    curriculum_text: Optional[str] = None

class MindMapResponse(BaseModel):
    """Response model for mind map generation"""
    mindmap_id: str
    svg_url: str
    png_url: str
    html_embed: Optional[str] = None
    nodes: Optional[dict] = None
    svg_base64: Optional[str] = None
    png_base64: Optional[str] = None

class Topic(BaseModel):
    """Model for a curriculum topic"""
    name: str
    description: Optional[str] = None
    subtopics: List[Union[str, "Topic"]] = []
    resources: Optional[List[Dict[str, str]]] = None

class CurriculumInfo(BaseModel):
    """Model for curriculum information"""
    curriculum: str
    grade: str
    subject: str
    topics: List[Topic] 