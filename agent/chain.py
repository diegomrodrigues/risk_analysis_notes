from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from pathlib import Path
from .processor import TaskProcessor
import json

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
        uploaded_files = None
        if step.input_files:
            uploaded_files = []
            for file_path in step.input_files:
                mime_type = "application/pdf" if file_path.suffix.lower() == ".pdf" else None
                uploaded_file = self.processor.upload_file(str(file_path), mime_type=mime_type)
                uploaded_files.append(uploaded_file)
            
            # Wait for files to be processed
            self.processor.wait_for_files_active(uploaded_files)
        
        current_content = content
        iterations = 0
        
        while iterations < step.max_iterations:
            for task_name in step.tasks:
                print(f"\n→ Executing task ({iterations + 1}/{step.max_iterations}): {task_name}")
                task_config = self.tasks_config[task_name].copy()
                
                # Add JSON response type if step expects JSON
                if step.expect_json:
                    task_config["response_mime_type"] = "application/json"
                
                # If not first iteration, modify user message to continue
                if iterations > 0:
                    task_config["user_message"] = "Continue exactly from where you stopped precisely without rewriting previous content"
                
                try:
                    result = self.processor.process_task(
                        task_name, 
                        task_config, 
                        current_content,
                        files=uploaded_files
                    )
                    
                    if result:
                        if iterations > 0:
                            # Append new content for continuations
                            current_content += result
                        else:
                            current_content = result

                        # Validate JSON if expected
                        if step.expect_json:
                            try:
                                json.loads(current_content)
                                # If JSON is valid, we can break the iteration loop
                                break
                            except json.JSONDecodeError:
                                # Continue iterations if JSON is incomplete
                                if iterations < step.max_iterations - 1:
                                    continue
                                else:
                                    raise Exception("❌ Failed to get complete JSON response after max iterations")

                    else:
                        print(f"❌ Step failed at task: {task_name}")
                        return None
                except Exception as e:
                    print(f"❌ Error in task {task_name}: {str(e)}")
                    return None
            
            # Check if we should stop based on the stop pattern
            if step.stop_at and step.stop_at in current_content:
                break
                
            # Only continue if we have a stop pattern and haven't reached it
            if not step.stop_at:
                break
                
            iterations += 1
            if iterations == step.max_iterations:
                print(f"⚠️ Reached maximum iterations ({step.max_iterations}) without finding stop pattern")
        
        # Store result if specified
        if step.store_result:
            self.previous_result = current_content
        
        print(f"✓ Completed step: {step.name}")
        return current_content
    
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