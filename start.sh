python -m venv myenv  # Create a virtual environment (if not already created)
source myenv/bin/activate  # Activate the virtual environment
python -m ensurepip --upgrade  # Ensure pip is installed and upgrade it
pip install -r requirements.txt
python main.py
