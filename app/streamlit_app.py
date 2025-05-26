import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
import streamlit as st
import requests
import json
import base64
from PIL import Image
import io
from dotenv import load_dotenv

from app.services.rag_service import RAGService
from app.services.generator import MindMapGenerator
from app.utils.schema import MindMapRequest

# Load environment variables
load_dotenv()

# Set page config
st.set_page_config(
    page_title="Cognitive Map Builder",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize services
@st.cache_resource
def init_services():
    rag_service = RAGService()
    mindmap_generator = MindMapGenerator(rag_service)
    return rag_service, mindmap_generator

rag_service, mindmap_generator = init_services()

# Create necessary directories
os.makedirs("app/static/img/mindmaps", exist_ok=True)

# App header
st.title("🧠 Cognitive Map Builder")
st.markdown("Create curriculum-aligned visual cognitive maps for academic topics")
st.markdown("---")

# Sidebar for inputs
with st.sidebar:
    st.header("Input Parameters")
    
    # Get user inputs
    curriculum = st.selectbox(
        "Curriculum",
        ["CBSE", "ICSE", "IGCSE", "IB", "State Board"]
    )
    
    grade = st.selectbox(
        "Grade/Class",
        [f"Grade {i}" for i in range(1, 13)]
    )
    
    subject = st.selectbox(
        "Subject",
        ["Science", "Physics", "Chemistry", "Biology", "Mathematics", 
         "History", "Geography", "English", "Social Studies", "Computer Science"]
    )
    
    topic = st.text_input("Topic/Chapter", value="", help="Enter the name of the topic or chapter")
    
    language = st.selectbox(
        "Language",
        ["English", "Hindi", "Spanish", "French"]
    )
    
    curriculum_file = st.file_uploader(
        "Upload Curriculum PDF (Optional)",
        type=["pdf", "txt", "docx"],
        help="Upload your own curriculum or textbook content"
    )
    
    st.markdown("---")
    
    # Generate button
    generate_button = st.button("Generate Cognitive Map", type="primary", use_container_width=True)

# Main content area
col1, col2 = st.columns([2, 3])

# Load placeholder image
with col1:
    st.subheader("Cognitive Map Settings")
    
    st.write("**Selected Parameters:**")
    
    parameters = {
        "Curriculum": curriculum,
        "Grade": grade,
        "Subject": subject,
        "Topic": topic,
        "Language": language
    }
    
    for key, value in parameters.items():
        st.write(f"- **{key}:** {value}")
    
    st.markdown("---")
    
    st.write("**Export Options:**")
    
    export_format = st.radio(
        "Export Format",
        ["SVG", "PNG", "Interactive HTML"],
        horizontal=True
    )
    
    include_resources = st.checkbox("Include Resource Links", value=True)
    include_questions = st.checkbox("Include Conceptual Questions", value=False)
    
    st.markdown("---")
    
    if st.button("Reset All", type="secondary"):
        st.rerun()

with col2:
    st.subheader("Cognitive Map Preview")
    
    # Display placeholder or result
    if 'mindmap_result' not in st.session_state:
        st.info("Your cognitive map will appear here after generation")
        
        # Show sample image
        st.image("https://www.edrawsoft.com/templates/images/sefl-introduction-mindmap.png", 
                caption="Sample Cognitive Map (Demo Only)")
    else:
        # Display the generated cognitive map
        result = st.session_state.mindmap_result
        
        if result.html_embed:
            st.components.v1.html(result.html_embed, height=600)
        elif result.svg_url:
            # Load the SVG file
            try:
                with open(f"app{result.svg_url}", "r") as f:
                    svg_content = f.read()
                    st.components.v1.html(svg_content, height=600)
            except:
                st.error("Failed to load SVG file")
        else:
            st.error("Failed to generate cognitive map")
        
        # Download buttons
        col_svg, col_png, col_html = st.columns(3)
        
        with col_svg:
            if result.svg_url:
                with open(f"app{result.svg_url}", "rb") as file:
                    svg_bytes = file.read()
                    svg_b64 = base64.b64encode(svg_bytes).decode()
                    href = f'<a href="data:image/svg+xml;base64,{svg_b64}" download="mindmap.svg" class="button">Download SVG</a>'
                    st.markdown(href, unsafe_allow_html=True)
        
        with col_png:
            if result.png_url:
                with open(f"app{result.png_url}", "rb") as file:
                    png_bytes = file.read()
                    png_b64 = base64.b64encode(png_bytes).decode()
                    href = f'<a href="data:image/png;base64,{png_b64}" download="mindmap.png" class="button">Download PNG</a>'
                    st.markdown(href, unsafe_allow_html=True)
        
        with col_html:
            if result.html_embed:
                # Extract the file path from the iframe src
                import re
                match = re.search(r'src="([^"]+)"', result.html_embed)
                if match:
                    html_path = match.group(1)
                    with open(f"app{html_path}", "rb") as file:
                        html_bytes = file.read()
                        html_b64 = base64.b64encode(html_bytes).decode()
                        href = f'<a href="data:text/html;base64,{html_b64}" download="mindmap.html" class="button">Download HTML</a>'
                        st.markdown(href, unsafe_allow_html=True)

# Process the generation request
if generate_button and topic:
    with st.spinner("Generating your cognitive map..."):
        # Prepare the curriculum text if file is uploaded
        curriculum_text = None
        if curriculum_file is not None:
            # Read the file
            bytes_data = curriculum_file.read()
            
            # Convert to text (assuming it's a text-based file)
            try:
                curriculum_text = bytes_data.decode("utf-8")
            except:
                st.error("Could not decode the uploaded file. Please try a different format.")
                curriculum_text = None
        
        # Create request object
        request = MindMapRequest(
            curriculum=curriculum,
            grade=grade,
            subject=subject,
            topic=topic,
            style="cognitive",
            language=language,
            curriculum_text=curriculum_text
        )
        
        # Generate cognitive map
        result = mindmap_generator.generate(request)
        
        # Store result in session
        st.session_state.mindmap_result = result
        
        # Rerun to display the result
        st.rerun()

# Custom CSS
st.markdown("""
<style>
    .main .block-container {
        padding-top: 2rem;
    }
    
    h1, h2, h3 {
        color: #1976d2;
    }
    
    .stButton>button {
        width: 100%;
    }
    
    .button {
        display: inline-block;
        padding: 0.5rem 1rem;
        background-color: #1976d2;
        color: white;
        text-align: center;
        text-decoration: none;
        border-radius: 4px;
        margin: 0.5rem 0;
        width: 100%;
    }
    
    .button:hover {
        background-color: #1565c0;
        color: white;
        text-decoration: none;
    }
    
    .css-1v0mbdj {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True) 