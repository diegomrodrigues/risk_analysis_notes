import os
import PyPDF2
from pathlib import Path

def split_pdf_by_sections(pdf_path, sections_dict, output_folder=".", skip_pages=0):
    """
    Split a PDF into multiple PDFs based on section definitions
    
    Args:
        pdf_path (str): Path to the PDF file
        sections_dict (dict): Dictionary with section names as keys and (start_page, end_page) tuples as values
        output_folder (str): Directory where section folders will be created (default: current directory)
        skip_pages (int): Number of initial pages to skip (for TOC, etc.) (default: 0)
    """
    # Get the PDF filename without extension
    pdf_filename = Path(pdf_path).stem
    
    # Create output folder if it doesn't exist
    os.makedirs(output_folder, exist_ok=True)
    
    # Open the original PDF
    with open(pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        
        # Sort sections by start page to assign numbers in order
        sorted_sections = sorted(sections_dict.items(), key=lambda x: x[1][0])
        
        for i, (section_name, (start_page, end_page)) in enumerate(sorted_sections, 1):
            # Create folder with format: "01. section a/"
            folder_name = f"{i:02d}. {section_name}"
            folder_path = os.path.join(output_folder, folder_name)
            os.makedirs(folder_path, exist_ok=True)
            
            # Create a new PDF writer
            pdf_writer = PyPDF2.PdfWriter()
            
            # Extract pages (PyPDF2 is 0-indexed, but user input is 1-indexed)
            # Also adjust for skipped pages
            for page_num in range(start_page - 1 + skip_pages, end_page + skip_pages):
                if page_num < len(pdf_reader.pages):
                    pdf_writer.add_page(pdf_reader.pages[page_num])
                    
            # Create output file path
            output_filename = f"{pdf_filename}_{start_page}-{end_page}.pdf"
            output_path = os.path.join(folder_path, output_filename)
            
            # Write the extracted pages to a new PDF
            with open(output_path, 'wb') as output_file:
                pdf_writer.write(output_file)
                
            print(f"Created: {output_path}")

if __name__ == "__main__":
    output_folder = "04. Stochastic Search"

    sections = {
        "Stochastic Search and Optimization": (1, 33),
        "Direct Methods for Stochastic Search": (34, 64),
        "Recursive Estimation for Linear Models": (65, 94),
        "Stochastic Approximation for Nonlinear Root-Finding": (95, 125),
        "Stochastic Gradient Form of Stochastic Approximation": (126, 149),
        "Stochastic Approximation and the Finite-Difference Method": (150, 175),
        "Simultaneous Perturbation Stochastic Approximation": (176, 207),
        "Annealing-Type Algorithms": (208, 230),
        "Evolutionary Computation I": (231, 258),
        "Evolutionary Computation II": (259, 277),
        "Reinforcement Learning via Temporal Differences": (278, 299),
        "Statistical Methods for Optimization in Discrete Problems": (300, 328),
        "Model Selection and Statistical Information": (329, 366),
        "Simulation-Based Optimization I": (367, 408),
        "Simulation-Based Optimization II": (409, 435),
        "Markov Chain Monte Carlo": (436, 463),
        "Optimal Design for Experimental Inputs": (464, 502)
    }

    # Replace with your PDF path
    pdf_path = "Stochastic Search.pdf"
    
    # Example with output folder and skipping 5 pages of TOC
    split_pdf_by_sections(
        pdf_path, 
        sections, 
        output_folder=output_folder, 
        skip_pages=18
    )