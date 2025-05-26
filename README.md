# Mind Map Generator

An AI-powered tool that generates curriculum-aligned mind maps for educational content using Google Gemini.

## Features

- Generate visually engaging mind maps for academic topics
- Support for various curricula (CBSE, ICSE, IGCSE, etc.)
- Hierarchical structure with main topics and subtopics
- Multiple output formats (SVG, PNG)
- RAG-based knowledge retrieval from curriculum resources and Wikipedia
- Optional styles and customization
- Powered by Google Gemini AI for curriculum knowledge

## Setup

1. Clone this repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Set up environment variables:
   ```
   cp .env.example .env
   ```
   Then edit `.env` with your Google API key

4. Run the application:
   ```
   python -m app.main
   ```
   
   Or use Streamlit interface:
   ```
   streamlit run app/streamlit_app.py
   ```

## Usage

1. Choose curriculum, grade, subject, and topic
2. Select preferred style and language (optional)
3. Generate the mind map
4. Download or embed the result

## Architecture

- FastAPI backend with LangChain for AI orchestration
- Google Gemini AI for intelligent content generation
- Qdrant vector database for RAG
- Google Generative AI embeddings for semantic search
- Graphviz/markmap for mind map rendering
- Streamlit for user interface 