import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from datetime import datetime
import traceback
from functools import wraps
import time
from typing import Optional, Dict, Any, List
from pathlib import Path

def retry_on_error(max_retries=3):
    """Decorator to retry operations on failure."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        print(f"❌ Failed after {max_retries} attempts: {func.__name__}")
                        raise Exception(f"Error: {str(e)} Trace: {traceback.format_exc()}")
                    print(f"⚠️ Attempt {attempt + 1}/{max_retries} failed, retrying...")
                    time.sleep(2 ** attempt)
            return None
        return wrapper
    return decorator

class TaskProcessor:
    SAFETY_SETTINGS = {
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE
    }

    def __init__(self, api_key: str):
        """Initialize the task processor with API key."""
        self.api_key = api_key
        genai.configure(api_key=api_key)
        
    def create_model(self, task_config: Dict[str, Any]) -> genai.GenerativeModel:
        """Create a Gemini model configured for the specific task."""
        model_config = {
            "temperature": task_config.get("temperature", 1),
            "top_p": task_config.get("top_p", 0.95),
            "top_k": task_config.get("top_k", 40),
            "max_output_tokens": task_config.get("max_output_tokens", 8192),
            "response_mime_type": task_config.get("response_mime_type", "text/plain")
        }

        return genai.GenerativeModel(
            model_name=task_config.get("model_name", "gemini-2.0-flash-exp"),
            generation_config=model_config,
            safety_settings=self.SAFETY_SETTINGS,
            system_instruction=task_config["system_instruction"]
        )

    @retry_on_error(max_retries=3)
    def upload_file(self, file_path: str, mime_type: Optional[str] = None) -> Any:
        """Upload a file to Gemini."""
        print(f"Uploading file: {file_path}")
        file = genai.upload_file(file_path, mime_type=mime_type)
        print(f"✓ Uploaded file '{file.display_name}' as: {file.uri}")
        return file

    def wait_for_files_active(self, files: List[Any]) -> None:
        """Wait for uploaded files to be processed."""
        print("Waiting for file processing...")
        for name in (file.name for file in files):
            file = genai.get_file(name)
            while file.state.name == "PROCESSING":
                print(".", end="", flush=True)
                time.sleep(10)
                file = genai.get_file(name)
            if file.state.name != "ACTIVE":
                raise Exception(f"File {file.name} failed to process")
        print("...all files ready")

    @retry_on_error(max_retries=3)
    def process_task(self, task_name: str, task_config: Dict[str, Any], content: str, 
                    files: Optional[List[Any]] = None) -> Optional[str]:
        """Process a single task using the Gemini API."""
        print(f"Processing task: {task_name}")
        
        # Create model for this specific task
        model = self.create_model(task_config)
        
        # Initialize chat with files if provided
        history = []
        if files:
            for file in files:
                history.append({
                    "role": "user",
                    "parts": [file],
                })
            chat = model.start_chat(history=history)
        else:
            chat = model.start_chat()

        if task_config["user_message"] and "{content}" in task_config["user_message"]:
            user_content = task_config["user_message"].format(content=content)
        else:
            user_content = content

        # Send content and get response
        response = chat.send_message(user_content)
        
        if response.text:
            print(f"✓ Successfully completed task: {task_name}")
            return response.text
        else:
            print(f"❌ Failed to process task: {task_name}")
            return None

