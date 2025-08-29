"""
Deep Study Mode AI Tutoring Module for PraxisAI

This module implements advanced AI tutoring features including:
- Multi-turn conversational AI with context memory
- Step-by-step topic explanations with formulas and examples
- Incremental problem solving with hints and solutions
- Personalized study plan generation
- Session tracking and progress adaptation
- Rich markdown content with math formulas
- Interactive quizzes with instant feedback
- Long conversation context management

Author: PraxisAI Team
Version: 1.0.0
"""

import os
import json
import uuid
import asyncio
import traceback
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Union
from enum import Enum
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from sentence_transformers import SentenceTransformer
from together import Together

from dotenv import load_dotenv

# Load environment variables
script_dir = os.path.dirname(__file__)
dotenv_path = os.path.join(script_dir, '.env')
load_dotenv(dotenv_path=dotenv_path)

# Configuration
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_PORT = os.getenv("DB_PORT")

# Initialize AI clients
llm_client = Together(api_key=TOGETHER_API_KEY)
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

# Router instance
router = APIRouter()

# Constants
MAX_CONTEXT_LENGTH = 8000  # Maximum tokens for conversation context
MAX_SESSION_DURATION = 24  # Hours
DEFAULT_MODEL = "mistralai/Mixtral-8x7B-Instruct-v0.1"
THEORETICAL_TOPICS = ["introduction", "overview", "basics", "fundamentals"]

class TutoringMode(str, Enum):
    """Available tutoring modes for Deep Study Mode"""
    EXPLAIN = "explain"
    SOLVE = "solve"
    PRACTICE = "practice"
    REVISE = "revise"
    PLAN = "plan"
    QUIZ = "quiz"

