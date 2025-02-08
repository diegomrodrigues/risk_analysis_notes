from pathlib import Path
import os
import yaml
from agent.processor import TaskProcessor
from agent.image_processor import ImageProcessor
import argparse
from dotenv import load_dotenv

# Base directory for processing
BASE_DIR = "./"

# Configuration for directory filtering
TARGET_FOLDERS = [
    "04. Monte Carlo Methods"
]
EXCLUDED_FOLDERS = [
]

def load_tasks_config(tasks_dir: str = './agent/tasks') -> dict:
    """Load all YAML files from the tasks directory into a single config dictionary."""
    tasks_config = {}
    tasks_path = Path(tasks_dir)
    
    for yaml_file in tasks_path.glob('*.yaml'):
        with open(yaml_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            tasks_config.update(config)
    
    return tasks_config

def get_numbered_folders(base_dir: Path) -> list[str]:
    """
    Get all numbered folders from the base directory, excluding specified folders.
    If TARGET_FOLDERS is specified, only return those folders.
    Returns folders sorted numerically.
    """
    if TARGET_FOLDERS:
        return sorted([folder for folder in TARGET_FOLDERS if folder not in EXCLUDED_FOLDERS])
    
    folders = [
        folder.name for folder in base_dir.iterdir()
        if folder.is_dir() 
        and folder.name.strip()[0].isdigit()
        and folder.name not in EXCLUDED_FOLDERS
    ]
    return sorted(folders)

def main():
    # Load environment variables from .env file
    load_dotenv()
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Process images and generate metadata')
    parser.add_argument('--debug', type=lambda x: x.lower() == 'true', default=False,
                       help='Enable debug mode (true/false)')
    parser.add_argument('--base-dir', type=str, default=BASE_DIR,
                       help='Base directory to process')
    args = parser.parse_args()
    
    # Load configuration and initialize processor
    tasks_config = load_tasks_config()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is required")
    
    # Initialize processors
    processor = TaskProcessor(api_key=api_key)
    image_processor = ImageProcessor(
        processor=processor,
        tasks_config=tasks_config,
        debug=args.debug
    )
    
    # Define base directory and get target folders
    base_dir = Path(args.base_dir)
    if not base_dir.exists():
        raise ValueError(f"Base directory not found: {base_dir}")
    
    target_folders = get_numbered_folders(base_dir)
    print(f"\n📂 Found {len(target_folders)} target folders to process")
    
    # Process each target directory
    for folder in target_folders:
        directory = base_dir / folder
        if directory.exists():
            print(f"\n🔍 Processing directory: {folder}")
            try:
                image_processor.process_directory_tree(
                    base_dir=directory,
                    excluded_dirs=EXCLUDED_FOLDERS
                )
            except Exception as e:
                print(f"❌ Error processing directory {folder}: {str(e)}")
        else:
            print(f"⚠️ Directory not found: {directory}")
    
    print("\n✨ Image processing completed")

if __name__ == "__main__":
    main() 