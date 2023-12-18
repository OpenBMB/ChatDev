import html
import logging
import re
import time

import markdown
import inspect
from camel.messages.system_messages import SystemMessage
from visualizer.app import send_msg


def now():
    return time.strftime("%Y%m%d%H%M%S", time.localtime())


def log_visualize(role, content=None):
    """
    send the role and content to visualizer server to show log on webpage in real-time
    You can leave the role undefined and just pass the content, i.e. log_visualize("messages"), where the role is "System".
    Args:
        role: the agent that sends message
        content: the content of message

    Returns: None

    """
    if not content:
        logging.info(role + "\n")
        send_msg("System", role)
        print(role + "\n")
    else:
        print(str(role) + ": " + str(content) + "\n")
        logging.info(str(role) + ": " + str(content) + "\n")
        if isinstance(content, SystemMessage):
            records_kv = []
            content.meta_dict["content"] = content.content
            for key in content.meta_dict:
                value = content.meta_dict[key]
                value = escape_string(value)
                records_kv.append([key, value])
            content = "**[SystemMessage**]\n\n" + convert_to_markdown_table(records_kv)
        else:
            role = str(role)
            content = str(content)
        send_msg(role, content)


def convert_to_markdown_table(records_kv):
    # Create the Markdown table header
    header = "| Parameter | Value |\n| --- | --- |"

    # Create the Markdown table rows
    rows = [f"| **{key}** | {value} |" for (key, value) in records_kv]

    # Combine the header and rows to form the final Markdown table
    markdown_table = header + "\n" + '\n'.join(rows)

    return markdown_table


def log_arguments(func):
    def wrapper(*args, **kwargs):
        sig = inspect.signature(func)
        params = sig.parameters

        all_args = {}
        all_args.update({name: value for name, value in zip(params.keys(), args)})
        all_args.update(kwargs)

        records_kv = []
        for name, value in all_args.items():
            if name in ["self", "chat_env", "task_type"]:
                continue
            value = escape_string(value)
            records_kv.append([name, value])
        records = f"**[{func.__name__}]**\n\n" + convert_to_markdown_table(records_kv)
        log_visualize("System", records)

        return func(*args, **kwargs)

    return wrapper

def escape_string(value):
    value = str(value)
    value = html.unescape(value)
    value = markdown.markdown(value)
    value = re.sub(r'<[^>]*>', '', value)
    value = value.replace("\n", " ")
    return value
