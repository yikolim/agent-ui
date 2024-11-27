from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import subprocess
import os
import signal
from typing import Dict
from src.api.auth_config import verify_password, get_user 

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active processes and their working directories
active_sessions: Dict[str, dict] = {}

async def execute_command(websocket: WebSocket, command: str, session_id: str):
    try:
        # Get or initialize session info
        if session_id not in active_sessions:
            active_sessions[session_id] = {
                'cwd': os.path.expanduser('~'),  # Start in user's home directory
                'process': None
            }
        
        session = active_sessions[session_id]
        
        # Handle cd command specially
        if command.strip().startswith('cd'):
            try:
                # Extract the path argument
                _, *args = command.strip().split()
                new_path = args[0] if args else os.path.expanduser('~')
                
                # Handle relative and absolute paths
                if not os.path.isabs(new_path):
                    new_path = os.path.join(session['cwd'], new_path)
                
                # Resolve the absolute path
                new_path = os.path.abspath(new_path)
                
                # Check if the path exists and is a directory
                if os.path.exists(new_path) and os.path.isdir(new_path):
                    session['cwd'] = new_path
                    await websocket.send_json({
                        "type": "output",
                        "content": f"Changed directory to: {new_path}"
                    })
                else:
                    await websocket.send_json({
                        "type": "error",
                        "content": f"Directory not found: {new_path}"
                    })
            except Exception as e:
                await websocket.send_json({
                    "type": "error",
                    "content": f"Error changing directory: {str(e)}"
                })
            return

        # For other commands
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=session['cwd'],  # Use the current working directory
            preexec_fn=os.setsid
        )
        
        session['process'] = process
        
        # Stream output
        async def read_stream(stream, is_error=False):
            while True:
                line = await stream.readline()
                if not line:
                    break
                await websocket.send_json({
                    "type": "error" if is_error else "output",
                    "content": line.decode().strip()
                })

        # Read both stdout and stderr
        await asyncio.gather(
            read_stream(process.stdout),
            read_stream(process.stderr, True)
        )
        
        # Wait for process to complete
        await process.wait()
        
        # Send completion message
        await websocket.send_json({
            "type": "completion",
            "exit_code": process.returncode
        })
        
        # Send current working directory
        await websocket.send_json({
            "type": "cwd",
            "content": session['cwd']
        })
        
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "content": f"Error executing command: {str(e)}"
        })
    finally:
        if session_id in active_sessions:
            active_sessions[session_id]['process'] = None

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    
    try:
        # Initialize session with home directory
        if session_id not in active_sessions:
            active_sessions[session_id] = {
                'cwd': os.path.expanduser('~'),
                'process': None
            }
        
        # Send initial working directory
        await websocket.send_json({
            "type": "cwd",
            "content": active_sessions[session_id]['cwd']
        })
        
        while True:
            message = await websocket.receive_json()
            
            if message["type"] == "command":
                await execute_command(
                    websocket,
                    message["content"],
                    session_id
                )
            elif message["type"] == "interrupt":
                session = active_sessions.get(session_id)
                if session and session['process']:
                    try:
                        os.killpg(os.getpgid(session['process'].pid), signal.SIGINT)
                        await websocket.send_json({
                            "type": "output",
                            "content": "Command interrupted"
                        })
                    except Exception as e:
                        await websocket.send_json({
                            "type": "error",
                            "content": f"Error interrupting process: {str(e)}"
                        })
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        # Cleanup session
        if session_id in active_sessions:
            session = active_sessions[session_id]
            if session['process']:
                try:
                    os.killpg(os.getpgid(session['process'].pid), signal.SIGTERM)
                except:
                    pass
            del active_sessions[session_id]

if __name__ == "__main__":
    import uvicorn
    print("Starting server...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")