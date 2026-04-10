import subprocess
from datetime import datetime

def get_git_info():
    try:
        # Get short hash
        sha = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()
        # Get commit date
        commit_date = subprocess.check_output(['git', 'log', '-1', '--format=%cd', '--date=format:%Y-%m-%d %H:%M']).decode('ascii').strip()
        return f"Build: {sha} | {commit_date}"
    except:
        # Fallback if git is not available
        return f"Last Refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M')}"

