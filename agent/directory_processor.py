from pathlib import Path
from typing import List, Optional
import json
from concurrent.futures import ThreadPoolExecutor
from .processor import TaskProcessor
from .topic_generator import TopicGenerator
from .topic_processor import TopicProcessor

class DirectoryProcessor:
    """Handles the processing of directories and their contents."""
    
    def __init__(self, processor: TaskProcessor, tasks_config: dict, context: str):
        self.processor = processor
        self.tasks_config = tasks_config
        self.topic_generator = TopicGenerator(processor, tasks_config)
        self.topic_processor = TopicProcessor(processor, tasks_config, context)

    def process_with_topics(self, directory: Path, perspectives: List[str], 
                          num_topics: Optional[int] = None, max_workers: int = 3) -> None:
        """Generate topics and process them for a directory."""
        try:
            # First, generate topics if they don't exist
            topics_file = directory / "topics.json"
            if not topics_file.exists():
                self.topic_generator.generate(directory, perspectives, num_topics)
            
            # Then process the topics
            self.process_directory(directory, max_workers)
            
        except Exception as e:
            print(f"❌ Failed to process directory: {directory}")
            print(f"Error: {str(e)}")
            raise

    def process_directory(self, directory: Path, max_workers: int = 3) -> None:
        """Process a single directory with its sections using parallel processing."""
        print(f"\nProcessing directory: {directory}")
        
        pdf_files = list(directory.glob("*.pdf"))
        if not pdf_files:
            print("No PDF files found in the directory, skipping...")
            return

        try:
            topics_data = self._read_topics_file(directory)
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                for topic_obj in topics_data["topics"]:
                    section_name = topic_obj["topic"]
                    section_topics = topic_obj["sub_topics"]
                    
                    future = executor.submit(
                        self.topic_processor.process_section,
                        directory,
                        section_name,
                        section_topics,
                        pdf_files,
                        5  # max_previous_topics
                    )
                    futures.append(future)

                for future in futures:
                    future.result()

        except Exception as e:
            print(f"❌ Failed to process directory: {directory}")
            print(f"Error: {str(e)}")
            raise

    def _read_topics_file(self, directory: Path) -> dict:
        """Read and parse the topics.json file."""
        topics_file = directory / "topics.json"
        if topics_file.exists():
            content = topics_file.read_text(encoding='utf-8')
            return json.loads(content)
        raise FileNotFoundError("topics.json not found in the specified directory") 