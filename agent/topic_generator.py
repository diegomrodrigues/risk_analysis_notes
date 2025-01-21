from pathlib import Path
from typing import List, Optional
from .chain import TaskChain, ChainStep
from .processor import TaskProcessor
import json
import re

class TopicGenerator:
    """Generates and manages topic hierarchies from PDF documents."""
    
    def __init__(self, processor: TaskProcessor, tasks_config: dict):
        self.processor = processor
        self.tasks_config = tasks_config

    def generate(self, directory: Path, perspectives: Optional[List[str]] = None, 
                num_topics: Optional[int] = None) -> str:
        """Generate a topics.json file from PDF documents in the directory."""
        self._validate_input(perspectives, num_topics)
        pdf_files = self._get_pdf_files(directory)
        
        # Generate topics from different perspectives
        num_perspectives = len(perspectives) if perspectives else num_topics
        perspective_results = self._generate_perspective_topics(pdf_files, perspectives, num_perspectives)
        
        # Merge and restructure topics
        merged_result = self._merge_final_topics(perspective_results)
        restructured_result = self._restructure_topics(directory, merged_result)
        
        self._save_topics(directory, restructured_result)
        return restructured_result

    def _validate_input(self, perspectives: Optional[List[str]], num_topics: Optional[int]):
        """Validate input parameters."""
        if perspectives is None and num_topics is None:
            raise ValueError("You should provide either perspectives or num_topics")

    def _get_pdf_files(self, directory: Path) -> List[Path]:
        """Get all PDF files in the directory."""
        return list(directory.glob("*.pdf"))

    def _generate_perspective_topics(self, pdf_files: List[Path], 
                                   perspectives: List[str], num_topics: int) -> List[str]:
        """Generate topics for each perspective."""
        perspective_results = []
        
        for i, perspective in enumerate(perspectives):
            print(f"\nGenerating topics for perspective {i+1}/{num_topics}")
            perspective_jsons = self._generate_perspective_set(pdf_files, perspective, i)
            merged_perspective = self._merge_perspective_set(perspective_jsons, i)
            perspective_results.append(merged_perspective)
            
        return perspective_results

    def _generate_perspective_set(self, pdf_files: List[Path], 
                                perspective: str, perspective_index: int) -> List[str]:
        """Generate multiple sets of topics for a single perspective."""
        perspective_jsons = []
        
        for j in range(3):  # Generate 3 JSONs per perspective
            topics_chain = TaskChain(self.processor, self.tasks_config, [
                ChainStep(
                    name=f"Generate Topics Set {j+1} for Perspective {perspective_index+1}",
                    tasks=["create_topics"],
                    input_files=pdf_files,
                    expect_json=True,
                    max_iterations=3
                )
            ])
            
            result = topics_chain.run(perspective)
            if not result:
                raise Exception(f"Failed to generate topics set {j+1} for perspective {perspective_index+1}")
            perspective_jsons.append(result)
            
        return perspective_jsons

    def _merge_perspective_set(self, perspective_jsons: List[str], perspective_index: int) -> str:
        """Merge multiple topic sets for a single perspective by combining their content."""
        # Parse all JSONs
        parsed_jsons = [json.loads(json_str) for json_str in perspective_jsons]
        
        # Merge the topics using the helper method
        merged_result = self._merge_topic_contents(parsed_jsons)
        
        # Ensure proper encoding of special characters
        return json.dumps(merged_result, indent=2, ensure_ascii=False)

    def _merge_final_topics(self, perspective_results: List[str]) -> str:
        """Merge all perspective results by combining their content."""
        # Parse all JSONs
        parsed_jsons = [json.loads(result) for result in perspective_results]
        
        # Merge the topics using the helper method
        merged_result = self._merge_topic_contents(parsed_jsons)
        
        # Ensure proper encoding of special characters
        return json.dumps(merged_result, indent=2, ensure_ascii=False)

    def _merge_topic_contents(self, json_list: List[dict]) -> dict:
        """Merge multiple topic JSONs by combining topics and their sub-topics."""
        topic_map = {}
        
        # Process each JSON document
        for json_doc in json_list:
            for topic_item in json_doc.get('topics', []):
                topic = topic_item['topic']
                sub_topics = set(topic_item.get('sub_topics', []))
                
                if topic in topic_map:
                    # Merge sub-topics for existing topic
                    topic_map[topic].update(sub_topics)
                else:
                    # Create new topic entry
                    topic_map[topic] = sub_topics
        
        # Convert back to the required format
        merged_result = {
            "topics": [
                {
                    "topic": topic,
                    "sub_topics": sorted(list(sub_topics))
                }
                for topic, sub_topics in topic_map.items()
            ]
        }
        
        return merged_result

    def _restructure_topics(self, directory: Path, merged_result: str) -> str:
        """Restructure and consolidate topics based on existing directory structure."""
        existing_dirs = self._get_existing_directories(directory)
        existing_dirs_context = json.dumps({"existing_directories": existing_dirs})
        
        restructure_chain = self._create_restructure_chain(existing_dirs_context)
        result = restructure_chain.run(merged_result)
        
        if not result:
            raise Exception("Failed to restructure and consolidate topics")
        return result

    def _get_existing_directories(self, directory: Path) -> List[str]:
        """Get existing directory names without numbering."""
        return [
            re.sub(r'^\d+\.\s*', '', d.name)
            for d in directory.iterdir() 
            if d.is_dir()
        ]

    def _create_restructure_chain(self, context: str) -> TaskChain:
        """Create chain for restructuring topics."""
        return TaskChain(self.processor, self.tasks_config, [
            ChainStep(
                name="Restructure Topics",
                tasks=["restructure_topics"],
                expect_json=True,
                max_iterations=5,
                additional_context=context
            ),
            ChainStep(
                name="Consolidate Subtopics",
                tasks=["consolidate_subtopics"],
                expect_json=True,
                max_iterations=3,
                use_previous_result=True
            )
        ])

    def _save_topics(self, directory: Path, content: str) -> None:
        """Save the generated topics to a file."""
        output_file = directory / "topics.json"
        output_file.write_text(content, encoding='utf-8')
        print(f"✔️ Topics generated and saved to: {output_file}") 