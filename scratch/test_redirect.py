import subprocess
import os

SUMMARIZER_PROMPT = (
    "Сделай краткое саммари переписки. Напиши 3 главных пункта."
)

directive_prompt = (
    "Сделай структурированное саммари переписки из стандартного ввода (stdin) строго по инструкции, "
    "указанной в начале stdin. Не запускай никаких инструментов, не пиши код и не задавай вопросов. "
    "Просто выведи готовый текст саммари на русском языке."
)

def test():
    # Мы знаем, что на локальной машине AGY_CLI_PATH равен "agy"
    cli_path = "agy"
    
    # Файлы для обмена
    input_file = "temp_input.txt"
    output_file = "temp_output.txt"
    
    messages_text = "[10:00] [Иван]: Привет всем! Сегодня сдаем лабу?\n[10:01] [Петр]: Да, препод сказал до 12:00 прислать."
    combined_input = f"ИНСТРУКЦИЯ ПО СОЗДАНИЮ САММАРИ:\n{SUMMARIZER_PROMPT}\n\nТЕКСТ ПЕРЕПИСКИ ДЛЯ АНАЛИЗА:\n{messages_text}"
    
    # Записываем входные данные во временный файл
    with open(input_file, "w", encoding="utf-8") as f:
        f.write(combined_input)
        
    # Формируем команду для запуска через shell с перенаправлением ввода и вывода
    # На Windows и Linux синтаксис '<' и '>' одинаков для перенаправления файлов!
    cmd_str = f'agy -p "{directive_prompt}" --dangerously-skip-permissions < {input_file} > {output_file}'
    
    print(f"Running command via shell: {cmd_str}")
    
    # Запускаем через shell
    result = subprocess.run(cmd_str, shell=True, capture_output=True, text=True)
    
    print(f"Subprocess return code: {result.returncode}")
    print(f"Subprocess stderr: {result.stderr}")
    
    # Читаем выходной файл
    if os.path.exists(output_file):
        with open(output_file, "r", encoding="utf-8", errors="ignore") as f:
            output_content = f.read()
        print("--- CAPTURED OUTPUT FROM FILE ---")
        print(output_content)
        # Удаляем временные файлы
        os.remove(output_file)
    else:
        print("Output file was not created!")
        
    if os.path.exists(input_file):
        os.remove(input_file)

if __name__ == "__main__":
    test()
