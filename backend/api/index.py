import sys
import os

# Put root backend folder in python path for module loading
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
