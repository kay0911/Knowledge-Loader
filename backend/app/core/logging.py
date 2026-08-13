import logging
import sys
import io

# Ensure sys.stdout handles UTF-8 on Windows
if hasattr(sys.stdout, 'buffer'):
    stream = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
else:
    stream = sys.stdout

# Configure logging format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(stream)
    ]
)

logger = logging.getLogger("graphrag_knowledge_loader")
