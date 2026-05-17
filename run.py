import sys
from subprocess import check_call

def main():
    print("Starting PetroBot Streamlit application...")
    check_call([sys.executable, "-m", "streamlit", "run", "app/main.py"])

if __name__ == "__main__":
    main()
