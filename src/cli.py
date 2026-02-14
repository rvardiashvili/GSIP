#!/usr/bin/env python3
import sys
import os

# Ensure project root is in path so 'src' can be imported
current_file = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(current_file))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def main():
    if len(sys.argv) < 2:
        print("Usage: gsip [infer|suite|studio|manage] ...")
        print("\nCommands:")
        print("  infer   Run the main inference pipeline")
        print("  suite   Run batch execution suite")
        print("  studio  Launch the GSIP Studio GUI")
        print("  manage  Manage adapters, reporters, and configs")
        sys.exit(1)

    command = sys.argv[1]
    
    # Remove the subcommand from sys.argv so the tools receive their expected arguments
    # e.g., ['gsip', 'infer', 'foo=bar'] -> ['gsip', 'foo=bar']
    sys.argv = [sys.argv[0]] + sys.argv[2:]

    if command == 'infer':
        # Lazy import to avoid loading heavy libraries until needed
        from src.main import main as run_inference
        run_inference()
        
    elif command == 'suite':
        from src.run_suite import main as run_suite
        run_suite()
        
    elif command == 'studio':
        # Ensure project root is in path for studio imports
        current_file = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(current_file))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
            
        from gtk_client.main import main as run_studio
        run_studio()
        
    elif command == 'manage':
        from src.manage import main as run_manage
        run_manage()
        
    else:
        print(f"❌ Unknown command: '{command}'")
        print("Available commands: infer, suite, studio, manage")
        sys.exit(1)

if __name__ == "__main__":
    main()

