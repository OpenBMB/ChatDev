import os
import json
import yaml
import shutil

#TODO: Convert all files to yaml
#TODO: Parse the yaml instead of JSON in the app and visualizer

def json_to_yaml(json_data):
    """Convert JSON data to YAML format."""
    return yaml.dump(json_data, default_flow_style=False, sort_keys=True)


def convert_directory(src_dir, dest_dir):
    """Convert all JSON files in src_dir to YAML files in dest_dir."""
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)

    for root, dirs, files in os.walk(src_dir):
        # Determine the relative path from the source directory
        relative_path = os.path.relpath(root, src_dir)
        # Determine the corresponding destination directory
        dest_root = os.path.join(dest_dir, relative_path)
        if not os.path.exists(dest_root):
            os.makedirs(dest_root)

        for file in files:
            if file.lower().endswith(".json"):
                src_file_path = os.path.join(root, file)
                dest_file_path = os.path.join(
                    dest_root, file.rsplit(".", 1)[0] + ".yaml"
                )

                # Read JSON file
                with open(src_file_path, "r") as json_file:
                    json_data = json.load(json_file)

                # Convert to YAML
                yaml_data = json_to_yaml(json_data)

                # Write YAML file
                with open(dest_file_path, "w") as yaml_file:
                    yaml_file.write(yaml_data)

                print(f"Converted {src_file_path} to {dest_file_path}")


def main():
    src_dir = input("Enter the path to the source directory: ").strip()
    dest_dir = src_dir + "_yaml"

    if not os.path.isdir(src_dir):
        print(f"Source directory {src_dir} does not exist.")
        return

    print(f"Converting JSON files from {src_dir} to YAML files in {dest_dir}...")
    convert_directory(src_dir, dest_dir)
    print("Conversion completed.")


if __name__ == "__main__":
    main()