class MessageRole(str, Enum):
    """Message roles in conversation"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"

@dataclass
class ConversationMessage:
    """Represents a message in the tutoring conversation"""
    role: MessageRole
    content: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class StudySession:
    """Represents an active study session"""
    session_id: str
    user_id: str
    subject: str
    topic: str
    mode: TutoringMode
    messages: List[ConversationMessage]
    created_at: datetime
    last_activity: datetime
    progress_data: Dict[str, Any]
    context_summary: Optional[str] = None

@dataclass
class StudyPlan:
    """Represents a personalized study plan"""
    plan_id: str
    user_id: str
    subjects: List[str]
    duration_days: int
    goals: List[str]
    daily_tasks: List[Dict[str, Any]]
    created_at: datetime
    progress: Dict[str, Any]

# Pydantic Models for API
class StartSessionRequest(BaseModel):
    """Request model for starting a new study session"""
    subject: str = Field(..., description="Subject to study (Physics, Chemistry, Mathematics)")
    topic: str = Field(..., description="Specific topic to focus on")
    mode: TutoringMode = Field(..., description="Tutoring mode to use")
    user_id: str = Field(..., description="User identifier")
    
    @validator('subject')
    def validate_subject(cls, v):
        valid_subjects = ['Physics', 'Chemistry', 'Mathematics']
        if v not in valid_subjects:
            raise ValueError(f'Subject must be one of: {valid_subjects}')
        return v

class ChatMessageRequest(BaseModel):
    """Request model for sending a message in study session"""
    session_id: str = Field(..., description="Active session identifier")
    message: str = Field(..., description="User message")
    context_hint: Optional[str] = Field(None, description="Optional context hint")

class ProblemSolveRequest(BaseModel):
    """Request model for problem solving assistance"""
    session_id: str = Field(..., description="Active session identifier")
    problem: str = Field(..., description="Problem statement")
    step: Optional[int] = Field(1, description="Current step in solving process")
    hint_level: Optional[int] = Field(1, description="Level of hint detail (1-3)")

class StudyPlanRequest(BaseModel):
    """Request model for generating study plans"""
    user_id: str = Field(..., description="User identifier")
    subjects: List[str] = Field(..., description="Subjects to include in plan")
    duration_days: int = Field(..., ge=1, le=30, description="Plan duration in days")
    goals: List[str] = Field(..., description="Learning goals")
    current_level: str = Field("intermediate", description="Current proficiency level")

class QuizRequest(BaseModel):
    """Request model for generating quizzes"""
    session_id: str = Field(..., description="Active session identifier")
    difficulty: str = Field("medium", description="Quiz difficulty level")
    question_count: int = Field(5, ge=1, le=10, description="Number of questions")

# Database utilities
def get_db_connection():
    """Get database connection with proper error handling"""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            cursor_factory=psycopg2.extras.RealDictCursor
        )
        return conn
    except psycopg2.OperationalError as e:
        print(f"Database connection error: {e}")
        traceback.print_exc()
        return None

@asynccontextmanager
async def get_db_context():
    """Async context manager for database operations"""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database connection unavailable")
    try:
        yield conn
    finally:
        conn.close()

# Session Management
class SessionManager:
    """Manages active study sessions and conversation context"""
    
    def __init__(self):
        self.active_sessions: Dict[str, StudySession] = {}
        self.session_locks: Dict[str, asyncio.Lock] = {}
    
    def create_session(self, user_id: str, subject: str, topic: str, mode: TutoringMode) -> StudySession:
        """Create a new study session"""
        session_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        session = StudySession(
            session_id=session_id,
            user_id=user_id,
            subject=subject,
            topic=topic,
            mode=mode,
            messages=[],
            created_at=now,
            last_activity=now,
            progress_data={
                "concepts_covered": [],
                "problems_solved": 0,
                "quiz_scores": [],
                "time_spent": 0,
                "difficulty_progression": []
            },
            context_summary=None
        )
        
        self.active_sessions[session_id] = session
        self.session_locks[session_id] = asyncio.Lock()
        
        return session
    
    def get_session(self, session_id: str) -> Optional[StudySession]:
        """Get an active session by ID"""
        return self.active_sessions.get(session_id)
    
    def update_session_activity(self, session_id: str):
        """Update session last activity timestamp"""
        if session_id in self.active_sessions:
            self.active_sessions[session_id].last_activity = datetime.utcnow()
    
    def add_message(self, session_id: str, role: MessageRole, content: str, metadata: Optional[Dict] = None):
        """Add a message to the session conversation"""
        if session_id in self.active_sessions:
            message = ConversationMessage(
                role=role,
                content=content,
                timestamp=datetime.utcnow(),
                metadata=metadata
            )
            self.active_sessions[session_id].messages.append(message)
    
    def get_conversation_context(self, session_id: str, max_messages: int = 10) -> List[Dict]:
        """Get conversation context for AI processing"""
        if session_id not in self.active_sessions:
            return []
        
        session = self.active_sessions[session_id]
        messages = session.messages[-max_messages:] if len(session.messages) > max_messages else session.messages
        
        # Filter out SYSTEM messages and only include USER and ASSISTANT messages
        # SYSTEM messages are handled separately in the API call
        conversation_messages = [
            {
                "role": msg.role.value,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat()
            }
            for msg in messages
            if msg.role.value in ["user", "assistant"]  # Exclude SYSTEM messages
        ]
        
        return conversation_messages
    
    def summarize_context(self, session_id: str) -> str:
        """Create a summary of the conversation context"""
        if session_id not in self.active_sessions:
            return ""
        
        session = self.active_sessions[session_id]
        if len(session.messages) < 5:
            return ""
        
        # Create a summary of key points discussed
        summary_prompt = f"""
        Summarize the key learning points from this tutoring session on {session.topic}:
        - Subject: {session.subject}
        - Mode: {session.mode.value}
        - Focus on main concepts, formulas, and problem-solving approaches discussed
        - Keep summary concise but comprehensive
        """
        
        # This would typically call the LLM to generate a summary
        # For now, return a basic summary
        return f"Session on {session.topic}: {len(session.messages)} messages exchanged, covering key concepts and problem-solving approaches."

# Initialize session manager
session_manager = SessionManager()

# Test function for message preparation (can be removed in production)
def test_message_preparation():
    """Test the message preparation logic for role alternation"""
    print("=== Testing Message Preparation ===")
    
    # Test case 1: Normal conversation
    test_messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": "How are you?"}
    ]
    
    system_prompt = "You are a helpful assistant."
    prepared = AIContentGenerator.prepare_conversation_messages(test_messages, system_prompt)
    
    print("Test 1 - Normal conversation:")
    for i, msg in enumerate(prepared):
        print(f"  {i}: {msg['role']} - {msg['content'][:50]}...")
    
    # Test case 2: Consecutive same roles
    test_messages_2 = [
        {"role": "user", "content": "First user message"},
        {"role": "user", "content": "Second user message"},
        {"role": "assistant", "content": "Assistant response"},
        {"role": "assistant", "content": "Another assistant response"}
    ]
    
    prepared_2 = AIContentGenerator.prepare_conversation_messages(test_messages_2, system_prompt)
    
    print("\nTest 2 - Consecutive same roles:")
    for i, msg in enumerate(prepared_2):
        print(f"  {i}: {msg['role']} - {msg['content'][:50]}...")
    
    # Test case 3: Empty messages
    prepared_3 = AIContentGenerator.prepare_conversation_messages([], system_prompt)
    
    print("\nTest 3 - Empty messages:")
    for i, msg in enumerate(prepared_3):
        print(f"  {i}: {msg['role']} - {msg['content'][:50]}...")
    
    print("=== End Testing ===")

# Uncomment the line below to run tests when the module is loaded
# test_message_preparation()

# AI Content Generation
class AIContentGenerator:
    """Handles AI-powered content generation for tutoring"""
    
    @staticmethod
    def create_system_prompt(mode: TutoringMode, subject: str, topic: str) -> str:
        """Create appropriate system prompt based on tutoring mode"""
        base_prompt = f"""You are an expert AI tutor specializing in {subject} for JEE preparation. 
        You are currently teaching the topic: {topic}.
        
        Your responses should be:
        - Clear and structured with proper markdown formatting
        - Include mathematical formulas using LaTeX notation ($$ for display, $ for inline)
        - Provide step-by-step explanations
        - Use examples and analogies when helpful
        - Encourage active learning and critical thinking
        """
        
        mode_prompts = {
            TutoringMode.EXPLAIN: f"{base_prompt}\n\nMode: EXPLANATION - Provide comprehensive topic explanations with formulas, proofs, and examples.",
            TutoringMode.SOLVE: f"{base_prompt}\n\nMode: PROBLEM SOLVING - Guide through problem-solving step by step with hints and complete solutions.",
            TutoringMode.PRACTICE: f"{base_prompt}\n\nMode: PRACTICE - Generate practice problems and provide detailed solutions.",
            TutoringMode.REVISE: f"{base_prompt}\n\nMode: REVISION - Create structured summaries and cheat sheets for quick revision.",
            TutoringMode.PLAN: f"{base_prompt}\n\nMode: STUDY PLANNING - Create personalized study plans with daily tasks and goals.",
            TutoringMode.QUIZ: f"{base_prompt}\n\nMode: QUIZ - Generate interactive quizzes with explanations and instant feedback."
        }
        
        return mode_prompts.get(mode, base_prompt)
    
    @staticmethod
    def prepare_conversation_messages(messages: List[Dict], system_prompt: str) -> List[Dict]:
        """
        Prepare conversation messages for Together AI API with strict role alternation.
        
        Together AI requires: system -> user -> assistant -> user -> assistant -> ...
        No consecutive messages with the same role are allowed.
        """
        # Start with system message
        prepared_messages = [{"role": "system", "content": system_prompt}]
        
        if not messages:
            return prepared_messages
        
        # Process conversation messages to ensure role alternation
        current_role = None
        merged_content = ""
        
        for msg in messages:
            msg_role = msg.get("role")
            msg_content = msg.get("content", "")
            
            # Skip messages without proper role/content
            if not msg_role or not msg_content:
                continue
            
            # If this is the first message after system, it must be user
            if current_role is None:
                if msg_role == "user":
                    prepared_messages.append({"role": "user", "content": msg_content})
                    current_role = "user"
                elif msg_role == "assistant":
                    # If first message is assistant, add a placeholder user message
                    prepared_messages.append({"role": "user", "content": "Please continue from where we left off."})
                    prepared_messages.append({"role": "assistant", "content": msg_content})
                    current_role = "assistant"
                continue
            
            # Check if role alternates properly
            if msg_role == current_role:
                # Same role - merge content
                merged_content += "\n\n" + msg_content
            else:
                # Different role - add the merged content from previous role
                if merged_content:
                    prepared_messages.append({"role": current_role, "content": merged_content})
                    merged_content = ""
                
                # Add current message
                prepared_messages.append({"role": msg_role, "content": msg_content})
                current_role = msg_role
        
        # Add any remaining merged content
        if merged_content:
            prepared_messages.append({"role": current_role, "content": merged_content})
        
        # Ensure we end with user role (Together AI requirement)
        if prepared_messages and prepared_messages[-1]["role"] == "assistant":
            # Add a placeholder user message to continue
            prepared_messages.append({"role": "user", "content": "Please continue."})
        
        return prepared_messages

    @staticmethod
    async def generate_response(
        messages: List[Dict],
        system_prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7
    ) -> str:
        """Generate AI response using the LLM"""
        try:
            # Prepare messages for the API with proper role alternation
            api_messages = AIContentGenerator.prepare_conversation_messages(messages, system_prompt)
            
            # Log the final message array for debugging
            print(f"=== Together AI API Messages ===")
            for i, msg in enumerate(api_messages):
                print(f"Message {i}: role={msg['role']}, content_length={len(msg['content'])}")
                if len(msg['content']) > 100:
                    print(f"  Content preview: {msg['content'][:100]}...")
                else:
                    print(f"  Content: {msg['content']}")
            print(f"================================")
            
            response = llm_client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=api_messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            print(f"Error generating AI response: {e}")
            traceback.print_exc()
            raise HTTPException(status_code=500, detail="Failed to generate AI response")
    
    @staticmethod
    async def get_syllabus_context(topic: str, subject: str) -> str:
        """Retrieve relevant syllabus content for context"""
        try:
            # Generate embedding for the topic
            topic_embedding = embedding_model.encode(topic).tolist()
            
            async with get_db_context() as conn:
                with conn.cursor() as cur:
                    # Find matching topics using semantic search
                    cur.execute("SELECT * FROM match_topics(%s::vector, 0.3, 5)", (topic_embedding,))
                    match_results = cur.fetchall()
                    
                    if not match_results:
                        return f"Topic: {topic} - General knowledge context"
                    
                    # Get the best match
                    best_match = match_results[0]
                    topic_id = best_match['id']
                    
                    # Fetch topic content
                    cur.execute("SELECT full_text FROM topics WHERE id = %s", (topic_id,))
                    topic_result = cur.fetchone()
                    
                    if topic_result and topic_result['full_text']:
                        return topic_result['full_text'][:5000]  # Limit context length
                    
                    return f"Topic: {topic} - Syllabus content available"
        
        except Exception as e:
            print(f"Error retrieving syllabus context: {e}")
            return f"Topic: {topic} - Context retrieval error"

# Quiz Generation
class QuizGenerator:
    """Handles quiz generation and management"""
    
    @staticmethod
    def parse_quiz_json(text: str) -> Optional[Dict]:
        """Parse quiz JSON from AI response with fallback regex parsing"""
        text = text.strip()
        # Remove markdown code blocks
        text = text.replace("```json", "").replace("```", "").strip()
        
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Fallback regex parsing
            import re
            try:
                question_match = re.search(r'"question":\s*"(.*?)"', text, re.DOTALL)
                options_match = re.search(r'"options":\s*{(.*?)}', text, re.DOTALL)
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
                
                return {
                    "question": question,
                    "options": options,
                    "correct_answer": correct_answer,
                    "explanation": explanation
                }
            
            except Exception as e:
                print(f"Regex parsing error: {e}")
                return None

# Study Plan Generator
class StudyPlanGenerator:
    """Handles personalized study plan generation"""
    
    @staticmethod
    async def generate_study_plan(request: StudyPlanRequest) -> StudyPlan:
        """Generate a personalized study plan"""
        plan_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        # Create system prompt for study plan generation
        system_prompt = f"""You are an expert educational planner specializing in JEE preparation.
        
        Create a detailed, personalized study plan with the following requirements:
        - Subjects: {', '.join(request.subjects)}
        - Duration: {request.duration_days} days
        - Goals: {', '.join(request.goals)}
        - Current Level: {request.current_level}
        
        The plan should include:
        1. Daily tasks with specific topics and time allocations
        2. Weekly milestones and progress checkpoints
        3. Practice and revision schedules
        4. Difficulty progression recommendations
        5. Resource recommendations
        
        Format the response as a structured JSON with daily_tasks array.
        """
        
        user_message = f"Generate a comprehensive study plan for JEE preparation covering {', '.join(request.subjects)} over {request.duration_days} days."
        
        try:
            response = await AIContentGenerator.generate_response(
                messages=[{"role": "user", "content": user_message}],
                system_prompt=system_prompt,
                max_tokens=3072,
                temperature=0.5
            )
            
            # Parse the response to extract daily tasks
            # This is a simplified implementation - in production, you'd want more robust parsing
            daily_tasks = []
            for day in range(1, request.duration_days + 1):
                daily_tasks.append({
                    "day": day,
                    "subjects": request.subjects,
                    "topics": f"Day {day} topics",
                    "time_allocation": "2-3 hours",
                    "tasks": ["Study", "Practice", "Review"],
                    "milestones": f"Complete Day {day} objectives"
                })
            
            plan = StudyPlan(
                plan_id=plan_id,
                user_id=request.user_id,
                subjects=request.subjects,
                duration_days=request.duration_days,
                goals=request.goals,
                daily_tasks=daily_tasks,
                created_at=now,
                progress={"completed_days": 0, "overall_progress": 0.0}
            )
            
            return plan
        
        except Exception as e:
            print(f"Error generating study plan: {e}")
            raise HTTPException(status_code=500, detail="Failed to generate study plan")

# API Routes
@router.get("/status")
async def get_status():
    """Health check endpoint for the agentic module"""
    return {
        "status": "active",
        "module": "Deep Study Mode",
        "active_sessions": len(session_manager.active_sessions),
        "timestamp": datetime.utcnow().isoformat()
    }

@router.post("/session/start")
async def start_study_session(request: StartSessionRequest):
    """Start a new Deep Study Mode session"""
    try:
        # Create new session
        session = session_manager.create_session(
            user_id=request.user_id,
            subject=request.subject,
            topic=request.topic,
            mode=request.mode
        )
        
        # Get syllabus context
        syllabus_context = await AIContentGenerator.get_syllabus_context(
            request.topic, request.subject
        )
        
        # Create initial system message
        system_prompt = AIContentGenerator.create_system_prompt(
            request.mode, request.subject, request.topic
        )
        
        # Generate welcome message
        welcome_message = f"""Welcome to Deep Study Mode! 

