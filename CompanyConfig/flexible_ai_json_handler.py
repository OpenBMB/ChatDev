import openai
import json
import os
import argparse
from dotenv import load_dotenv
from typing import List, Dict, Any
from urllib.parse import urlparse

# Load environment variables from .env file
load_dotenv()

def get_api_key(api_base: str) -> str:
    """
    Get the API key based on the API base URL.

    Args:
        api_base (str): The base URL of the API.

    Returns:
        str: The API key.
    """
    if not api_base:
        return os.getenv('OPENAI_API_KEY')
    
    domain = urlparse(api_base).netloc
    env_var_name = domain.split('.')[-2].upper()
    api_key = os.getenv(env_var_name)
    
    if not api_key:
        raise ValueError(f"API key not found for {domain}. Please set {env_var_name} in your .env file.")
    
    return api_key

def process_object_with_prompt(object: Dict[str, Any], prompt: str, model: str) -> str:
    """
    Process a single object with the specified model using the given prompt.

    Args:
        object (Dict[str, Any]): The object to process.
        prompt (str): The prompt to use for processing.
        model (str): The model to use for processing.

    Returns:
        str: The processed text from the model.
    """
    response = openai.ChatCompletion.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"{prompt}\n{json.dumps(object)}"}
        ],
        max_tokens=150,
        n=1,
        stop=None,
        temperature=0.7
    )
    return response.choices[0].message['content'].strip()

def process_json_file(input_file_path: str, output_file_path: str, prompt: str, interactive: bool, model: str) -> None:
    """
    Process a JSON file, applying the specified model to each object.

    Args:
        input_file_path (str): Path to the input JSON file.
        output_file_path (str): Path to the output JSON file.
        prompt (str): The initial prompt to use for processing.
        interactive (bool): Whether to use interactive mode for prompts.
        model (str): The model to use for processing.
    """
    with open(input_file_path, 'r') as infile:
        data = json.load(infile)

    processed_data = []
    for obj in data:
        current_prompt = prompt
        if interactive:
            print(f"Current object: {json.dumps(obj, indent=2)}")
            new_prompt = input(f"Current prompt: {prompt}\nEnter new prompt or press Enter to keep the current prompt: ")
            if new_prompt.strip():
                current_prompt = new_prompt.strip()
        
        processed_text = process_object_with_prompt(obj, current_prompt, model)
        processed_data.append(processed_text)
    
    with open(output_file_path, 'w') as outfile:
        json.dump(processed_data, outfile, indent=2)

def list_available_models(api_base: str) -> List[str]:
    """
    List available models from the specified API endpoint.

    Args:
        api_base (str): The base URL of the API.

    Returns:
        List[str]: A list of available model names.
    """
    try:
        response = openai.models.list()
        return [model['id'] for model in response['data']]
    except Exception as e:
        print(f"Error listing models: {str(e)}")
        return []

def main():
    parser = argparse.ArgumentParser(description="Process a JSON file with a specified model using OpenAI-compatible API.")
    parser.add_argument("input_file", nargs='?', help="Path to the input JSON file.")
    parser.add_argument("output_file", nargs="?", default="output.json", help="Path to the output JSON file (default: output.json).")
    parser.add_argument("prompt", nargs="?", default="Summarize the following information:", help="Prompt to send to the model (default: 'Summarize the following information:').")
    parser.add_argument("-i", "--interactive", action="store_true", help="Interactive mode to change prompt for each object.")
    parser.add_argument("-m", "--model", default="gpt-4-mini", help="Model to use (default: gpt-4-mini).")
    parser.add_argument("-e", "--endpoint", default="", help="API endpoint (e.g., https://api.groq.com/openai/v1).")
    parser.add_argument("-l", "--list-models", action="store_true", help="List available models and exit.")
    
    args = parser.parse_args()
    
    # Set up the API configuration
    openai.api_key = get_api_key(args.endpoint)
    if args.endpoint:
        openai.api_base = args.endpoint

    if args.list_models:
        models = list_available_models(args.endpoint)
        print("Available models:")
        for model in models:
            print(f"- {model}")
        return

    if not args.input_file:
        parser.error("input_file is required unless --list-models is specified.")

    process_json_file(args.input_file, args.output_file, args.prompt, args.interactive, args.model)

if __name__ == "__main__":
    main()