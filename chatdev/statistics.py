import os

import numpy as np


def get_info(dir, log_filepath):
    print("dir:", dir)

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
    if num_prompt_tokens != -1:
        cost += num_prompt_tokens * 0.003 / 1000.0
    if num_completion_tokens != -1:
        cost += num_completion_tokens * 0.004 / 1000.0

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
