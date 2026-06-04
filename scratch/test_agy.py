import asyncio
import platform
import shutil
import shlex
import subprocess

SUMMARIZER_PROMPT = (
    "Сделай краткое саммари переписки. Напиши 3 главных пункта."
)

directive_prompt = (
    "Сделай структурированное саммари переписки из стандартного ввода (stdin) строго по инструкции, "
    "указанной в начале stdin. Не запускай никаких инструментов, не пиши код и не задавай вопросов. "
    "Просто выведи готовый текст саммари на русском языке."
)

async def test():
    cli_path = "agy"
    cli_args = shlex.split(cli_path)
    resolved_exe = shutil.which(cli_args[0]) or cli_args[0]
    
    cmd = [resolved_exe] + cli_args[1:]
    cmd.extend([
        "-p", directive_prompt,
        "--dangerously-skip-permissions"
    ])
    
    print(f"Running command: {cmd}")
    
    # Добавляем флаг создания процесса без окна консоли на Windows
    extra_args = {}
    if platform.system() == "Windows":
        extra_args["creationflags"] = 0x08000000 # CREATE_NO_WINDOW
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        **extra_args
    )
    
    messages_text = "[10:00] [Иван]: Привет всем! Сегодня сдаем лабу?\n[10:01] [Петр]: Да, препод сказал до 12:00 прислать."
    combined_input = f"ИНСТРУКЦИЯ ПО СОЗДАНИЮ САММАРИ:\n{SUMMARIZER_PROMPT}\n\nТЕКСТ ПЕРЕПИСКИ ДЛЯ АНАЛИЗА:\n{messages_text}"
    
    stdout, stderr = await process.communicate(input=combined_input.encode("utf-8"))
    
    print("--- STDOUT ---")
    print(stdout.decode("utf-8", errors="ignore"))
    print("--- STDERR ---")
    print(stderr.decode("utf-8", errors="ignore"))
    print(f"Exit code: {process.returncode}")

if __name__ == "__main__":
    asyncio.run(test())
