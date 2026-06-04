import asyncio
import shutil
import shlex

async def test():
    cli_path = "agy"
    cli_args = shlex.split(cli_path)
    resolved_exe = shutil.which(cli_args[0]) or cli_args[0]
    
    cmd = [resolved_exe] + cli_args[1:]
    cmd.extend([
        "-p", "what is 2+2",
        "--dangerously-skip-permissions"
    ])
    
    print(f"Running command: {cmd}")
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await process.communicate()
    
    print("--- STDOUT ---")
    print(stdout.decode("utf-8", errors="ignore"))
    print("--- STDERR ---")
    print(stderr.decode("utf-8", errors="ignore"))
    print(f"Exit code: {process.returncode}")

if __name__ == "__main__":
    asyncio.run(test())
