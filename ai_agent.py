import os  # Provides a way to access environment variables and file paths
import re  # Regular expressions for pattern matching and text cleaning
import argparse  # For parsing command-line arguments
import subprocess  # Used to execute shell commands
import platform  # Detects the operating system
import google.generativeai as genai  # Gemini API (Google Generative AI) client
from dotenv import load_dotenv  # Loads environment variables from a .env file
from typing import List  # For type hinting

# Load environment variables from a .env file into the environment
load_dotenv()

class AIAgent:
    def __init__(self):
        self.conversation = []  # Stores conversation history with the AI
        self.blocked_commands = ['rm', 'shutdown', 'reboot', ':(){', 'mkfs', 'dd if=', '>:']  # Dangerous commands to block
        self._initialize_ai()  # Initialize AI model and setup system prompt

    def _initialize_ai(self):
        """Set up initial system prompt and API key"""
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))  # Configure Gemini API key
        self.model = genai.GenerativeModel('gemini-1.5-flash')  # Load Gemini model

        # System prompt that enforces strict shell command-only output from AI
        system_prompt = """... 
            Generate ONLY valid shell commands without ANY:
            - Explanatory text
            - Code blocks
            - Numbered lists
            - Header text
            - Markdown formatting
            - Should not be in multiple lines(only single line)
        Format response as ONE COMMAND PER LINE with NO ADDITIONAL TEXT"""
        
        self.conversation = [system_prompt]  # Start conversation history with system prompt

    def _sanitize_commands(self, commands: List[str]) -> List[str]:
        """Validate and filter potentially dangerous commands"""
        safe_commands = []
        for cmd in commands:
            clean_cmd = re.sub(r'#.*$', '', cmd).strip()  # Remove trailing comments and whitespace
            
            if not clean_cmd:
                continue
                
            # Block commands that match any of the dangerous patterns
            if any(bc in clean_cmd for bc in self.blocked_commands):
                print(f"\033[91mBLOCKED: {clean_cmd}\033[0m")
                continue
                
            safe_commands.append(clean_cmd)  # Add safe command
            
        return safe_commands

    def _get_ai_commands(self, task: str) -> List[str]:
        """Get commands from Gemini API with improved parsing"""
        self.conversation.append(f"User task: {task}")  # Add task to conversation history
        
        try:
            # Generate response using last 5 messages of the conversation
            response = self.model.generate_content("\n".join(self.conversation[-5:]))  
            ai_response = response.text  # Get raw text response from Gemini
            
            commands = []
            for line in ai_response.split('\n'):
                line = re.sub(r'^[^a-zA-Z0-9]*', '', line)  # Strip leading special characters
                if line and not line.startswith(('#', '//', '/*')):  # Ignore comments
                    commands.append(line.strip())  # Add cleaned line as a command
                    
            self.conversation.append(f"Generated commands:\n{ai_response}")  # Save response to history
            # print(commands)  # Debug print for generated commands
            return self._sanitize_commands(commands)  # Filter out unsafe commands
            
        except Exception as e:
            print(f"\033[91mAI Error: {str(e)}\033[0m")
            return []

    def _execute_commands(self, commands: List[str]):
        """Safer command execution with timeouts and validation"""
        if not commands:
            print("\033[93mNo valid commands to execute\033[0m")
            return

        for cmd in commands:
            try:
                print(f"\n\033[94mEXECUTING: {cmd}\033[0m")
                
                # Use bash on non-Windows systems
                shell = '/bin/bash' if platform.system() != 'Windows' else None
                
                # Execute the command with a timeout
                result = subprocess.run(
                    cmd, 
                    shell=True,
                    executable=shell,
                    check=False,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=300
                )

                # Handle different outputs and errors
                if result.returncode != 0:
                    print(f"\033[91mFAILED (code {result.returncode}): {cmd}\033[0m")
                if result.stdout:
                    print(f"\033[92mOUTPUT:\n{result.stdout}\033[0m")
                if result.stderr:
                    print(f"\033[91mERROR:\n{result.stderr}\033[0m")

            except subprocess.TimeoutExpired:
                print(f"\033[91mTIMEOUT: Command took too long - {cmd}\033[0m")
            except Exception as e:
                print(f"\033[91mCRITICAL ERROR: {str(e)}\033[0m")

    def _validate_environment(self):
        """Check for required dependencies"""
        required = ['git', 'python3']
        missing = []
        
        for tool in required:
            try:
                # Try to run `tool --version` to check if installed
                subprocess.run([tool, '--version'], 
                             check=True, 
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            except:
                missing.append(tool)
                
        if missing:
            print(f"\033[93mWARNING: Missing dependencies - {', '.join(missing)}\033[0m")

    def run(self, initial_task: str):
        """Enhanced execution loop with validation"""
        self._validate_environment()  # Check for required software
        task = initial_task
        attempt = 1

        while attempt <= 3:  # Try max 3 times
            print(f"\n\033[1mATTEMPT {attempt}\033[0m")
            commands = self._get_ai_commands(task)  # Get AI-generated shell commands
            
            if not commands:
                print("\033[93mNo commands generated. Refining task...\033[0m")
                attempt += 1
                continue

            print("\n\033[1mGENERATED PLAN:\033[0m")
            for i, cmd in enumerate(commands, 1):
                print(f"{i}. {cmd}")

            # Ask user for approval before executing
            approval = input("\nApprove execution? [Y/N/R] (Yes/No/Redo): ").lower()

            if approval == 'y':
                self._execute_commands(commands)  # Execute shell commands
                
                success = input("\nDid this solve the task? [Y/N] ").lower()
                if success == 'y':
                    print("\n\033[1;92mTASK COMPLETED SUCCESSFULLY!\033[0m")
                    return
                else:
                    feedback = input("What went wrong? Describe the issue: ")
                    task = f"Previous failure: {feedback}. Original task: {initial_task}"
                    attempt += 1
            elif approval == 'r':
                continue  # Retry with same attempt number
            else:
                print("\n\033[91mExecution canceled\033[0m")
                return

        print("\n\033[91mMaximum attempts reached. Task failed.\033[0m")

if __name__ == "__main__":
    # Parse task description from command-line arguments
    parser = argparse.ArgumentParser(description="AI Task Automator")
    parser.add_argument('task', type=str, help='Task description to execute')
    args = parser.parse_args()

    agent = AIAgent()  # Create an instance of the AI agent
    agent.run(args.task)  # Start the agent with the provided task