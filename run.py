import sys
from subprocess import check_call


def _running_inside_streamlit() -> bool:
    """Return True when this file is executed by `streamlit run`."""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        return get_script_run_ctx() is not None
    except Exception:
        return False


def main() -> None:
    print("Starting PetroBot Streamlit application...")
    check_call([sys.executable, "-m", "streamlit", "run", "app/main.py"])


if _running_inside_streamlit():
    # `streamlit run run.py` should render the app directly instead of
    # recursively spawning a second Streamlit process.
    # IMPORTANT: we must call main() explicitly — NOT use `from app.main import *`.
    # Python caches modules after first import, so module-level code in app.main
    # only runs once. On every Streamlit rerun run.py is re-executed but the
    # cached module's top-level statements don't re-run → blank screen on any
    # interaction. Calling main() explicitly re-executes the rendering each time.
    from app.main import main
    main()
elif __name__ == "__main__":
    # `python run.py` remains supported for convenience.
    main()
