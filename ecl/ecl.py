
import argparse
from graph import Graph
from experience import Experience
from utils import get_easyDict_from_filepath,now ,log_and_print_online
from memory import Memory
import sys
import os 
import logging
sys.path.append(os.path.join(os.getcwd(),"ecl"))


def memorize(directory):
    print(directory)
    cfg = get_easyDict_from_filepath("./ecl/config.yaml")
    
    folder_path = "ecl/logs"
    if not os.path.exists(folder_path):
        os.mkdir(folder_path)
    log_filename = folder_path+"/ecl_{}.log".format(os.path.basename(directory))
    print(log_filename)
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    file_handler = logging.FileHandler(log_filename, mode='w', encoding='utf-8')
    formatter = logging.Formatter('[%(asctime)s %(levelname)s] %(message)s', datefmt='%Y-%d-%m %H:%M:%S')
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    root_logger.setLevel(logging.INFO)

    log_and_print_online("[Config]:"+str(cfg))
    graph = Graph()
    graph.create_from_log(directory)
    graph.print()

    experience = Experience(graph, directory)
    if len(graph.nodes)==0 or len(graph.edges) == 0:
        log_and_print_online("No node or no edges constrcuted from the task execution process, maybe due to a unfinished software production or sometimes single node appears")
    else:
        if cfg.experience.reap_zombie:
            experience.reap_zombie()
            graph.print()
    experience.estimate()
    experiences = experience.extract_thresholded_experiences()

    # memory upload 
    memory = Memory()
    memory.upload()
    memory.upload_from_experience(experience)

def process_directory(directory):
    for root, dirs, files in os.walk(directory):
        for directory in dirs:
            file_path = os.path.join(root, directory)
            memorize(file_path)

def main():
    parser = argparse.ArgumentParser(description="Memorize one software or softwares from the directory.")
    parser.add_argument("path", help="The file or directory to process")
    parser.add_argument("-d", "--directory", action="store_true", help="Process all files in the given directory.")
    args = parser.parse_args()

    if args.directory:
        process_directory(args.path)
    else:
        memorize(args.path)

if __name__ == "__main__":
    main()