from functools import wraps
import time
import traceback
import yaml
import os
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from agent.processor import TaskProcessor
from agent.chain import TaskChain, ChainStep
from agent.filename_handler import FilenameHandler

CONTEXT = "Expert Financial Risk Analysis using Value at Risk Models"
EXCLUDED_FOLDERS = []

# Default perspectives for topic generation
PERSPECTIVES = [
    # Math (2x)
    "Foque nos aspectos matemáticos e fórmulas, incluindo definições formais, teoremas, provas e demonstrações matemáticas.",
    "Foque nos aspectos matemáticos e fórmulas, incluindo definições formais, teoremas, provas e demonstrações matemáticas.",
    
    # Finance (2x)
    "Foque nos conceitos financeiros e econômicos, incluindo aplicações práticas, interpretações e implicações para o mercado.",
    "Foque nos conceitos financeiros e econômicos, incluindo aplicações práticas, interpretações e implicações para o mercado.",
    
    # Computing (2x)
    "Foque nos aspectos computacionais e algorítmicos, incluindo complexidade, implementação e otimização.",
    "Foque nos aspectos computacionais e algorítmicos, incluindo complexidade, implementação e otimização."
]
NUM_TOPICS = len(PERSPECTIVES) or 5
MAX_PREVIOUS_TASKS = 5

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

def get_pdf_files(directory: Path) -> list[Path]:
    """Get all PDF files in the directory."""
    return list(directory.glob("*.pdf"))

def load_tasks_config(tasks_dir: str = './agent/tasks') -> dict:
    """Load all YAML files from the tasks directory into a single config dictionary."""
    tasks_config = {}
    tasks_path = Path(tasks_dir)
    for yaml_file in tasks_path.glob('*.yaml'):
        with open(yaml_file, 'r') as f:
            config = yaml.safe_load(f)
            tasks_config.update(config)
    return tasks_config

@retry_on_error(max_retries=3)
def generate_topics(directory: Path, processor: TaskProcessor, tasks_config: dict, 
                   perspectives: list[str] = None, num_topics: int = None) -> str:
    """Generate topics.json for a directory."""
    print(f"\nGenerating topics for directory: {directory}")
    
    if perspectives is None and num_topics is None:
        raise ValueError("You should provide either perspectives or num_topics")

    if perspectives is not None:
        num_topics = len(perspectives)
    
    pdf_files = get_pdf_files(directory)
    if not pdf_files:
        raise ValueError("No PDF files found in the directory")

    # Generate N separate topic JSONs
    all_topics_results = []
    for i in range(num_topics):
        print(f"\nGenerating topics set {i+1}/{num_topics}")
        topics_chain = TaskChain(processor, tasks_config, [
            ChainStep(
                name=f"Generate Topics Set {i+1}",
                tasks=["create_topics"],
                input_files=pdf_files,
                expect_json=True,
                max_iterations=3
            )
        ])
        
        topics_result = topics_chain.run(perspectives[i] if perspectives else "")
        if not topics_result:
            raise Exception(f"Failed to generate topics set {i+1}")
        all_topics_results.append(topics_result)

    # Merge topics
    merge_chain = TaskChain(processor, tasks_config, [
        ChainStep(
            name="Merge Topics",
            tasks=["merge_topics"],
            expect_json=True,
            max_iterations=5
        )
    ])
    
    merged_result = merge_chain.run("\n".join(all_topics_results))
    if not merged_result:
        raise Exception("Failed to merge topics")
    
    # Save and return merged topics
    output_file = directory / "topics.json"
    output_file.write_text(merged_result, encoding='utf-8')
    print(f"✔️ Topics generated and saved to: {output_file}")
    return merged_result

def process_topic_wrapper(args) -> tuple[str, bool]:
    """Wrapper function for process_topic to work with ThreadPoolExecutor."""
    directory, section_name, topic, content, processor, tasks_config = args
    success = process_topic(directory, section_name, topic, content, processor, tasks_config)
    return topic, success

def process_section_topic(directory: Path, section_name: str, topic: str, pdf_files: list[Path],
                         processor: TaskProcessor, tasks_config: dict, previous_topics: list[tuple[str, str]] = None,
                         max_previous_topics: int = 3) -> Optional[tuple[str, str]]:
    """Process a single topic within a section."""
    print(f"Processing topic: {topic[:50]}...")
    
    additional_context = ""
    if previous_topics:
        additional_context = "\n\nPrevious Topics:\n"
        for prev_topic, prev_content in previous_topics[-max_previous_topics:]:
            additional_context += f"--- START {prev_topic} ---\n{prev_content}\n"
            additional_context += f"--- END {prev_topic} ---\n"
    
    steps = [
        ChainStep(
            name="Generate Initial Draft",
            tasks=["generate_draft_task"],
            input_files=pdf_files,
            stop_at="# Conclusão",
            max_iterations=3,
            additional_context=additional_context
        ),
        ChainStep(
            name="Review and Enhance",
            tasks=[
                "cleanup_task",
                "generate_logical_steps_task",
                "generate_logical_steps_task",
                "generate_logical_steps_task",
                "generate_step_proofs_task",
                "generate_examples_task",
                "create_diagrams_task",
                "format_math_task",
                "cleanup_task"
            ],
            stop_at="# Conclusão",
            max_iterations=3
        )
    ]
    
    chain = TaskChain(processor, tasks_config, steps)
    
    try:
        input = (
            f"CONTEXT_PLACEHOLDER = {CONTEXT} e {directory} \n"
            f"TOPIC_PLACEHOLDER = {section_name} \n"
            f"SUBTOPIC_PLACEHOLDER = {topic}"
        )

        print(f"- Generating text from input = {input}")

        final_content = chain.run(input)
        if final_content:
            return topic, final_content
    except Exception as e:
        print(f"❌ Error processing topic {topic}: {str(e)}")
        raise e
    
    return None

