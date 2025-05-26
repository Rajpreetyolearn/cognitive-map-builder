import os
from typing import List, Dict, Optional, Union
import json
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_community.vectorstores import Qdrant
from langchain.chains import RetrievalQA
from langchain_core.prompts import PromptTemplate
from langchain_text_splitters import RecursiveCharacterTextSplitter
import requests
import wikipedia
from dotenv import load_dotenv
import asyncio

load_dotenv()

class RAGService:
    """
    Retrieval-Augmented Generation service for curriculum information using Google Gemini
    """
    
    def __init__(self):
        """Initialize the RAG service with necessary components"""
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        
        # Initialize embeddings with Google
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="models/text-embedding-004",
            google_api_key=self.google_api_key
        )
        
        # Initialize LLM with Gemini - using sync client
        self.llm = ChatGoogleGenerativeAI(
            google_api_key=self.google_api_key,
            model="gemini-1.5-flash-latest",
            temperature=0.2,
            transport="rest"  # Force synchronous REST API instead of async gRPC
        )
        
        # Initialize vector store if data exists
        self.vector_store = None
        self.curriculum_data = {}
        
        # Load curriculum data if available
        self._load_curriculum_data()
        
    def _load_curriculum_data(self):
        """Load curriculum data from JSON files"""
        curriculum_dir = "app/data/curricula"
        
        if not os.path.exists(curriculum_dir):
            os.makedirs(curriculum_dir, exist_ok=True)
            return
            
        for filename in os.listdir(curriculum_dir):
            if filename.endswith(".json"):
                with open(os.path.join(curriculum_dir, filename), 'r') as f:
                    curriculum_info = json.load(f)
                    key = f"{curriculum_info['curriculum']}_{curriculum_info['grade']}_{curriculum_info['subject']}"
                    self.curriculum_data[key] = curriculum_info
    
    def _create_vector_store(self, texts: List[str], metadata: List[Dict] = None):
        """Create vector store from texts"""
        # Initialize text splitter
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        
        # Split texts
        docs = []
        for i, text in enumerate(texts):
            chunks = text_splitter.split_text(text)
            for chunk in chunks:
                doc_metadata = metadata[i] if metadata else {}
                docs.append({"page_content": chunk, "metadata": doc_metadata})
        
        # Create vector store
        self.vector_store = Qdrant.from_documents(
            docs,
            self.embeddings,
            location=":memory:",
            collection_name="curriculum_data"
        )
    
    def query_curriculum(self, 
                         curriculum: str, 
                         grade: str, 
                         subject: str, 
                         topic: str,
                         curriculum_text: Optional[str] = None) -> Dict:
        """
        Query curriculum information
        """
        # Check if we have curriculum data
        key = f"{curriculum}_{grade}_{subject}"
        
        curriculum_info = None
        if key in self.curriculum_data:
            curriculum_info = self.curriculum_data[key]
            # Find matching topic
            for t in curriculum_info["topics"]:
                if t["name"].lower() == topic.lower():
                    return t
        
        # If curriculum text provided, use it
        if curriculum_text:
            # Create vector store from curriculum text
            self._create_vector_store([curriculum_text], [{"source": "user_upload"}])
            
            # Create QA chain
            qa_chain = RetrievalQA.from_chain_type(
                llm=self.llm,
                chain_type="stuff",
                retriever=self.vector_store.as_retriever(),
                return_source_documents=True,
                chain_type_kwargs={
                    "prompt": self._get_curriculum_prompt_template()
                }
            )
            
            # Query
            query = f"Extract information about {topic} in {subject} for {grade} {curriculum}"
            result = qa_chain({"query": query})
            
            # Gemini might return markdown JSON, attempt to clean it
            try:
                response_text = result["result"].strip()
                if response_text.startswith("```json"):
                    response_text = response_text[7:].strip()
                if response_text.endswith("```"):
                    response_text = response_text[:-3].strip()
                return json.loads(response_text)
            except json.JSONDecodeError:
                 # If parsing fails, use the LLM to reformat
                print("Warning: Failed to parse initial JSON, attempting reformat...")
                return self._reformat_to_json(result["result"], curriculum, grade, subject, topic)
            except Exception as e:
                print(f"Error processing LLM response: {e}")
                return self._generate_fallback_info(topic, curriculum, grade, subject)
        
        # Fallback to external sources
        return self._query_external_sources(curriculum, grade, subject, topic)
    
    def _query_external_sources(self, 
                               curriculum: str, 
                               grade: str, 
                               subject: str, 
                               topic: str) -> Dict:
        """Query external sources like Wikipedia"""
        # Try Wikipedia
        try:
            wiki_results = self._search_wikipedia(topic, subject)
            if wiki_results:
                return self._process_external_content(wiki_results, curriculum, grade, subject, topic)
        except Exception as e:
            print(f"Wikipedia search failed: {e}")
        
        # Fallback to just using the LLM
        return self._generate_curriculum_info(curriculum, grade, subject, topic)
    
    def _search_wikipedia(self, topic: str, subject: str) -> str:
        """Search Wikipedia for information"""
        search_term = f"{topic} {subject}"
        search_results = wikipedia.search(search_term)
        
        if not search_results:
            return None
        
        try:
            page = wikipedia.page(search_results[0])
            return page.content
        except Exception as e:
            print(f"Error fetching Wikipedia page: {e}")
            return None
    
    def _process_external_content(self, 
                                 content: str, 
                                 curriculum: str, 
                                 grade: str, 
                                 subject: str, 
                                 topic: str) -> Dict:
        """Process external content using the LLM"""
        prompt = self._get_json_formatting_prompt()
        
        response = self.llm.invoke(
            prompt.format(
                content=content,
                curriculum=curriculum,
                grade=grade,
                subject=subject,
                topic=topic
            )
        )
        
        try:
            # Extract JSON from the result
            result_text = response.content.strip()
            if result_text.startswith("```json"):
                result_text = result_text[7:].strip()
            if result_text.endswith("```"):
                result_text = result_text[:-3].strip()
            return json.loads(result_text)
        except json.JSONDecodeError:
             print("Warning: Failed to parse JSON from external content, attempting reformat...")
             return self._reformat_to_json(response.content, curriculum, grade, subject, topic)
        except Exception as e:
            print(f"Error processing external content: {e}")
            return self._generate_fallback_info(topic, curriculum, grade, subject)

    def _generate_curriculum_info(self, 
                                 curriculum: str, 
                                 grade: str, 
                                 subject: str, 
                                 topic: str) -> Dict:
        """Generate curriculum info using just the LLM"""
        prompt = self._get_json_formatting_prompt(use_content=False)
        
        response = self.llm.invoke(
            prompt.format(
                curriculum=curriculum,
                grade=grade,
                subject=subject,
                topic=topic
            )
        )
        
        try:
            # Extract JSON from the result
            result_text = response.content.strip()
            if result_text.startswith("```json"):
                result_text = result_text[7:].strip()
            if result_text.endswith("```"):
                result_text = result_text[:-3].strip()
            return json.loads(result_text)
        except json.JSONDecodeError:
            print("Warning: Failed to parse initial JSON generation, attempting reformat...")
            return self._reformat_to_json(response.content, curriculum, grade, subject, topic)
        except Exception as e:
            print(f"Error generating curriculum info: {e}")
            return self._generate_fallback_info(topic, curriculum, grade, subject)
            
    def _reformat_to_json(self, 
                         text_to_reformat: str, 
                         curriculum: str, 
                         grade: str, 
                         subject: str, 
                         topic: str) -> Dict:
        """Attempt to reformat text into the desired JSON structure using the LLM."""
        reformat_prompt = PromptTemplate(
            input_variables=["text"],
            template="""
            The following text contains curriculum information but might not be valid JSON. Please reformat it strictly into the following JSON structure:
            {{
                "name": "Topic name",
                "description": "Brief description of the topic",
                "subtopics": [
                    {{
                        "name": "Subtopic name",
                        "description": "Brief description of the subtopic",
                        "key_points": ["point 1", "point 2", ...]
                    }},
                    ...
                ],
                "resources": [
                    {{"type": "video", "title": "Resource title", "url": "URL"}},
                    ...
                ]
            }}
            Only output the JSON object, nothing else.

            Text to reformat:
            {text}
            """
        )
        
        try:
            response = self.llm.invoke(reformat_prompt.format(text=text_to_reformat))
            result_text = response.content.strip()
            if result_text.startswith("```json"):
                result_text = result_text[7:].strip()
            if result_text.endswith("```"):
                result_text = result_text[:-3].strip()
            return json.loads(result_text)
        except Exception as e:
            print(f"Error during JSON reformatting: {e}. Returning basic structure.")
            return self._generate_fallback_info(topic, curriculum, grade, subject)

    def _generate_fallback_info(self, topic: str, curriculum: str, grade: str, subject: str) -> Dict:
         """Return a basic fallback structure if all JSON parsing/generation fails."""
         return {
                "name": topic,
                "description": f"Information about {topic} in {subject} for {grade} {curriculum} (fallback data)",
                "subtopics": [],
                "resources": []
            }
            
    def _get_json_formatting_prompt(self, use_content=True):
        """Returns the prompt template for generating structured JSON output."""
        # Quadruple braces needed here for literal JSON braces in the final Langchain prompt template string.
        json_structure = """{{{{
    "name": "Topic name",
    "description": "Brief description of the topic",
    "subtopics": [
        {{{{
            "name": "Subtopic name",
            "description": "Brief description of the subtopic",
            "key_points": ["point 1", "point 2", ...]
        }}}},
        ...
    ],
    "resources": [
        {{{{ "type": "video", "title": "Resource title", "url": "URL" }}}},
        ...
    ]
}}}}"""

        # Use double braces for Langchain variables like {{topic}}
        if use_content:
            template_string = f"""
Create a structured curriculum topic for {{topic}} in {{subject}} for {{grade}} {{curriculum}}.
Content:
{{content}}

Format the output STRICTLY as a JSON object with the following structure:
{json_structure}

IMPORTANT: Only output the raw JSON object. Do not include ```json markdown or any other text before or after the JSON.
"""
            input_vars = ["curriculum", "grade", "subject", "topic", "content"]
        else:
            # Note the empty line where the content section would be
            template_string = f"""
Create a structured curriculum topic for {{topic}} in {{subject}} for {{grade}} {{curriculum}}.

Format the output STRICTLY as a JSON object with the following structure:
{json_structure}

IMPORTANT: Only output the raw JSON object. Do not include ```json markdown or any other text before or after the JSON.
"""
            input_vars = ["curriculum", "grade", "subject", "topic"]

        # Create the PromptTemplate with the fully constructed string
        return PromptTemplate(
            input_variables=input_vars,
            template=template_string
        )
    
    def _get_curriculum_prompt_template(self):
        """Get prompt template for curriculum extraction from provided text"""
        return PromptTemplate(
            input_variables=["context", "query"],
            template="""
            You are a curriculum expert. Use the following information to answer the question.
            
            {context}
            
            Based on the above information, extract the curriculum information into a structured format.
            Format your response STRICTLY as a JSON object with the following structure:
            {{
                "name": "Topic name",
                "description": "Brief description of the topic",
                "subtopics": [
                    {{
                        "name": "Subtopic name",
                        "description": "Brief description of the subtopic",
                        "key_points": ["point 1", "point 2", ...]
                    }},
                    ...
                ],
                "resources": [
                    {{"type": "video", "title": "Resource title", "url": "URL"}},
                    ...
                ]
            }}
            
            IMPORTANT: Only output the raw JSON object. Do not include ```json markdown or any other text before or after the JSON.
            Question: {query}
            """
        ) 