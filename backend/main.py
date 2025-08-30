import os
import sys
import traceback
import random
import psycopg2
import json
import re
from typing import Optional
from fastapi import FastAPI, HTTPException, Response, Form, UploadFile
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from together import Together
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import base64
import io
from PIL import Image

from agentic import router as agentic_router  # Added import for Agentic Study Room routes
from aiquickhelp import router as aiquickhelp_router  # Import your new Quick AI Help router

# --- DEBUG: Print environment variables containing sensitive info keys ---
print("---- ENVIRONMENT VARIABLES ----")
for key, value in os.environ.items():
    if "DB" in key or "API" in key or "SUPABASE" in key:
        print(f"{key}={value}")

# Load .env
script_dir = os.path.dirname(__file__)
dotenv_path = os.path.join(script_dir, '.env')
print(f"Attempting to load .env from {dotenv_path}")
load_dotenv(dotenv_path=dotenv_path)
print(".env loaded")

# API & DB config
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_PORT = os.getenv("DB_PORT")

print("DB config loaded:", DB_HOST, DB_USER, DB_NAME, DB_PORT)

# Initialize AI and Embedding clients
llm_client = Together(api_key=TOGETHER_API_KEY)
try:
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    print("Embedding model loaded successfully.")
except Exception as e:
    print(f"Error loading embedding model: {e}")
    traceback.print_exc()
    sys.exit(1)

# Request Models
class ContentRequest(BaseModel):
    topic: str
    mode: str

class GoogleLoginRequest(BaseModel):
    token: str

class FeatureRequest(BaseModel):
    user_email: str
    feature_text: str

class AskQuestionRequest(BaseModel):
    question: str
    image_data: Optional[str] = None

app = FastAPI()

# Register Agentic Study Room API routes
app.include_router(agentic_router, prefix="/agentic", tags=["Agentic Study Room"])

# Register Quick AI Help API routes
app.include_router(aiquickhelp_router, prefix="/agentic", tags=["Agentic Quick Help"])

origins = [
    "https://praxisai-rho.vercel.app",
    "https://praxis-ai.fly.dev",
    "http://localhost:8080",
    "http://localhost",
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:8080",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Explicit OPTIONS handler for all routes to assist CORS preflight requests ===
@app.options("/{rest_of_path:path}")
async def options_handler(rest_of_path: str):
    return Response(status_code=200)

def get_db_connection():
    try:
        print("Trying DB connection...")
        conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT)
        print("DB connect success.")
        return conn
    except psycopg2.OperationalError as e:
        print(f"CRITICAL: Could not connect to the database. Error: {e}")
        traceback.print_exc()
        return None

