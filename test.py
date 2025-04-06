import os
import re
from dotenv import load_dotenv

load_dotenv()

from pollo.agents.draft.writer import generate_drafts_from_topics

# Define the base directory where topic folders are located
base_dir = "."  # Change this to your actual base directory path

# Define directories to exclude from processing
EXCLUDE_DIRS = [
    "01. Value at Risk Models",
    "02. Forecasting Risk and Correlations",
    "08. Exceedance Probability Forecasting"
]

# Get all directories in the base directory
all_dirs = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]

# Filter directories matching the pattern "[0-9+]. [Topic Name]"
topic_dirs = [d for d in all_dirs if re.match(r"^\d+\.\s+.+$", d)]

# Exclude directories that are in the EXCLUDE_DIRS list
topic_dirs = [d for d in topic_dirs if d not in EXCLUDE_DIRS]

# Define the perspectives for all topics
basic_perspective = "Foque nos conceitos fundamentais de análise de risco, incluindo modelos de Valor em Risco (VaR), métodos de previsão, risco de liquidez e simulações de Monte Carlo. Explique como os riscos são quantificados, a diferença entre abordagens paramétricas e não-paramétricas, e como interpretar resultados de VaR, backtesting e mapeamento de risco em contextos práticos de gestão de portfólio."
advanced_perspective = "Foque na teoria matemática e estatística de análise de risco avançada, incluindo modelos multivariados, testes de estresse, correlações de risco e o modelo StoneX. Cubra métodos computacionais para VaR, teoria de cópulas, modelagem de eventos extremos e técnicas de simulação para quantificação de risco em carteiras complexas e cenários de mercado adversos."

# Process each topic directory
for directory in topic_dirs:
    print(f"Processing directory: {directory}")
    generate_drafts_from_topics(
        directory=directory,
        perspectives=[
            basic_perspective,
            advanced_perspective
        ],
        json_per_perspective=2,
        branching_factor=1
    )
    
print(f"Processed {len(topic_dirs)} topic directories")