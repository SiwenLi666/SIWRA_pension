"""
Server startup script for the SIWRA Pension Advisor
"""
import os
import sys
import subprocess
import time
import signal
import platform
from dotenv import load_dotenv
import uvicorn
from src.main import app

def find_and_kill_process_on_port(port):
    """Find and kill any process using the specified port"""
    print(f"Checking for processes using port {port}...")
    
    if platform.system() == "Windows":
        # Windows implementation
        try:
            # Find process using the port
            netstat_output = subprocess.check_output(
                f"netstat -ano | findstr :{port}", shell=True
            ).decode('utf-8')
            
            if netstat_output:
                # Extract PID from netstat output
                for line in netstat_output.strip().split('\n'):
                    if f":{port}" in line:
                        parts = line.strip().split()
                        if len(parts) >= 5:
                            pid = parts[4]
                            print(f"Found process with PID {pid} using port {port}")
                            
                            # Kill the process
                            try:
                                subprocess.check_output(f"taskkill /PID {pid} /F", shell=True)
                                print(f"Successfully killed process with PID {pid}")
                                # Give the system a moment to release the port
                                time.sleep(1)
                                return True
                            except subprocess.CalledProcessError:
                                print(f"Failed to kill process with PID {pid}")
        except subprocess.CalledProcessError:
            # No process found using the port
            print(f"No process found using port {port}")
        except Exception as e:
            print(f"Error checking port: {str(e)}")
    else:
        # Linux/Mac implementation
        try:
            # Find process using the port
            lsof_output = subprocess.check_output(
                f"lsof -i :{port} -t", shell=True
            ).decode('utf-8')
            
            if lsof_output:
                pid = lsof_output.strip()
                print(f"Found process with PID {pid} using port {port}")
                
                # Kill the process
                try:
                    os.kill(int(pid), signal.SIGTERM)
                    print(f"Successfully killed process with PID {pid}")
                    # Give the system a moment to release the port
                    time.sleep(1)
                    return True
                except Exception as e:
                    print(f"Failed to kill process with PID {pid}: {str(e)}")
        except subprocess.CalledProcessError:
            # No process found using the port
            print(f"No process found using port {port}")
        except Exception as e:
            print(f"Error checking port: {str(e)}")
    
    return False

def main():
    # Load environment variables first
    load_dotenv()
    
    # Get configuration from environment
    host = os.getenv("HOST", "localhost")
    port = int(os.getenv("PORT", "9090"))
    
    # Kill any existing process using the port
    find_and_kill_process_on_port(port)
    
    print(f"Starting server on {host}:{port}")
    
    # Run the server with the app instance directly
    try:
        uvicorn.run(
            app,
            host=host,
            port=port,
            reload=False,
            workers=1,
            log_level="info"
        )
    except Exception as e:
        print(f"Error starting server: {str(e)}")
        # If the port is still in use, try to kill the process again and retry
        if "address already in use" in str(e).lower():
            print("Port is still in use. Trying again to kill the process...")
            if find_and_kill_process_on_port(port):
                print("Retrying server startup...")
                time.sleep(2)  # Give more time for the port to be released
                uvicorn.run(
                    app,
                    host=host,
                    port=port,
                    reload=False,
                    workers=1,
                    log_level="info"
                )

if __name__ == "__main__":
    main()