def parse_quiz_json_from_string(text: str) -> dict | None:
    text = text.strip()
    text = re.sub(r"^\\`\\`\\`json\\`\\`\\`|\\`\\`\\`$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        print("DEBUG: AI did not return valid JSON. Attempting regex parsing...")
        try:
            question_match = re.search(r'"question":\s*"(.*?)"', text, re.DOTALL)
            options_match = re.search(r'"options":\s*\{(.*?)\}', text, re.DOTALL)
            answer_match = re.search(r'"correct_answer":\s*"(.*?)"', text, re.DOTALL)
            explanation_match = re.search(r'"explanation":\s*"(.*?)"', text, re.DOTALL)
            if not all([question_match, options_match, answer_match, explanation_match]):
                return None
            question = question_match.group(1).strip().replace('\\n', '\n').replace('\\"', '"')
            options_str = options_match.group(1)
            correct_answer = answer_match.group(1).strip()
            explanation = explanation_match.group(1).strip().replace('\\n', '\n').replace('\\"', '"')
            options = {}
            option_matches = re.findall(r'"([A-D])":\s*"(.*?)"', options_str)
            for key, value in option_matches:
                options[key] = value.strip().replace('\\n', '\n').replace('\\"', '"')
            if len(options) != 4:
                return None
            return {"question": question, "options": options, "correct_answer": correct_answer, "explanation": explanation}
        except Exception as e:
            print(f"DEBUG: Regex parsing encountered an unexpected error: {e}")
            traceback.print_exc()
            return None

THEORETICAL_TOPICS = ["introduction", "overview", "basics", "fundamentals"]

@app.get("/api/syllabus")
async def get_syllabus():
    print("GET /api/syllabus called")
    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            raise HTTPException(status_code=503, detail="Database connection unavailable.")
        with conn.cursor() as cur:
            print("Running syllabus DB queries...")
            cur.execute("SELECT id, name FROM subjects ORDER BY name")
            subjects_raw = cur.fetchall()
            cur.execute("SELECT id, name, chapter_number, subject_id, class_number FROM chapters ORDER BY subject_id, class_number, chapter_number")
            chapters_raw = cur.fetchall()
            cur.execute("SELECT id, name, topic_number, chapter_id FROM topics ORDER BY chapter_id, topic_number")
            topics_raw = cur.fetchall()
            chapters_map = {c_id: {"id": c_id, "name": c_name, "number": c_num, "class_level": c_level, "topics": []} for c_id, c_name, c_num, s_id, c_level in chapters_raw}
            for t_id, t_name, t_num, c_id in topics_raw:
                if c_id in chapters_map:
                    chapters_map[c_id]["topics"].append({"id": t_id, "name": t_name, "number": t_num})
            subjects_map = {s_id: {"id": s_id, "name": s_name, "chapters": []} for s_id, s_name in subjects_raw}
            for c_id, c_name, c_num, s_id, c_level in chapters_raw:
                if s_id in subjects_map:
                    subjects_map[s_id]["chapters"].append(chapters_map[c_id])
            syllabus = list(subjects_map.values())
        print("Syllabus query success.")
        return JSONResponse(content=syllabus)
    except psycopg2.Error as e:
        print(f"Database query error while fetching syllabus: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="An error occurred while fetching the syllabus.")
    finally:
        if conn:
            conn.close()

@app.post("/api/generate-content")
async def generate_content(request: ContentRequest):
    print("POST /api/generate-content called with:", request)
    topic_prompt = request.topic
    mode = request.mode
    conn = None
    try:
        topic_embedding = embedding_model.encode(topic_prompt).tolist()
        print("Embedding generated successfully.")

        conn = get_db_connection()
        if conn is None:
            raise HTTPException(status_code=503, detail="Database connection unavailable.")

        relevant_text, context_level, context_name = "", "", ""
        with conn.cursor() as cur:
            print("Finding matching topic in DB...")
            cur.execute("SELECT * FROM match_topics(%s::vector, 0.3, 10)", (topic_embedding,))
            match_results = cur.fetchall()
            print(f"Match results count: {len(match_results)}")
            if not match_results:
                return JSONResponse(content={"question": None, "error": "Practice questions are not applicable for this introductory topic.", "source_name": topic_prompt, "source_level": "User Query"})

            matched_topic_id, matched_topic_name, similarity, matched_chapter_id = random.choice(match_results)
            print(f"DEBUG: Randomly selected topic '{matched_topic_name}' (Similarity: {similarity:.4f})")

            cur.execute("SELECT full_text FROM topics WHERE id = %s", (matched_topic_id,))
            topic_text_result = cur.fetchone()

            # --- THIS IS THE CORRECTED LINE ---
            if topic_text_result and topic_text_result[0] and topic_text_result[0].strip():
                relevant_text, context_level, context_name = topic_text_result[0], "Topic", matched_topic_name
            else:
                print(f"DEBUG: Topic text empty. Falling back to CHAPTER level context (ID: {matched_chapter_id}).")
                cur.execute("SELECT name, full_text FROM chapters WHERE id = %s", (matched_chapter_id,))
                chapter_text_result = cur.fetchone()
                if chapter_text_result and chapter_text_result[1] and chapter_text_result[1].strip():
                    relevant_text, context_level, context_name = chapter_text_result[1], "Chapter", chapter_text_result[0]
                else:
                    return JSONResponse(content={"question": None, "error": "Practice questions are not applicable for this introductory topic.", "source_name": matched_topic_name, "source_level": "Topic"})

        if mode == "practice" and context_level == "Chapter":
            if context_name.strip().lower() in THEORETICAL_TOPICS:
                return JSONResponse(content={"question": None, "error": "Practice questions are not applicable for this introductory topic.", "source_name": context_name, "source_level": context_level})

        max_chars = 15000
        if len(relevant_text) > max_chars:
            relevant_text = relevant_text[:max_chars]

        user_message_content = f"The user wants to learn about the topic: '{topic_prompt}'.\n\n--- CONTEXT FROM TEXTBOOK ({context_level}: {context_name}) ---\n{relevant_text}\n--- END OF CONTEXT ---"
        response_params = {"model": "mistralai/Mixtral-8x7B-Instruct-v0.1", "max_tokens": 2048, "temperature": 0.4}
        system_message = ""

        if mode == 'revise':
            system_message = """You are an AI assistant creating a structured 'cheat sheet' for JEE topics."""
        elif mode == 'practice':
            system_message = (
                "You are an expert AI quiz generator for JEE students. "
                "Given textbook context, respond ONLY with a valid JSON object matching this template: "
                '{'
                '"question": "...", '
                '"options": { "A": "...", "B": "...", "C": "...", "D": "..." }, '
                '"correct_answer": "...", '
                '"explanation": "..." '
                '}. '
                "Do not include any explanations, comments, or Markdown. ONLY output strict JSON—no extra formatting."
            )
        else:
            system_message = """You are an expert JEE tutor."""

        try:
            print("Calling LLM API for response...")
            messages = [{"role": "system", "content": system_message}, {"role": "user", "content": user_message_content}]
            response_params["messages"] = messages
            response = llm_client.chat.completions.create(**response_params)
            content = response.choices[0].message.content.strip()
            print("LLM response received.")
            if not content or content.lower().startswith("i'm sorry") or content.lower().startswith("i cannot"):
                print("LLM refused to answer.")
                raise HTTPException(status_code=503, detail="The AI was unable to generate a response.")
            if mode == 'practice':
                parsed_quiz = parse_quiz_json_from_string(content)
                if parsed_quiz is None:
                    print("LLM returned invalid format for quiz. Try fallback on chapter context.")
                    with conn.cursor() as cur:
                        cur.execute("SELECT full_text, name FROM chapters WHERE id = %s", (matched_chapter_id,))
                        chapter_result = cur.fetchone()
                        if chapter_result and chapter_result[0] and chapter_result[0].strip():
                            chapter_text, chapter_name = chapter_result
                            fallback_message_content = f"The user wants to learn about the topic: '{topic_prompt}'.\n\n--- CONTEXT FROM TEXTBOOK (Chapter: {chapter_name}) ---\n{chapter_text}\n--- END OF CONTEXT ---"
                            fallback_messages = [{"role": "system", "content": system_message}, {"role": "user", "content": fallback_message_content}]
                            fallback_response = llm_client.chat.completions.create(
                                model=response_params["model"],
                                max_tokens=response_params["max_tokens"],
                                temperature=response_params["temperature"],
                                messages=fallback_messages
                            )
                            fallback_content = fallback_response.choices[0].message.content.strip()
                            parsed_fallback = parse_quiz_json_from_string(fallback_content)
                            if parsed_fallback:
                                parsed_fallback['source_name'], parsed_fallback['source_level'] = chapter_name, "Chapter"
                                print("Fallback quiz generated from chapter context.")
                                return JSONResponse(content=parsed_fallback)
                    print("AI returned invalid format for both topic and chapter context.")
                    raise HTTPException(status_code=502, detail="The AI returned an invalid format for both topic and chapter context.")
                parsed_quiz['source_name'], parsed_quiz['source_level'] = context_name, context_level
                print("Quiz generated and returned.")
                return JSONResponse(content=parsed_quiz)
            else:
                print("Learn/revise content returned.")
                return JSONResponse(content={"content": content, "source_name": context_name, "source_level": context_level})
        except HTTPException as e:
            print("HTTP exception:", e)
            traceback.print_exc()
            raise e
        except Exception as e:
            print("An unexpected error occurred during AI call:", e)
            traceback.print_exc()
            raise HTTPException(status_code=500, detail="An unexpected error occurred.")
    finally:
        if conn:
            conn.close()
        print("DB connection closed (if any).")

@app.post("/api/google-login")
async def google_login(data: GoogleLoginRequest):
    try:
        idinfo = id_token.verify_oauth2_token(
            data.token,
            google_requests.Request(),
            "621306164868-21bamnrurup0nk6f836fss6q92s04aav.apps.googleusercontent.com"  # Your Google OAuth Client ID
        )
        email = idinfo.get("email")
        name = idinfo.get("name")
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=503, detail="Database connection unavailable.")
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (email, name)
                VALUES (%s, %s)
                ON CONFLICT (email) DO UPDATE SET name = EXCLUDED.name
                """,
                (email, name)
            )
            conn.commit()
        print(f"Google login success for: {email}")
        return {"email": email, "name": name}
    except Exception as e:
        print(f"Google token verification or DB save failed: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail="Invalid Google token or DB error")
    finally:
        if 'conn' in locals() and conn:
            conn.close()

@app.post("/api/feature-request")
async def submit_feature_request(request: FeatureRequest):
    conn = get_db_connection()
    if conn is None:
        raise HTTPException(status_code=503, detail="Database unavailable.")
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO feature_requests (user_email, feature_text) VALUES (%s, %s)",
                (request.user_email, request.feature_text)
            )
            conn.commit()
        return {"message": "Feature request submitted successfully."}
    except Exception as e:
        print(f"Feature request insert error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Error saving feature request.")
    finally:
        if conn:
            conn.close()

@app.post("/ask-question")
async def ask_question(request: AskQuestionRequest):
    """AI endpoint to answer questions with optional image support"""
    print("POST /ask-question called with:", request.question[:100] + "..." if len(request.question) > 100 else request.question)
    
    try:
        # Process image if provided
        image_description = ""
        if request.image_data:
            try:
                # Decode base64 image
                image_bytes = base64.b64decode(request.image_data)
                image = Image.open(io.BytesIO(image_bytes))
                
                # Extract text from image using PIL for basic analysis
                # For now, we'll create a description of the image
                image_description = f"Image detected: {image.size[0]}x{image.size[1]} pixels, format: {image.format}, mode: {image.mode}"
                
                # If it's a mathematical problem or diagram, add context
                if image.size[0] > image.size[1]:  # Landscape - likely a diagram
                    image_description += ". This appears to be a diagram or graph."
                else:  # Portrait - likely text or formula
                    image_description += ". This appears to contain text or mathematical content."
                
                print(f"Image processed: {image_description}")
                
            except Exception as e:
                print(f"Error processing image: {e}")
                image_description = "Image processing failed, but continuing with text question."
        
        # Combine question with image description
        full_question = request.question
        if image_description:
            full_question = f"Question: {request.question}\n\nImage Context: {image_description}\n\nPlease analyze both the question and the image to provide a comprehensive answer."
        
        # Generate embedding for the question
        question_embedding = embedding_model.encode(full_question).tolist()
        print("Question embedding generated successfully.")
        
        conn = None
        try:
            conn = get_db_connection()
            if conn is None:
                raise HTTPException(status_code=503, detail="Database connection unavailable.")
            
            # Find relevant content in database
            relevant_text, context_level, context_name = "", "", ""
            with conn.cursor() as cur:
                print("Finding matching content in DB...")
                cur.execute("SELECT * FROM match_topics(%s::vector, 0.3, 10)", (question_embedding,))
                match_results = cur.fetchall()
                print(f"Match results count: {len(match_results)}")
                
                if match_results:
                    matched_topic_id, matched_topic_name, similarity, matched_chapter_id = random.choice(match_results)
                    print(f"Selected topic '{matched_topic_name}' (Similarity: {similarity:.4f})")
                    
                    # Get topic text
                    cur.execute("SELECT full_text FROM topics WHERE id = %s", (matched_topic_id,))
                    topic_text_result = cur.fetchone()
                    
                    if topic_text_result and topic_text_result[0] and topic_text_result[0].strip():
                        relevant_text, context_level, context_name = topic_text_result[0], "Topic", matched_topic_name
                    else:
                        # Fallback to chapter text
                        cur.execute("SELECT name, full_text FROM chapters WHERE id = %s", (matched_chapter_id,))
                        chapter_text_result = cur.fetchone()
                        if chapter_text_result and chapter_text_result[1] and chapter_text_result[1].strip():
                            relevant_text, context_level, context_name = chapter_text_result[1], "Chapter", chapter_text_result[0]
                        else:
                            relevant_text = "General JEE knowledge"
                            context_level = "General"
                            context_name = "JEE Syllabus"
                else:
                    relevant_text = "General JEE knowledge"
                    context_level = "General"
                    context_name = "JEE Syllabus"
            
            # Limit text length
            max_chars = 15000
            if len(relevant_text) > max_chars:
                relevant_text = relevant_text[:max_chars]
            
            # Create prompt for AI
            system_message = """You are an expert JEE tutor specializing in Physics, Chemistry, and Mathematics. 
            
            CRITICAL: You are NOT ChatGPT or a general AI. You are a JEE PCM tutor ONLY.
            
            Your task is to answer the student's question using the provided textbook context and any image context.
            
            Guidelines:
            - If an image is provided, carefully analyze both the question and image content
            - Use the textbook context to provide accurate, JEE-level explanations
            - Include mathematical formulas using LaTeX notation when relevant
            - Provide step-by-step explanations suitable for JEE preparation
            - Focus only on JEE PCM subjects (Physics, Chemistry, Mathematics)
            - If asked about non-PCM topics, politely redirect to JEE subjects
            
            Format your response clearly with proper markdown formatting."""
            
            user_message_content = f"Student Question: {full_question}\n\n--- TEXTBOOK CONTEXT ({context_level}: {context_name}) ---\n{relevant_text}\n--- END OF CONTEXT ---"
            
            # Call AI model
            print("Calling LLM API for response...")
            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message_content}
            ]
            
            response_params = {
                "model": "mistralai/Mixtral-8x7B-Instruct-v0.1",
                "max_tokens": 2048,
                "temperature": 0.4,
                "messages": messages
            }
            
            response = llm_client.chat.completions.create(**response_params)
            answer = response.choices[0].message.content.strip()
            
            if not answer or answer.lower().startswith(("i'm sorry", "i cannot", "i don't know")):
                raise HTTPException(status_code=503, detail="The AI was unable to generate a response.")
            
            print("AI response generated successfully.")
            
            return JSONResponse(content={
                "answer": answer,
                "source_chapter": context_name,
                "source_level": context_level,
                "image_processed": bool(request.image_data)
            })
            
        except HTTPException as e:
            raise e
        except Exception as e:
            print(f"Error in ask_question: {e}")
            traceback.print_exc()
            raise HTTPException(status_code=500, detail="An error occurred while processing your question.")
        finally:
            if conn:
                conn.close()
                
    except Exception as e:
        print(f"Unexpected error in ask_question: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")

@app.post("/image-solve")
async def image_solve(
    question: str = Form(...),
    image: UploadFile = File(...)
):
    """Image solver endpoint that processes images and sends them to AI chat"""
    print(f"POST /image-solve called with question: {question[:100]}...")
    print(f"Image file: {image.filename}, size: {image.size} bytes")
    
    try:
        # Read and process the uploaded image
        image_content = await image.read()
        
        # Convert to base64 for storage and transmission
        image_base64 = base64.b64encode(image_content).decode('utf-8')
        
        # Process image with PIL for basic analysis
        try:
            # Convert bytes to PIL Image
            pil_image = Image.open(io.BytesIO(image_content))
            
            # Basic image analysis using PIL only
            width, height = pil_image.size
            image_format = pil_image.format
            image_mode = pil_image.mode
            
            print(f"Image processed: {width}x{height} pixels, format: {image_format}, mode: {image_mode}")
            
            # Enhanced image description for AI
            image_description = f"""
Image Analysis:
- Dimensions: {width}x{height} pixels
- Format: {image_format}
- Color mode: {image_mode}
- File size: {len(image_content)} bytes

This image appears to contain a {'mathematical problem or diagram' if width > height else 'text or formula content'}.
Please analyze both the visual content and the accompanying question to provide a comprehensive solution.
"""
            
        except Exception as e:
            print(f"Error in image processing: {e}")
            # Fallback to basic description
            image_description = f"Image uploaded: {image.filename}, size: {len(image_content)} bytes"
        
        # Now call the ask-question endpoint with both text and image data
        # We'll simulate the internal call to avoid HTTP overhead
        try:
            # Create the request object for internal processing
            internal_request = AskQuestionRequest(
                question=f"{question}\n\n{image_description}",
                image_data=image_base64
            )
            
            # Process internally (this avoids making an HTTP call to ourselves)
            return await ask_question(internal_request)
            
        except Exception as e:
            print(f"Error in internal ask_question call: {e}")
            # Fallback: return the processed image data for manual handling
            return JSONResponse(content={
                "answer": f"Image processed successfully. Question: {question}\n\nImage: {image.filename} ({len(image_content)} bytes)\n\nPlease use the ask-question endpoint with the image data to get a complete answer.",
                "source_chapter": "Image Analysis",
                "source_level": "Image",
                "image_processed": True,
                "image_data": image_base64,
                "image_metadata": {
                    "filename": image.filename,
                    "size": len(image_content),
                    "format": getattr(pil_image, 'format', 'unknown'),
                    "dimensions": f"{getattr(pil_image, 'size', [0, 0])[0]}x{getattr(pil_image, 'size', [0, 0])[1]}"
                }
            })
            
    except Exception as e:
        print(f"Error in image_solve: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to process image: {str(e)}")

# Alternative endpoint for base64 encoded images
@app.post("/image-solve-base64")
async def image_solve_base64(request: AskQuestionRequest):
    """Image solver endpoint that accepts base64 encoded images"""
    print(f"POST /image-solve-base64 called with question: {request.question[:100]}...")
    print(f"Image data provided: {bool(request.image_data)}")
    
    if not request.image_data:
        raise HTTPException(status_code=400, detail="Image data is required for this endpoint")
    
    try:
        # Decode base64 image
        image_bytes = base64.b64decode(request.image_data)
        
        # Process image
        pil_image = Image.open(io.BytesIO(image_bytes))
        
        width, height = pil_image.size
        print(f"Base64 image processed: {width}x{height} pixels")
        
        # Enhanced question with image context
        enhanced_question = f"""
{request.question}

Image Context:
- Dimensions: {width}x{height} pixels
- Format: {getattr(pil_image, 'format', 'unknown')}
- This appears to contain {'a mathematical problem or diagram' if width > height else 'text or mathematical content'}.

Please analyze both the question and the image content to provide a comprehensive solution.
"""
        
        # Create internal request with enhanced question
        internal_request = AskQuestionRequest(
            question=enhanced_question,
            image_data=request.image_data
        )
        
        # Process internally
        return await ask_question(internal_request)
        
    except Exception as e:
        print(f"Error in image_solve_base64: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to process base64 image: {str(e)}")

# --- Health Check Endpoint ---
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Import and include Agentic Study Room routes
app.include_router(agentic_router, prefix="/agentic", tags=["Agentic Study Room"])
