from pathlib import Path
from typing import List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
from .processor import TaskProcessor
from .chain import TaskChain, ChainStep
from .filename_handler import FilenameHandler

class TopicProcessor:
    """Handles the processing of topics and sections."""
    
    def __init__(self, processor: TaskProcessor, tasks_config: dict, context: str):
        self.processor = processor
        self.tasks_config = tasks_config
        self.context = context
        self.filename_handler = FilenameHandler(processor, tasks_config)

    def process_section_topic(self, directory: Path, section_name: str, topic: str, 
                            pdf_files: List[Path], previous_topics: List[Tuple[str, str]] = None,
                            max_previous_topics: int = 3) -> Optional[Tuple[str, str]]:
        """Process a single topic within a section."""
        print(f"Processing topic: {topic[:50]}...")
        
        additional_context = self._build_previous_topics_context(previous_topics, max_previous_topics)
        chain = self._create_topic_chain(pdf_files, additional_context)
        
        try:
            input_text = self._build_input_text(directory, section_name, topic)
            final_content = chain.run(input_text)
            if final_content:
                return topic, final_content
        except Exception as e:
            print(f"❌ Error processing topic {topic}: {str(e)}")
            raise e
        
        return None

    def process_section(self, directory: Path, section_name: str, section_topics: List[str],
                       pdf_files: List[Path], max_previous_topics: int = 5) -> None:
        """Process all topics within a section sequentially."""
        print(f"\nProcessing section: {section_name} with {len(section_topics)} topics...")
        
        previous_topics = []
        
        for topic in section_topics:
            try:
                result = self.process_section_topic(
                    directory, section_name, topic, pdf_files,
                    previous_topics, max_previous_topics
                )
                
                if result:
                    topic, content = result
                    success = self._save_topic(directory, section_name, topic, content)
                    if success:
                        previous_topics.append((topic, content))
            except Exception as e:
                print(f"❌ Error processing topic {topic}: {str(e)}")

    def _build_previous_topics_context(self, previous_topics: List[Tuple[str, str]], 
                                     max_previous_topics: int) -> str:
        """Build context string from previous topics."""
        if not previous_topics:
            return ""
            
        context = "\n\nPrevious Topics:\n"
        for prev_topic, prev_content in previous_topics[-max_previous_topics:]:
            context += f"--- START {prev_topic} ---\n{prev_content}\n"
            context += f"--- END {prev_topic} ---\n"
        return context

    def _create_topic_chain(self, pdf_files: List[Path], additional_context: str) -> TaskChain:
        """Create the chain for topic processing."""
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
                    "format_math_task",
                    "translate_english_task",
                    "cleanup_task"
                ],
                stop_at="# Conclusão",
                max_iterations=3
            )
        ]
        
        return TaskChain(self.processor, self.tasks_config, steps)

    def _build_input_text(self, directory: Path, section_name: str, topic: str) -> str:
        """Build the input text for the chain."""
        return (
            f"CONTEXT_PLACEHOLDER = {self.context} e {directory} \n"
            f"TOPIC_PLACEHOLDER = {section_name} \n"
            f"SUBTOPIC_PLACEHOLDER = {topic}"
        )

    def _save_topic(self, directory: Path, section_name: str, topic: str, content: str) -> bool:
        """Save the processed topic to a file."""
        try:
            section_dir = self.filename_handler.create_section_directory(directory, section_name)
            result = self.filename_handler.generate_filename(section_dir, topic)
            
            if result.exists:
                print(f"⚠️ Similar topic already exists: {result.filename}")
                return True
            
            result.path.write_text(content, encoding='utf-8')
            print(f"✔️ Saved topic to: {result.filename}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to process topic: {str(e)}")
            return False 