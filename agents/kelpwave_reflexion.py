#!/usr/bin/env python3
import os, sys, re, json, time, subprocess
from datetime import datetime

C_BLUE, C_GREEN, C_YELLOW, C_RED, C_CYAN, C_MAGENTA, C_BOLD, C_END = "\033[94m", "\033[92m", "\033[93m", "\033[91m", "\033[96m", "\033[95m", "\033[1m", "\033[0m"

# Пути
LLAMA_CLI_PATH = "/data/data/com.termux/files/home/llama.cpp/build/bin/llama-completion"
DOWNLOADS_DIR = "/data/data/com.termux/files/home/storage/shared/Download/kelpwave"

# Напоминание: после скачивания 7B-модели поменяй имя файла ниже!
MODEL_PATH = os.path.join(DOWNLOADS_DIR, "qwen2.5-0.5b-instruct-q4_k_m.gguf")

KNOWLEDGE_PATH = os.path.join(DOWNLOADS_DIR, "lessons_learned.json")
SOLUTION_PATH = os.path.join(DOWNLOADS_DIR, "solution.py")

B = chr(96) * 3

SYSTEM_PROMPT = f"""You are "kelpwave-coder", an elite autonomous AI Agent.
Your job is to write a single Python script 'solution.py' to accomplish the user's task.

You must output your response in this exact format:
THOUGHT: [Describe your thoughts and plans here]
CODE:
{B}python
# [Write your fully working python code here]
{B}

Do not output any JSON. Just write standard Python code inside the markdown block."""

def run_local_model(prompt, max_tokens=512, temp=0.1):
    temp_prompt_path = os.path.join(DOWNLOADS_DIR, "temp_prompt.txt")
    temp_output_path = os.path.join(DOWNLOADS_DIR, "temp_output.txt")
    temp_error_path = os.path.join(DOWNLOADS_DIR, "temp_error.txt")

    with open(temp_prompt_path, "w", encoding="utf-8") as f:
        f.write(prompt)
        
    cmd = (
        f'"{LLAMA_CLI_PATH}" -m "{MODEL_PATH}" -f "{temp_prompt_path}" '
        f'-n {max_tokens} -t 4 --temp {temp} --no-display-prompt -no-cnv > "{temp_output_path}" 2> "{temp_error_path}"'
    )
    
    try:
        subprocess.run(cmd, shell=True, timeout=120)
        if os.path.exists(temp_error_path):
            with open(temp_error_path, "r", encoding="utf-8") as f:
                err = f.read().strip()
                if err: print(f"\n{C_RED}[DEBUG ERROR LOG]:\n{err}{C_END}\n")
                    
        if os.path.exists(temp_output_path):
            with open(temp_output_path, "r", encoding="utf-8") as f:
                res_text = f.read().strip()
        else:
            res_text = ""
        return res_text
    except Exception as e:
        return f"Error: {e}"
    finally:
        for temp_file in [temp_prompt_path, temp_output_path, temp_error_path]:
            if os.path.exists(temp_file):
                try: os.remove(temp_file)
                except: pass

def extract_code_block(text):
    pattern = r"" + B + r"python\s*(.*?)\s*" + B
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if match: return match.group(1).strip()
    
    pattern_fallback = r"" + B + r"\s*(.*?)\s*" + B
    match_fallback = re.search(pattern_fallback, text, re.DOTALL)
    if match_fallback: return match_fallback.group(1).strip()
    
    clean_text = text.replace("CODE:", "").replace("THOUGHT:", "").strip()
    if any(kw in clean_text for kw in ["def ", "print(", "import ", "try:", "names ="]):
        return clean_text
    return ""

def parse_thought(text):
    pattern = r"THOUGHT:\s*(.*?)(?=\nCODE:|\n" + B + r"|\Z)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""

