import sys
import logging
logging.basicConfig(stream=sys.stderr)
sys.path.insert(0, "/app")

from app import app
application = app
