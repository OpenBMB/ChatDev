import os

import numpy as np


def prompt_cost(model_type: str, num_prompt_tokens: float, num_completion_tokens: float):
    input_cost_map = {
        "gpt-3.5-turbo": 0.0015,
        "gpt-3.5-turbo-16k": 0.003,
        "gpt-3.5-turbo-0613": 0.0015,
        "gpt-3.5-turbo-16k-0613": 0.003,
        "gpt-4": 0.03,
        "gpt-4-0613": 0.03,
        "gpt-4-32k": 0.06,
    }

    output_cost_map = {
        "gpt-3.5-turbo": 0.002,
        "gpt-3.5-turbo-16k": 0.004,
        "gpt-3.5-turbo-0613": 0.002,
        "gpt-3.5-turbo-16k-0613": 0.004,
        "gpt-4": 0.06,
        "gpt-4-0613": 0.06,
        "gpt-4-32k": 0.12,
    }

    if model_type not in input_cost_map or model_type not in output_cost_map:
        return -1

    return num_prompt_tokens * input_cost_map[model_type] / 1000.0 + num_completion_tokens * output_cost_map[model_type] / 1000.0


def get_info(dir, log_filepath):
    print("dir:", dir)

    model_type = ""
    version_updates = -1
    num_code_files = -1
    num_png_files = -1
    num_doc_files = -1
    code_lines = -1
    env_lines = -1
    manual_lines = -1
    duration = -1
    num_utterance = -1
    num_reflection = -1
    num_prompt_tokens = -1
    num_completion_tokens = -1
    num_total_tokens = -1

    if os.path.exists(dir):
        filenames = os.listdir(dir)
        # print(filenames)

        num_code_files = len([filename for filename in filenames if filename.endswith(".py")])
        # print("num_code_files:", num_code_files)

        num_png_files = len([filename for filename in filenames if filename.endswith(".png")])
        # print("num_png_files:", num_png_files)

        num_doc_files = 0
        for filename in filenames:
            if filename.endswith(".py") or filename.endswith(".png"):
                continue
            if os.path.isfile(os.path.join(dir, filename)):
                # print(filename)
                num_doc_files += 1
        # print("num_doc_files:", num_doc_files)

        if "meta.txt" in filenames:
            lines = open(os.path.join(dir, "meta.txt"), "r", encoding="utf8").read().split("\n")
            version_updates = float([lines[i + 1] for i, line in enumerate(lines) if "Code_Version" in line][0]) + 1
        else:
            version_updates = -1
        # print("version_updates: ", version_updates)

        if "requirements.txt" in filenames:
            lines = open(os.path.join(dir, "requirements.txt"), "r", encoding="utf8").read().split("\n")
            env_lines = len([line for line in lines if len(line.strip()) > 0])
        else:
            env_lines = -1
        # print("env_lines:", env_lines)

        if "manual.md" in filenames:
            lines = open(os.path.join(dir, "manual.md"), "r", encoding="utf8").read().split("\n")
            manual_lines = len([line for line in lines if len(line.strip()) > 0])
        else:
            manual_lines = -1
        # print("manual_lines:", manual_lines)

        code_lines = 0
        for filename in filenames:
            if filename.endswith(".py"):
                # print("......filename:", filename)
                lines = open(os.path.join(dir, filename), "r", encoding="utf8").read().split("\n")
                code_lines += len([line for line in lines if len(line.strip()) > 0])
        # print("code_lines:", code_lines)

        lines = open(log_filepath, "r", encoding="utf8").read().split("\n")
        sublines = [line for line in lines if "| **model_type** |" in line]
        if len(sublines) > 0:
            model_type = sublines[0].split("| **model_type** | ModelType.")[-1].split(" | ")[0]
            model_type = model_type[:-2]
            if model_type == "GPT_3_5_TURBO":
                model_type = "gpt-3.5-turbo"
            elif model_type == "GPT_4":
                model_type = "gpt-4"
            elif model_type == "GPT_4_32k":
                model_type = "gpt-4-32k"
            # print("model_type:", model_type)
        
        lines = open(log_filepath, "r", encoding="utf8").read().split("\n")
        start_lines = [line for line in lines if "**[Start Chat]**" in line]
        chat_lines = [line for line in lines if "<->" in line]
        num_utterance = len(start_lines) + len(chat_lines)
        # print("num_utterance:", num_utterance)

        lines = open(log_filepath, "r", encoding="utf8").read().split("\n")
        sublines = [line for line in lines if line.startswith("prompt_tokens:")]
        if len(sublines) > 0:
            nums = [int(line.split(": ")[-1]) for line in sublines]
            num_prompt_tokens = np.sum(nums)
            # print("num_prompt_tokens:", num_prompt_tokens)

        lines = open(log_filepath, "r", encoding="utf8").read().split("\n")
        sublines = [line for line in lines if line.startswith("completion_tokens:")]
        if len(sublines) > 0:
            nums = [int(line.split(": ")[-1]) for line in sublines]
            num_completion_tokens = np.sum(nums)
            # print("num_completion_tokens:", num_completion_tokens)

        lines = open(log_filepath, "r", encoding="utf8").read().split("\n")
        sublines = [line for line in lines if line.startswith("total_tokens:")]
        if len(sublines) > 0:
            nums = [int(line.split(": ")[-1]) for line in sublines]
            num_total_tokens = np.sum(nums)
            # print("num_total_tokens:", num_total_tokens)

        lines = open(log_filepath, "r", encoding="utf8").read().split("\n")

        lines = open(log_filepath, "r", encoding="utf8").read().split("\n")
        num_reflection = 0
        for line in lines:
            if "on : Reflection" in line:
                num_reflection += 1
        # print("num_reflection:", num_reflection)

    cost = 0.0
    if num_png_files != -1:
        cost += num_png_files * 0.016
    if prompt_cost(model_type, num_prompt_tokens, num_completion_tokens) != -1:
        cost += prompt_cost(model_type, num_prompt_tokens, num_completion_tokens)

    # info = f"🕑duration={duration}s 💰cost=${cost} 🔨version_updates={version_updates} 📃num_code_files={num_code_files} 🏞num_png_files={num_png_files} 📚num_doc_files={num_doc_files} 📃code_lines={code_lines} 📋env_lines={env_lines} 📒manual_lines={manual_lines} 🗣num_utterances={num_utterance} 🤔num_self_reflections={num_reflection} ❓num_prompt_tokens={num_prompt_tokens} ❗num_completion_tokens={num_completion_tokens} ⁉️num_total_tokens={num_total_tokens}"

    info = "\n\n💰**cost**=${:.6f}\n\n🔨**version_updates**={}\n\n📃**num_code_files**={}\n\n🏞**num_png_files**={}\n\n📚**num_doc_files**={}\n\n📃**code_lines**={}\n\n📋**env_lines**={}\n\n📒**manual_lines**={}\n\n🗣**num_utterances**={}\n\n🤔**num_self_reflections**={}\n\n❓**num_prompt_tokens**={}\n\n❗**num_completion_tokens**={}\n\n🌟**num_total_tokens**={}" \
        .format(cost,
                version_updates,
                num_code_files,
                num_png_files,
                num_doc_files,
                code_lines,
                env_lines,
                manual_lines,
                num_utterance,
                num_reflection,
                num_prompt_tokens,
                num_completion_tokens,
                num_total_tokens)

    return info
