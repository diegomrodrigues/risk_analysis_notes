from pathlib import Path
from typing import List, Dict, Optional
import json
from .processor import TaskProcessor
from .chain import TaskChain, ChainStep
from .utils import retry_on_error

class ImageProcessor:
    """Processes images within directories and generates descriptive metadata."""
    
    def __init__(self, processor: TaskProcessor, tasks_config: dict, debug: bool = False):
        self.processor = processor
        self.tasks_config = tasks_config
        self.debug = debug

    @retry_on_error(max_retries=3)
    def process_directory_tree(self, base_dir: Path, excluded_dirs: List[str] = ['exclude_dir']) -> None:
        """Process all valid directories in the base directory."""
        print(f"\n🔍 Searching for target directories in: {base_dir}")
        
        for directory in self._find_target_directories(base_dir, excluded_dirs):
            if self.debug:
                print(f"\n⚙️ Processing directory: {directory}")
            
            pdf_files = list(directory.glob("*.pdf"))
            if not pdf_files:
                if self.debug:
                    print("  - No PDF files found, skipping directory")
                continue
                
            self._process_directory_images(directory, pdf_files[0])

    def _find_target_directories(self, base_dir: Path, excluded_dirs: List[str]) -> List[Path]:
        """Find directories containing an 'images' folder, excluding specified patterns."""
        target_dirs = []
        
        for path in base_dir.rglob("images"):
            if any(excluded in path.parent.parts for excluded in excluded_dirs):
                continue
                
            target_dirs.append(path.parent)
            
        return target_dirs

    def _process_directory_images(self, directory: Path, pdf_file: Path) -> None:
        """Process all images in a directory's images folder."""
        images_dir = directory / "images"
        if not images_dir.exists():
            if self.debug:
                print("  - No images directory found")
            return

        image_entries = []
        figure_counter = 1  # Track figure numbers per directory
        
        for image_file in images_dir.iterdir():
            if image_file.suffix.lower() in ['.png', '.jpg', '.jpeg']:
                if self.debug:
                    print(f"  - Processing image: {image_file.name}")
                
                result = self._process_single_image(image_file, pdf_file)
                if result:
                    # Generate sequential filename
                    new_filename = f"figure{figure_counter}{image_file.suffix}"
                    new_path = image_file.parent / new_filename
                    
                    try:
                        image_file.rename(new_path)
                        if self.debug:
                            print(f"  - Renamed to: {new_filename}")
                        
                        image_entries.append({
                            'path': str(new_path.relative_to(directory)),
                            'description': result.get('description', ''),
                            'filename': new_filename
                        })
                        figure_counter += 1  # Increment counter after successful processing
                        
                    except Exception as e:
                        print(f"❌ Failed to rename {image_file.name}: {str(e)}")

        if image_entries:
            self._generate_json_summary(directory, image_entries)

    def _process_single_image(self, image_file: Path, pdf_file: Path) -> Optional[Dict]:
        """Process a single image with its associated PDF."""
        chain = TaskChain(self.processor, self.tasks_config, [
            ChainStep(
                name="Process Image Metadata",
                tasks=["process_image_task"],
                input_files=[image_file, pdf_file],
                expect_json=True,
                extract_json=False
            )
        ], debug=self.debug)

        try:
            result = chain.run("Extract image metadata")
            return json.loads(result) if result else None
        except Exception as e:
            print(f"❌ Failed to process image {image_file.name}: {str(e)}")
            return None

    def _generate_json_summary(self, directory: Path, entries: List[Dict]) -> None:
        """Generate images.json summary file and markdown documentation."""
        # Generate JSON
        json_data = {
            "images": [
                {
                    "filename": entry['filename'],
                    "path": entry['path'],
                    "description": entry['description'],
                    "legenda": entry.get('legenda', '')  # Add legenda field
                } for entry in entries
            ]
        }
        
        # Write JSON file
        output_file = directory / "images.json"
        output_file.write_text(json.dumps(json_data, indent=2), encoding='utf-8')
        print(f"✔️ Generated image catalog at: {output_file}")
        
        # Generate Markdown
        markdown_content = []
        for entry in entries:
            figure_name = entry['filename'].split('.')[0].capitalize()
            markdown_content.extend([
                f"## {figure_name}",
                "",
                f"![{entry.get('legenda', figure_name)}](./images/{entry['filename']})",
                "",
                entry['description'],
                ""
            ])
        
        # Write Markdown file
        markdown_file = directory / "images.md"
        markdown_file.write_text('\n'.join(markdown_content), encoding='utf-8')
        print(f"✔️ Generated markdown documentation at: {markdown_file}") 