**Subject:** {request.subject}
**Topic:** {request.topic}
**Mode:** {request.mode.value.title()}

I'm here to help you master this topic through interactive learning. Let's begin!

**Available Commands:**
- Ask questions about concepts
- Request step-by-step explanations
- Get help with problem solving
- Take practice quizzes
- Generate study materials

What would you like to explore first?"""
        
        # Add initial messages to session
        session_manager.add_message(
            session.session_id,
            MessageRole.SYSTEM,
            system_prompt
        )
        
        session_manager.add_message(
            session.session_id,
            MessageRole.ASSISTANT,
            welcome_message,
            {"type": "welcome", "context": syllabus_context[:500]}
        )
        
        return {
            "session_id": session.session_id,
            "welcome_message": welcome_message,
            "subject": session.subject,
            "topic": session.topic,
            "mode": session.mode.value,
            "created_at": session.created_at.isoformat()
        }
    
    except Exception as e:
        print(f"Error starting session: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to start study session")

@router.post("/session/chat")
async def chat_message(request: ChatMessageRequest):
    """Send a message in an active study session"""
    try:
        # Get session
        session = session_manager.get_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Update activity
        session_manager.update_session_activity(request.session_id)
        
        # Get conversation context BEFORE adding new user message
        conversation_context = session_manager.get_conversation_context(request.session_id)
        
        # Log the conversation context for debugging
        print(f"=== Chat Conversation Context ===")
        print(f"Session ID: {request.session_id}")
        print(f"Context messages count: {len(conversation_context)}")
        for i, msg in enumerate(conversation_context):
            print(f"  Context {i}: role={msg['role']}, content_length={len(msg['content'])}")
        print(f"================================")
        
        # Create system prompt
        system_prompt = AIContentGenerator.create_system_prompt(
            session.mode, session.subject, session.topic
        )
        
        # Add context hint if provided
        if request.context_hint:
            system_prompt += f"\n\nContext Hint: {request.context_hint}"
        
        # Generate response using existing conversation context
        response = await AIContentGenerator.generate_response(
            messages=conversation_context,
            system_prompt=system_prompt,
            max_tokens=2048,
            temperature=0.7
        )
        
        # Add user message to session AFTER generating response
        session_manager.add_message(
            request.session_id,
            MessageRole.USER,
            request.message
        )
        
        # Add assistant response to session
        session_manager.add_message(
            request.session_id,
            MessageRole.ASSISTANT,
            response
        )
        
        return {
            "session_id": request.session_id,
            "response": response,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        print(f"Error in chat: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to process chat message")

@router.post("/session/solve")
async def problem_solve(request: ProblemSolveRequest):
    """Get step-by-step problem solving assistance"""
    try:
        # Get session
        session = session_manager.get_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Update activity
        session_manager.update_session_activity(request.session_id)
        
        # Create problem-solving prompt
        hint_levels = {
            1: "Provide a gentle hint to guide the student",
            2: "Give a more detailed hint with partial solution",
            3: "Provide a complete step-by-step solution"
        }
        
        system_prompt = f"""You are an expert problem-solving tutor for {session.subject}.
        
        Problem: {request.problem}
        Current Step: {request.step}
        Hint Level: {request.hint_level} - {hint_levels[request.hint_level]}
        
        Provide a {hint_levels[request.hint_level].lower()} that:
        - Guides the student through the problem-solving process
        - Explains the reasoning behind each step
        - Uses clear mathematical notation with LaTeX
        - Encourages critical thinking
        - Builds problem-solving skills
        """
        
        # Generate response
        response = await AIContentGenerator.generate_response(
            messages=[{"role": "user", "content": f"Help me solve: {request.problem}"}],
            system_prompt=system_prompt,
            max_tokens=2048,
            temperature=0.6
        )
        
        # Add to session
        session_manager.add_message(
            request.session_id,
            MessageRole.ASSISTANT,
            response,
            {"type": "problem_solve", "step": request.step, "hint_level": request.hint_level}
        )
        
        return {
            "session_id": request.session_id,
            "solution": response,
            "step": request.step,
            "hint_level": request.hint_level,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        print(f"Error in problem solving: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to generate problem solution")

@router.post("/session/quiz")
async def generate_quiz(request: QuizRequest):
    """Generate an interactive quiz for the session"""
    try:
        # Get session
        session = session_manager.get_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Update activity
        session_manager.update_session_activity(request.session_id)
        
        # Create quiz generation prompt
        system_prompt = f"""You are an expert quiz generator for {session.subject}.
        
        Generate a {request.difficulty} difficulty quiz with {request.question_count} questions about {session.topic}.
        
        Format each question as JSON:
        {{
            "question": "Question text with LaTeX math notation",
            "options": {{"A": "option A", "B": "option B", "C": "option C", "D": "option D"}},
            "correct_answer": "A",
            "explanation": "Detailed explanation of the correct answer"
        }}
        
        Return an array of {request.question_count} such objects.
        """
        
        # Generate quiz
        response = await AIContentGenerator.generate_response(
            messages=[{"role": "user", "content": f"Generate a {request.difficulty} quiz about {session.topic}"}],
            system_prompt=system_prompt,
            max_tokens=3072,
            temperature=0.5
        )
        
        # Parse quiz JSON
        try:
            # Try to parse as JSON array
            quiz_data = json.loads(response)
            if isinstance(quiz_data, list):
                questions = quiz_data
            else:
                questions = [quiz_data]
        except json.JSONDecodeError:
            # Fallback: try to extract individual questions
            questions = []
            import re
            question_blocks = re.findall(r'\{[^{}]*"question"[^{}]*\}', response, re.DOTALL)
            for block in question_blocks:
                parsed = QuizGenerator.parse_quiz_json(block)
                if parsed:
                    questions.append(parsed)
        
        if not questions:
            raise HTTPException(status_code=500, detail="Failed to generate valid quiz questions")
        
        # Add quiz to session
        session_manager.add_message(
            request.session_id,
            MessageRole.ASSISTANT,
            f"Generated {len(questions)} quiz questions",
            {"type": "quiz", "questions": questions, "difficulty": request.difficulty}
        )
        
        return {
            "session_id": request.session_id,
            "questions": questions,
            "difficulty": request.difficulty,
            "question_count": len(questions),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        print(f"Error generating quiz: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to generate quiz")

@router.post("/plan/generate")
async def generate_study_plan(request: StudyPlanRequest):
    """Generate a personalized study plan"""
    try:
        plan = await StudyPlanGenerator.generate_study_plan(request)
        
        return {
            "plan_id": plan.plan_id,
            "subjects": plan.subjects,
            "duration_days": plan.duration_days,
            "goals": plan.goals,
            "daily_tasks": plan.daily_tasks,
            "created_at": plan.created_at.isoformat(),
            "progress": plan.progress
        }
    
    except Exception as e:
        print(f"Error generating study plan: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to generate study plan")

@router.get("/session/{session_id}")
async def get_session_info(session_id: str):
    """Get information about an active session"""
    try:
        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {
            "session_id": session.session_id,
            "user_id": session.user_id,
            "subject": session.subject,
            "topic": session.topic,
            "mode": session.mode.value,
            "created_at": session.created_at.isoformat(),
            "last_activity": session.last_activity.isoformat(),
            "message_count": len(session.messages),
            "progress": session.progress_data
        }
    
    except Exception as e:
        print(f"Error getting session info: {e}")
        raise HTTPException(status_code=500, detail="Failed to get session information")

@router.get("/session/{session_id}/history")
async def get_session_history(session_id: str, limit: int = 20):
    """Get conversation history for a session"""
    try:
        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Get recent messages
        recent_messages = session.messages[-limit:] if len(session.messages) > limit else session.messages
        
        return {
            "session_id": session_id,
            "messages": [
                {
                    "role": msg.role.value,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                    "metadata": msg.metadata
                }
                for msg in recent_messages
            ],
            "total_messages": len(session.messages)
        }
    
    except Exception as e:
        print(f"Error getting session history: {e}")
        raise HTTPException(status_code=500, detail="Failed to get session history")

@router.delete("/session/{session_id}")
async def end_session(session_id: str):
    """End an active study session"""
    try:
        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Create session summary
        summary = session_manager.summarize_context(session_id)
        
        # Remove from active sessions
        if session_id in session_manager.active_sessions:
            del session_manager.active_sessions[session_id]
        
        if session_id in session_manager.session_locks:
            del session_manager.session_locks[session_id]
        
        return {
            "session_id": session_id,
            "status": "ended",
            "summary": summary,
            "duration_minutes": int((datetime.utcnow() - session.created_at).total_seconds() / 60),
            "message_count": len(session.messages)
        }
    
    except Exception as e:
        print(f"Error ending session: {e}")
        raise HTTPException(status_code=500, detail="Failed to end session")

# Background task for session cleanup
async def cleanup_expired_sessions():
    """Clean up expired sessions periodically"""
    while True:
        try:
            now = datetime.utcnow()
            expired_sessions = []
            
            for session_id, session in session_manager.active_sessions.items():
                if (now - session.last_activity).total_seconds() > (MAX_SESSION_DURATION * 3600):
                    expired_sessions.append(session_id)
            
            for session_id in expired_sessions:
                print(f"Cleaning up expired session: {session_id}")
                if session_id in session_manager.active_sessions:
                    del session_manager.active_sessions[session_id]
                if session_id in session_manager.session_locks:
                    del session_manager.session_locks[session_id]
            
            if expired_sessions:
                print(f"Cleaned up {len(expired_sessions)} expired sessions")
        
        except Exception as e:
            print(f"Error in session cleanup: {e}")
        
        # Run cleanup every hour
        await asyncio.sleep(3600)

# Start background cleanup task
@router.on_event("startup")
async def startup_event():
    """Initialize background tasks on startup"""
    asyncio.create_task(cleanup_expired_sessions())
    print("Deep Study Mode agentic module initialized")

# Export the router
__all__ = ["router"]