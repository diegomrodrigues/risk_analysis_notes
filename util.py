import os
from pathlib import Path

# Define the logical order of linear algebra topics
topic_order = [
    "Vector Spaces",
    "Matrices",
    "Determinants",
    "Vector Norm and Matrix Norms",
    "Euclidean Spaces",
    "Dual Space",
    "Eigenvectors & Eigenvalues",
    "Computing Eigenvalues",
    "Gaussian Elimination",
    "Solving Linear Systems",
    "QR Decomposition",
    "SVD & Polar Form",
    "Spectral Theorems",
    "Hermitian Spaces",
    "Hadamard Matrices",
    "Unit Quaternions and Rotations",
    "Direct Sums",
    "Applications"
]

def rename_pdf_in_folder(folder_path):
    """Rename PDF files in the given folder by prepending 'Ref -'"""
    for file in folder_path.glob('*.pdf'):
        if not file.name.startswith('Ref -'):
            new_name = f"Ref - {file.name}"
            try:
                file.rename(folder_path / new_name)
                print(f"Renamed PDF: {file.name} -> {new_name}")
            except Exception as e:
                print(f"Error renaming PDF {file.name}: {e}")

def rename_folders():
    workspace_path = Path.cwd()
    
    for idx, topic in enumerate(topic_order, 1):
        old_path = workspace_path / topic
        new_name = f"{idx:02d}. {topic}"
        new_path = workspace_path / new_name
        
        if new_path.exists():
            try:
                # First rename any PDFs in the current folder
                rename_pdf_in_folder(new_path)
                # Then rename the folder itself
                #old_path.rename(new_path)
                print(f"Renamed folder: {topic} -> {new_name}")
            except Exception as e:
                print(f"Error renaming {topic}: {e}")

if __name__ == "__main__":
    rename_folders()