@retry_on_error(max_retries=3)
def process_topic(directory: Path, section_name: str, topic: str, content: str, 
                 processor: TaskProcessor, tasks_config: dict) -> bool:
    """Process a single topic and save it to a file."""
    try:
        filename_handler = FilenameHandler(processor, tasks_config)
        section_dir = filename_handler.create_section_directory(directory, section_name)
        result = filename_handler.generate_filename(section_dir, topic)
        
        if result.exists:
            print(f"⚠️ Similar topic already exists: {result.filename}")
            return True
        
        result.path.write_text(content, encoding='utf-8')
        print(f"✔️ Saved topic to: {result.filename}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to process topic: {str(e)}")
        return False

def process_section(directory: Path, section_name: str, section_topics: list[str],
                   pdf_files: list[Path], processor: TaskProcessor, tasks_config: dict,
                   max_previous_topics: int = 5) -> None:
    """Process all topics within a section sequentially."""
    print(f"\nProcessing section: {section_name} with {len(section_topics)} topics...")
    
    previous_topics = []
    
    for topic in section_topics:
        try:
            result = process_section_topic(
                directory, 
                section_name, 
                topic, 
                pdf_files, 
                processor, 
                tasks_config,
                previous_topics,
                max_previous_topics
            )
            
            if result:
                topic, content = result
                success = process_topic(directory, section_name, topic, content, processor, tasks_config)
                if success:
                    print(f"✔️ Topic processed and saved successfully: {topic}")
                    previous_topics.append((topic, content))
                else:
                    print(f"❌ Failed to save topic: {topic}")
            else:
                print(f"❌ Failed to process topic")
        except Exception as e:
            print(f"❌ Error processing topic {topic}: {str(e)}")

def read_topics_file(directory: Path) -> str:
    """Read and find the topics.json file in the given directory."""
    topics_file = directory / "topics.json"
    if topics_file.exists():
        return topics_file.read_text(encoding='utf-8')
    raise FileNotFoundError("topics.json not found in the specified directory")

@retry_on_error(max_retries=5)
def process_directory(directory: Path, processor: TaskProcessor, tasks_config: dict, max_workers: int = 3) -> None:
    """Process a single directory with its sections using parallel processing."""
    print(f"\nProcessing directory: {directory}")
    
    pdf_files = get_pdf_files(directory)
    if not pdf_files:
        print("No PDF files found in the directory, skipping...")
        return

    try:
        topics_content = read_topics_file(directory)
        topics_data = json.loads(topics_content)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for topic_obj in topics_data["topics"]:
                section_name = topic_obj["topic"]
                section_topics = topic_obj["sub_topics"]
                
                future = executor.submit(
                    process_section,
                    directory,
                    section_name,
                    section_topics,
                    pdf_files,
                    processor,
                    tasks_config,
                    MAX_PREVIOUS_TASKS
                )
                futures.append(future)

            for future in futures:
                future.result()

    except Exception as e:
        print(f"❌ Failed to process directory: {directory}")
        print(f"Error: {str(e)}")
        raise

def process_directory_with_topics(directory: Path, processor: TaskProcessor, 
                                tasks_config: dict, max_workers: int = 3) -> None:
    """Generate topics and process them for a directory."""
    try:
        # First, generate topics if they don't exist
        topics_file = directory / "topics.json"
        if not topics_file.exists():
            generate_topics(
                directory, 
                processor, 
                tasks_config, 
                perspectives=PERSPECTIVES,
                num_topics=NUM_TOPICS
            )
        
        # Then process the topics
        process_directory(directory, processor, tasks_config, max_workers)
        
    except Exception as e:
        print(f"❌ Failed to process directory: {directory}")
        print(f"Error: {str(e)}")
        raise

def get_numbered_folders(base_dir: Path) -> list[str]:
    """Get all numbered folders from the base directory."""
    folders = [
        folder.name for folder in base_dir.iterdir()
        if folder.is_dir() 
        and folder.name.strip()[0].isdigit()
        and folder.name not in EXCLUDED_FOLDERS
    ]
    return sorted(folders)

def main():
    # Load configuration and initialize processor
    tasks_config = load_tasks_config()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is required")
    processor = TaskProcessor(api_key=api_key)
    
    # Define base directory and settings
    base_dir = Path("/content/risk_analysis_notes/01. Value at Risk Models")
    target_folders = []  # Empty list means process all folders
    max_workers = 2
    
    # Get all folders if none specified
    if not target_folders:
        target_folders = get_numbered_folders(base_dir)
    
    # Process each target directory
    for folder in target_folders:
        directory = base_dir / folder
        if directory.exists():
            process_directory_with_topics(directory, processor, tasks_config, max_workers)
        else:
            print(f"Directory not found: {directory}")

if __name__ == "__main__":
    main() 