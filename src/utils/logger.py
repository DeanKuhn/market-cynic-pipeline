import logging
import os
from datetime import datetime

def setup_logger(name):
    # Create logs directory if it doesn't exist
    if not os.path.exists("logs"):
        os.makedirs("logs")

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # 1. Create a File Handler
    log_filename = f"logs/pipeline_{datetime.now().strftime("%Y-%m-%d")}.log"
    file_handler = logging.FileHandler(log_filename)

    # 2. Create a Console Handler
    console_handler = logging.StreamHandler()

    # 3. Define the Format (Timestamp - Name - Level - Message)
    formatter = \
    logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add handler to the logger
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger