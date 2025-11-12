from streamlit.web import cli as stcli
import sys
import os

# get path of current file
path = os.path.dirname(os.path.abspath(__file__))

if __name__ == '__main__':
    sys.argv = ["streamlit", "run", os.path.join(path, "main.py")]
    sys.exit(stcli.main())