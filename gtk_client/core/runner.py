import os
import subprocess
import threading
import re
import signal
from gi.repository import GLib

class PipelineRunner:
    def __init__(self, command, cwd=None, env=None, on_output=None, on_progress=None, on_finish=None):
        self.command = command
        self.cwd = cwd or os.getcwd()
        self.env = env
        self.on_output = on_output
        self.on_progress = on_progress
        self.on_finish = on_finish
        self.process = None
        self.running = False

    def start(self):
        self.running = True
        thread = threading.Thread(target=self._run)
        thread.daemon = True
        thread.start()

    def stop(self):
        self.running = False
        if self.process:
            try:
                # Kill the entire process group to ensure children (e.g. hydra/python subprocs) die too
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            except ProcessLookupError:
                pass # Process already dead

    def _run(self):
        try:
            # Prepare Environment
            if self.env:
                run_env = self.env.copy()
            else:
                run_env = os.environ.copy()
            
            # Force unbuffered output for real-time updates
            run_env["PYTHONUNBUFFERED"] = "1"
            
            self.process = subprocess.Popen(
                self.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=self.cwd,
                env=run_env,
                preexec_fn=os.setsid # Create new process group
            )

            # Regex for tqdm progress parsing (e.g. "Inference: 50%|#####     |")
            progress_regex = re.compile(r'(\d+)%')

            for line in self.process.stdout:
                if not self.running:
                    break
                
                # Update Log View (in main thread)
                if self.on_output:
                    GLib.idle_add(self.on_output, line)

                # Parse Progress
                if self.on_progress and "%" in line:
                    match = progress_regex.search(line)
                    if match:
                        percent = int(match.group(1)) / 100.0
                        GLib.idle_add(self.on_progress, percent)

            self.process.wait()
            return_code = self.process.returncode
            
            if self.on_finish:
                GLib.idle_add(self.on_finish, return_code)

        except Exception as e:
            if self.on_output:
                GLib.idle_add(self.on_output, f"\nError starting process: {e}\n")
            if self.on_finish:
                GLib.idle_add(self.on_finish, -1)
