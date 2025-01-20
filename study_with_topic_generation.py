from pathlib import Path
import os
from agent.processor import TaskProcessor
from agent.directory_processor import DirectoryProcessor

CONTEXT = "Expert Financial Risk Analysis using Value at Risk Models"
PERSPECTIVES = [
    "Foque nos aspectos matemáticos e fórmulas, incluindo definições formais, teoremas, provas e demonstrações matemáticas.",
    "Foque nos conceitos financeiros e econômicos, incluindo aplicações práticas, interpretações e implicações para o mercado.",
    "Foque nos aspectos computacionais e algorítmicos, incluindo complexidade, implementação e otimização."
]

def main():
    # Load configuration and initialize processor
    tasks_config = load_tasks_config()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is required")
    
    processor = TaskProcessor(api_key=api_key)
    directory_processor = DirectoryProcessor(processor, tasks_config, CONTEXT)
    
    # Define base directory and settings
    base_dir = Path("/content/risk_analysis_notes/01. Value at Risk Models")
    target_folders = get_numbered_folders(base_dir)
    max_workers = 2
    
    # Process each target directory
    for folder in target_folders:
        directory = base_dir / folder
        if directory.exists():
            directory_processor.process_with_topics(
                directory,
                perspectives=PERSPECTIVES,
                num_topics=len(PERSPECTIVES),
                max_workers=max_workers
            )
        else:
            print(f"Directory not found: {directory}")

if __name__ == "__main__":
    main()