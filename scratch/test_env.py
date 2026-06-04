import asyncio
import shutil
import shlex
import os

async def run_with_env(env_updates):
    cli_path = "agy"
    cli_args = shlex.split(cli_path)
    resolved_exe = shutil.which(cli_args[0]) or cli_args[0]
    
    cmd = [resolved_exe] + cli_args[1:]
    cmd.extend([
        "-p", "what is 2+2",
        "--dangerously-skip-permissions"
    ])
    
    # Копируем текущее окружение и обновляем его
    env = os.environ.copy()
    env.update(env_updates)
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env
    )
    
    stdout, stderr = await process.communicate()
    
    stdout_str = stdout.decode("utf-8", errors="ignore")
    stderr_str = stderr.decode("utf-8", errors="ignore")
    
    print(f"\n--- ENV: {env_updates} ---")
    print(f"Exit code: {process.returncode}")
    print(f"Captured STDOUT: {repr(stdout_str)}")
    print(f"Captured STDERR: {repr(stderr_str)}")

async def main():
    # Проверяем разные переменные
    await run_with_env({"TERM": "dumb"})
    await run_with_env({"NO_COLOR": "1"})
    await run_with_env({"TERM": "dumb", "NO_COLOR": "1"})
    # Попробуем очистить переменные терминала
    await run_with_env({"TERM": "", "COLORTERM": ""})

if __name__ == "__main__":
    asyncio.run(main())