def load_lessons():
    if os.path.exists(KNOWLEDGE_PATH):
        try:
            with open(KNOWLEDGE_PATH, "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return []

def save_lessons(lessons):
    with open(KNOWLEDGE_PATH, "w", encoding="utf-8") as f: json.dump(lessons, f, indent=2, ensure_ascii=False)

def reflect_and_learn(code_attempt, error_output):
    print(f"{C_BOLD}{C_MAGENTA}[🧠 REFLEXION] Analyzing failure and generating new knowledge...{C_END}")
    prompt = (
        f"<|im_start|>system\nYou are 'kelpwave-reflexion', an advanced self-learning optimizer. "
        f"Analyze the following failing Python code and its error traceback. "
        f"Write a single, concise 'Lesson Learned' (one sentence) that explains how to prevent "
        f"this error in the future. Be highly specific and technical.<|im_end|>\n"
        f"<|im_start|>user\nFailing Code:\n```python\n{code_attempt}\n```\n\nError Output:\n{error_output}\n"
        f"Generate the lesson learned.<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )
    lesson = run_local_model(prompt, max_tokens=150)
    return lesson.replace("[end of text]", "").replace("<|im_end|>", "").strip()

def run_session(task):
    print(f"\n{C_BOLD}{C_GREEN}🚀 STARTING SELF-LEARNING AGENT SESSION (DOWNLOADS MODE)...{C_END}")
    print(f"Goal: {task}")
    print("="*60)
    attempt, success, max_attempts = 1, False, 3
    while attempt <= max_attempts and not success:
        print(f"\n{C_BOLD}{C_BLUE}--- ATTEMPT {attempt} of {max_attempts} ---{C_END}")
        lessons = load_lessons()
        lessons_context = ""
        if lessons:
            lessons_context = "\nTHESE ARE LESSONS YOU LEARNED FROM PREVIOUS FAILURES. YOU MUST OBEY THEM:\n" + "\n".join(f"- {l}" for l in lessons)
            
        prompt = f"<|im_start|>system\n{SYSTEM_PROMPT}\n{lessons_context}<|im_end|>\n<|im_start|>user\n{task}<|im_end|>\n<|im_start|>assistant\nTHOUGHT:"
        print("[*] Generating code...")
        output = run_local_model(prompt)
        
        print(f"\n{C_YELLOW}--- RAW MODEL OUTPUT ---{C_END}\n{output}\n" + "="*50)
        
        thought = parse_thought(output)
        code = extract_code_block(output)
        if thought: print(f"\n🧠 {C_BOLD}{C_CYAN}Thought:{C_END} {thought}")
        
        if code.strip():
            # Бэкапим и архивируем успешные старые файлы, чтобы бот ничего не стирал!
            if os.path.exists(SOLUTION_PATH):
                try:
                    with open(SOLUTION_PATH, "r", encoding="utf-8") as rf:
                        old_code = rf.read().strip()
                    if len(old_code) > 5:
                        archive_path = os.path.join(DOWNLOADS_DIR, f"successful_solution_{int(time.time())}.py")
                        with open(archive_path, "w", encoding="utf-8") as wf:
                            wf.write(old_code)
                        print(f"👣 [ARCHIVE] Archived previous successful solution to '{archive_path}'")
                except: pass

            with open(SOLUTION_PATH, "w", encoding="utf-8") as f: f.write(code)
            print(f"📝 {C_GREEN}[+] Code successfully written to '{SOLUTION_PATH}'{C_END}")
            print("[*] Automatically executing solution.py to verify...")
            result = subprocess.run(f"python3 {SOLUTION_PATH}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
            stdout, stderr = result.stdout.strip(), result.stderr.strip()
            if stdout: print(f"STDOUT:\n{stdout}")
            if result.returncode == 0 and not stderr:
                print(f"\n{C_BOLD}{C_GREEN}✅ SUCCESS! Code executed with no errors.{C_END}")
                success = True
                with open(SOLUTION_PATH, "a", encoding="utf-8") as f:
                    f.write(f"\n# ✅ SUCCESSFUL AGENT RUN AT {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                break
            else:
                print(f"\n{C_BOLD}{C_RED}❌ FAILURE! Code crashed.{C_END}")
                error_msg = stderr if stderr else "Returned non-zero code."
                print(f"Traceback/Error:\n{C_RED}{error_msg}{C_END}\n")
                with open(SOLUTION_PATH, "r", encoding="utf-8") as f: code_attempt = f.read()
                new_lesson = reflect_and_learn(code_attempt, error_msg)
                print(f"{C_BOLD}{C_GREEN}[💡 LEARNED NEW INSIGHT]:{C_END} {new_lesson}")
                lessons.append(new_lesson)
                save_lessons(lessons)
                attempt += 1
                time.sleep(1)
        else:
            print(f"\n{C_RED}❌ FAILURE! No valid Python code block was generated by the model.{C_END}")
            new_lesson = reflect_and_learn(output, "Model generated empty or unparseable code block. Ensure you write python code inside ```python ... ``` block.")
            print(f"{C_BOLD}{C_GREEN}[💡 LEARNED NEW INSIGHT]:{C_END} {new_lesson}")
            lessons.append(new_lesson)
            save_lessons(lessons)
            attempt += 1
            time.sleep(1)
            
    if success: print(f"\n{C_BOLD}{C_GREEN}🎯 GOAL ACCOMPLISHED BY SELF-LEARNING AGENT!{C_END}")
    else: print(f"\n{C_RED}⚠️ Session failed within {max_attempts} attempts.{C_END}")

if __name__ == "__main__":
    print('\033[94m🌊 KELPWAVE - DEEP PERSISTENT LEARNING ENGINE\033[0m')
    print("\nDescribe the programming task you want the ИИ Agent to solve autonomously.")
    try:
        user_task = input(f"{C_BOLD}Enter Goal (or press Enter for default test):{C_END} ").strip()
    except KeyboardInterrupt:
        sys.exit(0)
        
    if not user_task:
        user_task = "Write a python script solution.py that defines a list of names ['kelpwave', 'freedrich', 'zanbot'] and prints the name at index 5, but gracefully catches any IndexError and prints 'Out of bounds' instead of crashing."
        
    run_session(user_task)
