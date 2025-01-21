from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
from .processor import TaskProcessor, retry_on_error
from .chain import TaskChain, ChainStep
from .filename_handler import FilenameHandler

@dataclass
class TopicResult:
    """Represents the result of topic processing."""
    topic: str
    content: str
    success: bool = False

class TopicProcessor:
    """Handles the processing of topics and sections with improved organization and error handling."""
    
    def __init__(self, processor: TaskProcessor, tasks_config: dict, context: str):
        self.processor = processor
        self.tasks_config = tasks_config
        self.context = context
        self.filename_handler = FilenameHandler(processor, tasks_config)

    def process_section(self, directory: Path, section_name: str, section_topics: List[str],
                       pdf_files: List[Path], max_previous_topics: int = 5) -> None:
        """
        Process all topics within a section sequentially.
        
        Args:
            directory: Base directory for saving topics
            section_name: Name of the current section
            section_topics: List of topics to process
            pdf_files: List of PDF files to use as reference
            max_previous_topics: Maximum number of previous topics to use as context
        """
        print(f"\nProcessing section: {section_name} ({len(section_topics)} topics)")
        
        processed_topics: List[TopicResult] = []
        for topic in section_topics:
            result = self._process_single_topic(
                directory=directory,
                section_name=section_name,
                topic=topic,
                pdf_files=pdf_files,
                previous_topics=processed_topics,
                max_previous_topics=max_previous_topics
            )
            if result and result.success:
                processed_topics.append(result)

    @retry_on_error(max_retries=3)
    def _process_single_topic(self, directory: Path, section_name: str, topic: str,
                            pdf_files: List[Path], previous_topics: List[TopicResult],
                            max_previous_topics: int) -> Optional[TopicResult]:
        """Process a single topic and handle its result."""
        try:
            print(f"Processing topic: {topic[:50]}...")
            
            # Generate content for the topic
            content = self._generate_topic_content(
                directory=directory,
                section_name=section_name,
                topic=topic,
                pdf_files=pdf_files,
                previous_topics=previous_topics,
                max_previous_topics=max_previous_topics
            )
            
            if not content:
                return None

            # Save the generated content
            success = self._save_topic_content(directory, section_name, topic, content)
            return TopicResult(topic=topic, content=content, success=success)

        except Exception as e:
            print(f"❌ Error processing topic '{topic}': {str(e)}")
            return None

    def _generate_topic_content(self, directory: Path, section_name: str, topic: str,
                              pdf_files: List[Path], previous_topics: List[TopicResult],
                              max_previous_topics: int) -> Optional[str]:
        """Generate content for a topic using the processing chain."""
        context = self._build_previous_topics_context(previous_topics, max_previous_topics)
        chain = self._create_processing_chain(pdf_files, context)
        input_text = self._build_input_text(directory, section_name, topic)
        
        return chain.run(input_text)

    def _create_processing_chain(self, pdf_files: List[Path], context: str) -> TaskChain:
        """Create the processing chain with defined steps."""
        return TaskChain(self.processor, self.tasks_config, [
            self._create_draft_step(pdf_files, context),
            self._create_enhancement_step()
        ])

    def _create_draft_step(self, pdf_files: List[Path], context: str) -> ChainStep:
        """Create the initial draft generation step."""
        return ChainStep(
            name="Generate Initial Draft",
            tasks=["generate_draft_task"],
            input_files=pdf_files,
            stop_at="<!-- END -->",
            max_iterations=3,
            additional_context=context
        )

    def _create_enhancement_step(self) -> ChainStep:
        """Create the enhancement and review step."""
        return ChainStep(
            name="Review and Enhance",
            tasks=[
                "cleanup_task",
                "generate_logical_steps_task",
                "generate_logical_steps_task",
                "generate_logical_steps_task",
                "generate_step_proofs_task",
                "generate_examples_task",
                "format_math_task",
                "cleanup_task"
            ],
            stop_at="<!-- END -->",
            max_iterations=3
        )

    def _build_previous_topics_context(self, previous_topics: List[TopicResult], 
                                     max_previous_topics: int) -> str:
        """Build context string from previous topics."""
        if not previous_topics:
            return ""
            
        context_parts = ["\n\nPrevious Topics:"]
        for topic_result in previous_topics[-max_previous_topics:]:
            context_parts.extend([
                f"--- START {topic_result.topic} ---",
                topic_result.content,
                f"--- END {topic_result.topic} ---"
            ])
        
        return "\n".join(context_parts)

    def _build_input_text(self, directory: Path, section_name: str, topic: str) -> str:
        """Build the input text for the processing chain."""
        return "\n".join(
            f"CONTEXT_PLACEHOLDER = {self.context} e {directory}"
            f"TOPIC_PLACEHOLDER = {section_name}"
            f"SUBTOPIC_PLACEHOLDER = {topic}"
        )

    def _save_topic_content(self, directory: Path, section_name: str, 
                          topic: str, content: str) -> bool:
        """Save the processed topic content to a file."""
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
            print(f"❌ Failed to save topic: {str(e)}")
            return False 