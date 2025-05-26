import os
import uuid
import json
import time
from typing import Dict, List, Optional
import subprocess
import re
import math
from app.utils.schema import MindMapNode, MindMapRequest, MindMapResponse
from app.services.rag_service import RAGService

class MindMapGenerator:
    """
    Service for generating cognitive maps from curriculum data
    """
    
    def __init__(self, rag_service: RAGService):
        """Initialize cognitive map generator"""
        self.rag_service = rag_service
        
        # Create directories if they don't exist
        os.makedirs("app/static/img/mindmaps", exist_ok=True)
        
    def generate(self, request: MindMapRequest) -> MindMapResponse:
        """Generate a cognitive map based on the provided request"""
        
        # Get curriculum information
        curriculum_info = self.rag_service.query_curriculum(
            curriculum=request.curriculum,
            grade=request.grade,
            subject=request.subject,
            topic=request.topic,
            curriculum_text=request.curriculum_text
        )
        
        # Create nodes
        root_node = self._create_node_tree(curriculum_info)
        
        # Generate cognitive map
        mindmap_id = str(uuid.uuid4())
        
        # Always use cognitive style
        svg_url, png_url = self._generate_graphviz(mindmap_id, root_node, "cognitive")
        html_embed = None
        
        # Create response
        response = MindMapResponse(
            mindmap_id=mindmap_id,
            svg_url=svg_url,
            png_url=png_url,
            html_embed=html_embed,
            nodes=root_node.to_dict()
        )
        
        return response
    
    def _create_node_tree(self, curriculum_info: Dict) -> MindMapNode:
        """Create a tree of nodes from curriculum information"""
        # Create root node
        root_id = "root"
        root_node = MindMapNode(
            id=root_id,
            text=curriculum_info["name"],
            attributes={"description": curriculum_info.get("description", "")}
        )
        
        # Process subtopics
        if "subtopics" in curriculum_info:
            for i, subtopic in enumerate(curriculum_info["subtopics"]):
                # Create subtopic node
                subtopic_id = f"subtopic_{i}"
                
                if isinstance(subtopic, dict):
                    subtopic_node = MindMapNode(
                        id=subtopic_id,
                        text=subtopic["name"],
                        parent_id=root_id,
                        attributes={"description": subtopic.get("description", "")}
                    )
                    
                    # Add key points
                    if "key_points" in subtopic:
                        for j, point in enumerate(subtopic["key_points"]):
                            point_id = f"{subtopic_id}_point_{j}"
                            point_node = MindMapNode(
                                id=point_id,
                                text=point,
                                parent_id=subtopic_id
                            )
                            subtopic_node.add_child(point_node)
                else:
                    # If subtopic is a string
                    subtopic_node = MindMapNode(
                        id=subtopic_id,
                        text=subtopic,
                        parent_id=root_id
                    )
                
                root_node.add_child(subtopic_node)
        
        # Add resources
        if "resources" in curriculum_info and curriculum_info["resources"]:
            resources_id = "resources"
            resources_node = MindMapNode(
                id=resources_id,
                text="Resources",
                parent_id=root_id
            )
            
            for i, resource in enumerate(curriculum_info["resources"]):
                resource_id = f"resource_{i}"
                resource_text = f"{resource['title']} ({resource['type']})"
                resource_node = MindMapNode(
                    id=resource_id,
                    text=resource_text,
                    parent_id=resources_id,
                    attributes={"url": resource.get("url", "")}
                )
                resources_node.add_child(resource_node)
            
            root_node.add_child(resources_node)
        
        return root_node
    
    def _generate_markmap(self, mindmap_id: str, root_node: MindMapNode) -> tuple:
        """Generate a cognitive map using markmap"""
        # Convert to markmap format
        markmap_data = self._node_to_markmap(root_node)
        
        # Save markmap data
        markmap_file = f"app/static/img/mindmaps/{mindmap_id}.mm.json"
        with open(markmap_file, 'w') as f:
            json.dump(markmap_data, f)
        
        # Create HTML file with embedded markmap
        html_file = f"app/static/img/mindmaps/{mindmap_id}.html"
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="UTF-8">
          <title>Cognitive Map: {root_node.text}</title>
          <script src="https://cdn.jsdelivr.net/npm/d3@6"></script>
          <script src="https://cdn.jsdelivr.net/npm/markmap-view@0.15.4"></script>
        </head>
        <body>
          <div id="mindmap" style="width: 100%; height: 600px;"></div>
          <script>
            const data = {json.dumps(markmap_data)};
            const {{ Markmap }} = window.markmap;
            const mm = Markmap.create('#mindmap', null, data);
          </script>
        </body>
        </html>
        """
        
        with open(html_file, 'w') as f:
            f.write(html_content)
        
        # Create SVG file
        svg_file = f"app/static/img/mindmaps/{mindmap_id}.svg"
        
        # Fallback to empty SVG if we can't generate one
        with open(svg_file, 'w') as f:
            f.write('<svg width="800" height="600" xmlns="http://www.w3.org/2000/svg"><text x="10" y="20">See HTML version for interactive cognitive map</text></svg>')
            
        svg_url = f"/static/img/mindmaps/{mindmap_id}.svg"
        html_embed = f'<iframe src="/static/img/mindmaps/{mindmap_id}.html" width="800" height="600" frameborder="0"></iframe>'
        
        return svg_url, html_embed
    
    def _node_to_markmap(self, node: MindMapNode) -> Dict:
        """Convert a node to markmap format"""
        result = {"t": node.text}
        
        if node.children:
            result["c"] = [self._node_to_markmap(child) for child in node.children]
            
        return result
    
    def _generate_graphviz(self, mindmap_id: str, root_node: MindMapNode, style: str) -> tuple:
        """Generate a cognitive map using Graphviz with enhanced output"""
        # Create DOT file
        dot_content = self._create_dot_file(root_node, style)
        
        dot_file = f"app/static/img/mindmaps/{mindmap_id}.dot"
        svg_file = f"app/static/img/mindmaps/{mindmap_id}.svg"
        png_file = f"app/static/img/mindmaps/{mindmap_id}.png"
        
        # Write DOT file
        with open(dot_file, 'w') as f:
            f.write(dot_content)
        
        # Generate SVG using Graphviz
        try:
            # Use neato engine with specific settings for cognitive maps
            engine = 'neato'
            # Additional arguments for higher quality, bigger output
            subprocess.run([engine, '-Tsvg', '-Gsize=15,15!', '-Gdpi=300', '-Gmaxiter=1000', '-Gsplines=line', dot_file, '-o', svg_file], check=True)
            subprocess.run([engine, '-Tpng', '-Gsize=15,15!', '-Gdpi=300', '-Gmaxiter=1000', '-Gsplines=line', dot_file, '-o', png_file], check=True)
                
        except Exception as e:
            print(f"Graphviz error: {e}")
            # Create empty files if generation fails
            with open(svg_file, 'w') as f:
                f.write('<svg width="800" height="600" xmlns="http://www.w3.org/2000/svg"><text x="10" y="20">Failed to generate cognitive map</text></svg>')
            
            with open(png_file, 'w') as f:
                f.write('')
        
        svg_url = f"/static/img/mindmaps/{mindmap_id}.svg"
        png_url = f"/static/img/mindmaps/{mindmap_id}.png"
        
        return svg_url, png_url
    
    def _create_dot_file(self, root_node: MindMapNode, style: str) -> str:
        """Create a DOT file from a node tree"""
        # Always use cognitive style
        return self._create_cognitive_dot(root_node)
    
    def _create_tree_dot(self, root_node: MindMapNode) -> str:
        """Create a tree DOT file"""
        lines = ['digraph G {']
        lines.append('  graph [rankdir=LR, splines=polyline, overlap=false, nodesep=0.5, ranksep=1.5];')
        lines.append('  node [shape=box, style="rounded,filled", fillcolor="#f5f5f5", fontname=Arial, fontsize=12, margin="0.2,0.1"];')
        lines.append('  edge [color="#666666"];')
        
        # Add root node
        lines.append(f'  "{root_node.id}" [label="{root_node.text}", fillcolor="#e8f5e9", fontsize=16, fontcolor="#2e7d32"];')
        
        # Add children recursively
        self._add_nodes_to_tree_dot(root_node, lines)
        
        lines.append('}')
        return '\n'.join(lines)
    
    def _add_nodes_to_tree_dot(self, node: MindMapNode, lines: List[str]):
        """Add nodes to DOT file recursively for tree style"""
        for child in node.children:
            # Select color based on level
            if child.parent_id == "root":
                color = "#e3f2fd"  # Light blue for first level
                font_color = "#1565c0"
            elif "resources" in child.id:
                color = "#fff8e1"  # Light amber for resources
                font_color = "#ff8f00"
            elif "point" in child.id:
                color = "#f3e5f5"  # Light purple for points
                font_color = "#6a1b9a"
            else:
                color = "#f1f8e9"  # Light green for other levels
                font_color = "#558b2f"
            
            # Clean label text
            label = re.sub(r'"', '\\"', child.text)
            
            # Add node
            lines.append(f'  "{child.id}" [label="{label}", fillcolor="{color}", fontcolor="{font_color}"];')
            
            # Add edge
            lines.append(f'  "{node.id}" -> "{child.id}";')
            
            # Recurse
            self._add_nodes_to_tree_dot(child, lines)
    
    def _create_cloud_dot(self, root_node: MindMapNode) -> str:
        """Create a cloud-style DOT file with pastel colors in a radial structure"""
        lines = ['digraph G {']
        # For radial layout with neato engine
        lines.append('  graph [overlap=false, splines=true, root="root", outputorder=edgesfirst];')
        # Use custom node styling for cloud-like appearance
        lines.append('  node [shape=ellipse, style="filled,rounded", penwidth=3.0, fontname="Comic Sans MS,Arial", fontsize=12, fixedsize=false, margin=0.3];')
        lines.append('  edge [color="#996B89", penwidth=1.8, style=dashed];')
        
        # Add root node - with more prominent styling
        root_text = re.sub(r'"', '\\"', root_node.text)
        lines.append(f'  "{root_node.id}" [label="{root_text}", shape=doubleoctagon, fillcolor="#A9BE70:#D4F5A9", style="filled,rounded,radial", fontsize=16, fontcolor="#5A6B39", pencolor="#996B89", width=2.2, height=2.2];')
        
        # Add children recursively with custom node styling
        self._add_cloud_nodes_to_dot(root_node, lines)
        
        lines.append('}')
        return '\n'.join(lines)
    
    def _add_cloud_nodes_to_dot(self, node: MindMapNode, lines: List[str]):
        """Add cloud-style nodes to DOT file recursively with radial positioning"""
        # Enhanced pastel color palette with gradient pairs
        cloud_colors = [
            "#D4C1EC:#E8DBFF",  # Lavender gradient
            "#AAD4F5:#D6EBFF",  # Light blue gradient
            "#C2E6CE:#E3F8EB",  # Mint gradient
            "#F2E5A7:#FCF7D9",  # Light yellow gradient
            "#F5CAC2:#FFEAE6",  # Light pink gradient
            "#F6D2A9:#FFEBD6",  # Light orange gradient
            "#BFD7E3:#E1F0F9",  # Light steel blue gradient
        ]
        
        # Calculate even distribution around the circle
        num_children = len(node.children)
        radius = 2.8  # Base radius for primary nodes
        
        for i, child in enumerate(node.children):
            # Select color based on index to ensure variety
            color_idx = i % len(cloud_colors)
            fill_color = cloud_colors[color_idx]
            
            # Determine pen color based on node type
            if "resources" in child.id:
                pen_color = "#D4A017"  # Gold for resources
                font_color = "#8B6F28"  # Darker gold for resources text
                node_shape = "egg"     # Different shape for resources
            elif "point" in child.id:
                pen_color = "#A877BA"  # Purple for points
                font_color = "#6A1B9A"  # Dark purple for point text
                node_shape = "oval"    # Different shape for points
            else:
                pen_color = "#6E9CAA"  # Blue-gray for subtopics
                font_color = "#2B5F75"  # Dark blue-gray for subtopic text
                node_shape = "ellipse" # Regular shape for subtopics
            
            # Clean label text and add line breaks for better layout
            label = re.sub(r'"', '\\"', child.text)
            # Insert line breaks for long text (approximately every 12-15 chars)
            if len(label) > 12:
                words = label.split()
                new_label = ""
                line_length = 0
                for word in words:
                    if line_length + len(word) > 12:
                        new_label += "\\n" + word
                        line_length = len(word)
                    else:
                        if new_label:
                            new_label += " " + word
                        else:
                            new_label = word
                        line_length += len(word) + 1
                label = new_label
            
            # Position primary children in a circle around the root
            if node.id == "root":
                # Calculate position in a circle
                angle = 2.0 * 3.14159 * i / num_children
                x = radius * math.cos(angle)
                y = radius * math.sin(angle)
                
                # Add node with cloud-like properties and explicit position
                lines.append(f'  "{child.id}" [label="{label}", shape={node_shape}, fillcolor="{fill_color}", style="filled,rounded,radial", fontcolor="{font_color}", pencolor="{pen_color}", penwidth=2.5, pos="{x},{y}!"];')
            else:
                # Non-first-level nodes with more subtle styling
                lines.append(f'  "{child.id}" [label="{label}", shape={node_shape}, fillcolor="{fill_color}", style="filled,rounded,radial", fontcolor="{font_color}", pencolor="{pen_color}", penwidth=2.0];')
            
            # Add edge with appropriate style based on level
            if node.id == "root":
                # More prominent edges from root
                lines.append(f'  "{node.id}" -> "{child.id}" [penwidth=2.0, style=solid, color="{pen_color}"];')
            else:
                # Subtler edges for deeper levels
                lines.append(f'  "{node.id}" -> "{child.id}" [style=dashed, arrowsize=0.8];')
            
            # Recurse with a smaller radius for sub-nodes
            self._add_cloud_nodes_to_dot(child, lines) 
    
    def _create_cognitive_dot(self, root_node: MindMapNode) -> str:
        """Create a scientific diagram with central node and straight extending lines"""
        lines = ['digraph G {']
        # Clean, minimalist layout with strict positioning
        lines.append('  graph [overlap=prism, splines=polyline, nodesep=2.0, ranksep=3.0, bgcolor="white", pad=2.0, outputorder=edgesfirst, concentrate=true, sep="+25,25"];')
        # Clean text nodes without borders but with padding to prevent overlap with lines
        lines.append('  node [shape=box, fontname="Arial", fontsize=10, margin=0.15, height=0.3, width=0, style="filled", fillcolor="white", penwidth=0, color=white];')
        # Thin black lines with gentle routing
        lines.append('  edge [color="black", penwidth=0.5, arrowhead=none];')
        
        # Add central node with box styling - slimmer border
        root_text = re.sub(r'"', '\\"', root_node.text.upper())
        lines.append(f'  "{root_node.id}" [label="{root_text}", shape=box, style="filled,rounded", fillcolor="white", penwidth=0.5, fontsize=11, fontname="Arial-Bold", margin=0.3, width=4.0, height=0.6, pos="0,0!"];')
        
        # Create ranks for precise layout
        rank_groups = {}
        
        # Process the cognitive map structure with scientific diagram layout
        self._create_scientific_branches(root_node, lines, rank_groups)
        
        # Add rank constraints
        for rank, nodes in rank_groups.items():
            if len(nodes) > 1:
                lines.append(f'  {{ rank=same; {"; ".join(nodes)} }}')
        
        lines.append('}')
        return '\n'.join(lines)
    
    def _create_scientific_branches(self, root_node: MindMapNode, lines: List[str], rank_groups):
        """Create the main topic branches with scientific diagram layout"""
        # Get direct children
        main_branches = [child for child in root_node.children if "resources" not in child.id]
        num_branches = len(main_branches)
        
        # Define precise angles for radial distribution
        # Optimized angles for different branch counts
        if num_branches <= 3:
            # For 1-3 branches, use equidistant positions
            angles = []
            for i in range(num_branches):
                angles.append(2 * math.pi * i / num_branches + math.pi/4)  # Offset by 45 degrees
        elif num_branches <= 6:
            # For 4-6 branches, use optimized positions to minimize overlap
            start_angle = math.pi/6  # 30 degrees
            angles = []
            for i in range(num_branches):
                angles.append(start_angle + (2 * math.pi * i / num_branches))
        else:
            # For more branches, distribute them with custom spacing to prevent overlap
            angles = []
            for i in range(num_branches):
                # Add slight variation to evenly space branches
                angles.append(2 * math.pi * i / num_branches + 0.1)
        
        # Distance from center - increased for better spacing
        distance = 10.0
        
        # Create all main topics with precise positioning
        for i, branch in enumerate(main_branches):
            branch_text = re.sub(r'"', '\\"', branch.text.upper())
            branch_id = branch.id
            
            # Calculate position using angle
            angle = angles[i % len(angles)]
            x = distance * math.cos(angle)
            y = distance * math.sin(angle)
            
            # Create branch node
            lines.append(f'  "{branch_id}" [label="{branch_text}", fontsize=10, fontname="Arial-Bold", style="filled", fillcolor="white", pos="{x},{y}!"];')
            
            # Connect with straight line - extremely thin
            lines.append(f'  "{root_node.id}" -> "{branch_id}" [penwidth=0.5];')
            
            # Store position for branch items
            branch_rank = f"rank_{i}"
            if branch_rank not in rank_groups:
                rank_groups[branch_rank] = []
            rank_groups[branch_rank].append(f'"{branch_id}"')
            
            # Process branch items with extremely long horizontal lines
            self._create_scientific_subitems(branch, lines, angle, x, y, rank_groups, branch_rank)
            
    def _create_scientific_subitems(self, branch_node: MindMapNode, lines: List[str], angle: float, branch_x: float, branch_y: float, rank_groups: dict, branch_rank: str):
        """Create subitems with proper spacing to avoid overlapping lines"""
        # Get child items
        items = branch_node.children
        
        # Skip if no items
        if not items:
            return
            
        # Direction vector from angle
        dir_x = math.cos(angle)
        dir_y = math.sin(angle)
        
        # Determine if we're in left or right half
        is_right_side = (dir_x > 0)
        h_direction = 1 if is_right_side else -1
            
        # Vertical spacing between items - increased to prevent overlap
        v_spacing = 3.0
        
        # Number of items - used to adjust vertical positioning
        num_items = len(items)
        
        # Offset angle for items to avoid overlapping the branch lines
        # This pushes items slightly away from the direct line
        offset_angle = 0.2 * h_direction
        
        # Process each item with precise staggered vertical placement
        for i, item in enumerate(items):
            # Use a combination of radial and vertical staggering for better distribution
            # This creates a more organic spread of items that's less likely to overlap
            sub_angle = angle + offset_angle
            v_offset = ((i - (num_items-1)/2) * v_spacing)
            
            # Clean text - no wrapping, plain formatting
            item_text = re.sub(r'"', '\\"', item.text)
            item_id = item.id
            
            # Item-specific rank
            item_rank = f"item_{branch_rank}_{i}"
            if item_rank not in rank_groups:
                rank_groups[item_rank] = []
            
            # Position calculation with better spacing
            item_distance = 6.0  # Distance from branch
            
            # Calculate position with slight angle offset to avoid direct line overlap
            item_x = branch_x + (item_distance * math.cos(sub_angle))
            item_y = branch_y + (item_distance * math.sin(sub_angle)) + v_offset
            
            # Text node with white background to mask overlapping lines
            lines.append(f'  "{item_id}" [label="{item_text}", fontsize=9, style="filled", fillcolor="white", pos="{item_x},{item_y}!"];')
            
            # Connect branch to item with polyline option for better routing
            lines.append(f'  "{branch_node.id}" -> "{item_id}" [penwidth=0.5];')
            
            # Add to rank group
            rank_groups[item_rank].append(f'"{item_id}"')
    
    def _wrap_text(self, text: str, width: int) -> str:
        """Wrap text at specified width while preserving words and maintaining readability"""
        if len(text) <= width:
            return text
            
        words = text.split()
        lines = []
        current_line = []
        current_length = 0
        
        for word in words:
            if current_length + len(word) + len(current_line) <= width:
                current_line.append(word)
                current_length += len(word)
            else:
                lines.append(" ".join(current_line))
                current_line = [word]
                current_length = len(word)
                
        if current_line:
            lines.append(" ".join(current_line))
            
        return "\\n".join(lines) 