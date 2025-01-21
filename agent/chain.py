from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from pathlib import Path
from .processor import TaskProcessor
import json
import tempfile

@dataclass
class ChainStep:
    """Represents a step in the task chain with its associated tasks."""
    name: str
    tasks: List[str]  # List of task names to be executed in this step
    input_files: Optional[List[Path]] = None  # Optional list of input files
    expect_json: bool = False  # Add flag for JSON output
    store_result: bool = False  # New flag to store result for next step
    use_previous_result: bool = False  # New flag to use previous step's result
    stop_at: Optional[str] = None  # New: String pattern to stop generation
    max_iterations: int = 5  # New: Maximum number of continuation attempts
    additional_context: Optional[str] = None  # New field for additional context
    
    def __post_init__(self):
        """Validate the step configuration after initialization."""
        if not self.name:
            raise ValueError("Step name cannot be empty")
        if not self.tasks:
            raise ValueError("Step must contain at least one task")

class TaskChain:
    """Manages the sequential processing of tasks in steps."""
    
    def __init__(self, task_processor: TaskProcessor, tasks_config: Dict[str, Dict[str, Any]], steps: List[ChainStep]):
        """Initialize the task chain with a processor, configuration, and steps."""
        self.processor = task_processor
        self.tasks_config = tasks_config
        self.steps = steps
        self.previous_result = None  # Store previous step result
        self.validate_config()
        self.validate_steps()
    
    def validate_config(self):
        """Validate that all required tasks exist in the configuration."""
        if not self.tasks_config:
            raise ValueError("Tasks configuration cannot be empty")
        
        required_keys = ['system_instruction', 'user_message']
        for task_name, task_config in self.tasks_config.items():
            missing_keys = [key for key in required_keys if key not in task_config]
            if missing_keys:
                raise ValueError(f"Task '{task_name}' is missing required keys: {missing_keys}")
    
    def validate_steps(self):
        """Validate all steps and their tasks exist in configuration."""
        if not self.steps:
            raise ValueError("Steps list cannot be empty")
            
        for step in self.steps:
            missing_tasks = [task for task in step.tasks if task not in self.tasks_config]
            if missing_tasks:
                raise ValueError(f"Step '{step.name}' contains undefined tasks: {missing_tasks}")
    
    def process_step(self, step: ChainStep, content: str) -> Optional[str]:
        """Process all tasks in a single step sequentially."""
        print(f"\n📎 Processing step: {step.name}")
        
        # Use previous result if specified
        if step.use_previous_result and self.previous_result:
            content = self.previous_result
            
        # Add additional context if provided
        if step.additional_context:
            content = f"Additional Context:\n{step.additional_context}\n\n{content}"
        
        # Upload input files if provided
        uploaded_files = self._handle_file_uploads(step)
        
        current_content = content
        iterations = 0
        last_valid_json = None  # Track the last valid JSON response
        should_stop = False
        
        while iterations < step.max_iterations:
            for task_name in step.tasks:
                print(f"\n→ Executing task ({iterations + 1}/{step.max_iterations}): {task_name}")
                task_config = self.tasks_config[task_name].copy()
                
                # Modified continuation logic for JSON
                if iterations > 0 and step.expect_json:
                    try:
                        # Try to parse current content as JSON
                        parsed_json = json.loads(current_content)
                        last_valid_json = current_content
                        # If we have valid JSON, we're done
                        should_stop = True
                        break
                    except json.JSONDecodeError as e:
                        # If JSON is incomplete, modify the prompt to continue it
                        task_config["user_message"] = (
                            "Continue completing this JSON structure. Here's the partial JSON:\n\n"
                            f"{current_content}\n\n"
                            "Complete the JSON structure, ensuring it's valid.\n"
                            "Do not repeat any previous content, only provide the missing parts."
                        )
                elif iterations > 0:
                    # Regular text continuation logic
                    last_chunk = self._get_last_chunk(current_content)
                    task_config["user_message"] = (
                        "Continue exactly from where this text ends. "
                        "Do not repeat any previous content. Here's the last part:\n\n"
                        f"{last_chunk}\n\n"
                        "Continue the text from this point, providing only new content:\n"
                    )
                
                try:
                    result = self.processor.process_task(
                        task_name, 
                        task_config, 
                        current_content,
                        expect_json=step.expect_json,
                        files=uploaded_files
                    )
                    
                    if result:
                        if iterations > 0:
                            if step.expect_json:
                                # For JSON, try to combine the results
                                try:
                                    combined_json = self._combine_json_content(current_content, result)
                                    current_content = combined_json
                                except json.JSONDecodeError:
                                    current_content = result  # Use new result if combination fails
                            else:
                                # Text content handling
                                overlap = self._find_overlap(current_content, result)
                                if overlap > 0:
                                    result = result[overlap:]
                                if result.strip():
                                    current_content += result
                        else:
                            current_content = result
                        
                        # Validate JSON if expected
                        if step.expect_json:
                            try:
                                json.loads(current_content)
                                should_stop = True
                                last_valid_json = current_content
                            except json.JSONDecodeError:
                                if iterations >= step.max_iterations - 1:
                                    if last_valid_json:
                                        current_content = last_valid_json
                                        should_stop = True
                                    else:
                                        raise Exception("Failed to get complete JSON response")
                    else:
                        print(f"❌ Step failed at task: {task_name}")
                        return None
                except Exception as e:
                    print(f"❌ Error in task {task_name}: {str(e)}")
                    if last_valid_json and step.expect_json:
                        return last_valid_json
                    return None
            
            if should_stop or (not step.stop_at and not step.expect_json):
                break
                
            if step.stop_at and step.stop_at in current_content:
                break
            
            iterations += 1
            
        self.previous_result = current_content
        return current_content

    def _combine_json_content(self, current: str, new: str) -> str:
        """Attempt to combine two JSON contents intelligently."""
        try:
            current_json = json.loads(current) if current.strip() else {}
            new_json = json.loads(new) if new.strip() else {}
            
            # If both are valid JSON, merge them
            if isinstance(current_json, dict) and isinstance(new_json, dict):
                # Merge logic for topics
                if "topics" in current_json and "topics" in new_json:
                    current_json["topics"].extend(new_json["topics"])
                    # Remove duplicates based on topic names
                    seen = set()
                    unique_topics = []
                    for topic in current_json["topics"]:
                        if topic["topic"] not in seen:
                            seen.add(topic["topic"])
                            unique_topics.append(topic)
                    current_json["topics"] = unique_topics
                
                return json.dumps(current_json, indent=2)
        except json.JSONDecodeError:
            pass
        
        return new  # Return new content if combination fails

    def _handle_file_uploads(self, step: ChainStep) -> Optional[List[Any]]:
        """Handle file uploads for a step."""
        if not step.input_files:
            return None
            
        uploaded_files = []
        for file_path in step.input_files:
            mime_type = "application/pdf" if file_path.suffix.lower() == ".pdf" else None
            uploaded_file = self.processor.upload_file(str(file_path), mime_type=mime_type)
            uploaded_files.append(uploaded_file)
        
        self.processor.wait_for_files_active(uploaded_files)
        return uploaded_files
    
    def _get_last_chunk(self, text: str, chunk_size: int = 200) -> str:
        """Get the last meaningful chunk of text (complete sentence or JSON structure)."""
        if not text:
            return ""        
        text_chunk = text[-chunk_size:]
        return text_chunk

    def _find_overlap(self, original: str, new_text: str, min_overlap: int = 20) -> int:
        """Enhanced overlap detection between original and new text."""
        if not original or not new_text:
            return 0
            
        original_end = original[-500:]  # Look at last 500 chars of original
        
        # Try different overlap sizes, from largest to smallest
        for i in range(len(original_end), min_overlap - 1, -1):
            if original_end[-i:].lower() == new_text[:i].lower():  # Case-insensitive comparison
                return i
                    
        return 0
    
    def run(self, initial_content: str) -> Optional[str]:
        """Run all steps in the chain sequentially."""
        print("🔄 Starting task chain execution...")
        
        current_content = initial_content
        for step in self.steps:
            result = self.process_step(step, current_content)
            if result:
                current_content = result
            else:
                raise Exception(f"❌ Chain failed at step: {step.name}")
        
        print("✨ Task chain completed successfully")
        return current_content 