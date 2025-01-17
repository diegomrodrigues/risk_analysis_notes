import yaml
import os
from pathlib import Path
from agent.processor import TaskProcessor
from agent.chain import TaskChain, ChainStep

EXCLUDED_FOLDERS = [
]

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

def process_directory(directory: Path, processor: TaskProcessor, tasks_config: dict, perspectives: list[str] = None, num_topics: int = None) -> None:
    """Process a single directory to generate topics JSON and merge them.
    
    Args:
        directory: Directory path to process
        processor: TaskProcessor instance
        tasks_config: Tasks configuration dictionary
        perspectives: Optional list of perspectives to use for topic generation. If None, uses default perspectives
        num_topics: Optional number of topics to generate. If None, uses len(perspectives)
    """
    print(f"\nProcessing directory: {directory}")
    
    # Default perspectives if none provided
    if perspectives is None and num_topics is None:
        raise ValueError("You should provide either perspectives or num_topics to be generated.")

    if perspectives is not None:
        num_topics = len(perspectives)
    
    pdf_files = get_pdf_files(directory)
    if not pdf_files:
        print("No PDF files found in the directory, skipping...")
        return

    try:
        # Generate N separate topic JSONs
        all_topics_results = []
        for i in range(num_topics):
            print(f"\nGenerating topics set {i+1}/{num_topics} with perspective: {perspectives[i]}")
            topics_steps = [
                ChainStep(
                    name=f"Generate Topics Set {i+1}",
                    tasks=["create_topics"],
                    input_files=pdf_files,
                    expect_json=True,
                    max_iterations=3
                )
            ]
            
            topics_chain = TaskChain(processor, tasks_config, topics_steps)
            if perspectives is None:
                topics_result = topics_chain.run("")
            else:
                topics_result = topics_chain.run(perspectives[i])
            
            if not topics_result:
                raise Exception(f"Failed to generate topics set {i+1}")
                
            all_topics_results.append(topics_result)

        # Merge all topics
        merge_steps = [
            ChainStep(
                name="Merge Topics",
                tasks=["merge_topics"],
                expect_json=True,
                max_iterations=5
            )
        ]
        
        merge_chain = TaskChain(processor, tasks_config, merge_steps)
        merged_result = merge_chain.run("\n".join(all_topics_results))
        
        if not merged_result:
            raise Exception("Failed to merge topics")
            
        # Save merged topics to file
        output_file = directory / "topics.json"
        output_file.write_text(merged_result, encoding='utf-8')
        print(f"✔️ Merged topics saved to: {output_file}")

    except Exception as e:
        print(f"❌ Failed to process directory: {directory}")
        print(f"Error: {str(e)}")

def get_numbered_folders(base_dir: Path) -> list[str]:
    """
    Get all numbered folders from the base directory, excluding specified folders.
    Returns folders sorted numerically.
    """
    folders = [
        folder.name for folder in base_dir.iterdir()
        if folder.is_dir() 
        and folder.name.strip()[0].isdigit()
        and folder.name not in EXCLUDED_FOLDERS
    ]
    return sorted(folders)

def main():
    # Load tasks configuration
    tasks_config = load_tasks_config()
    
    # Initialize processor
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is required")
    processor = TaskProcessor(api_key=api_key)
    
    # Define base directory and target folders
    base_dir = Path("/content/risk_analysis_notes/01. Value at Risk Models")
    target_folders = [
    ]

    perspectives = [
        # Math
        "Foque nos aspectos matemáticos e fórmulas, incluindo definições formais, teoremas, provas e demonstrações matemáticas.",
        "Foque nos aspectos matemáticos e fórmulas, incluindo definições formais, teoremas, provas e demonstrações matemáticas.",

        # Finance
        "Foque nos conceitos financeiros e econômicos, incluindo aplicações práticas, interpretações e implicações para o mercado.",
        "Foque nos conceitos financeiros e econômicos, incluindo aplicações práticas, interpretações e implicações para o mercado.",

        # Computing
        "Foque nos aspectos computacionais e algorítmicos, incluindo complexidade, implementação e otimização.",
        "Foque nos aspectos computacionais e algorítmicos, incluindo complexidade, implementação e otimização."
    ]
    
    num_topics = len(perspectives) or 3

    # If no target folders specified, get all numbered folders
    if not target_folders:
        target_folders = get_numbered_folders(base_dir)
    
    # Process each target directory
    for folder in target_folders:
        directory = base_dir / folder
        if directory.exists():
            process_directory(directory, processor, tasks_config, perspectives, num_topics)  # Using default perspectives
        else:
            print(f"Directory not found: {directory}")

if __name__ == "__main__":
    main()