import json  
import os
import argparse
filter_threshold = 0.9

def filter_valuegain(directory, filtered_directory): 
    """filter memory by experience's valueGain, delete experience whose valueGain is smaller than filter_threshold  

    Keyword arguments:
    directory -- the input directory of MemoryCards, like "./ecl/memory/MemoryCards.json"
    filtered_directory -- the output directory of filtered MemoryCards, like "./ecl/memory/MemoryCards.json"
    """
    with open(directory) as file:
        content = json.load(file)
        new_content = []
        for memorypiece in content:
            experiences = memorypiece.get("experiences")
            filtered_experienceList = []
            
            if experiences != None:
                print("origin:",len(experiences))
                for experience in experiences:
                    valueGain = experience.get("valueGain")
                    print(valueGain)
                    if valueGain >= filter_threshold:
                        filtered_experienceList.append(experience)
                print(len(experiences))
                memorypiece["experiences"] = filtered_experienceList
                new_content.append(memorypiece)
            else:
                new_content.append(memorypiece)
        file.close()
    with open(filtered_directory, 'w') as file:
        json.dump(content, file)
        file.close()


def main():
    parser = argparse.ArgumentParser(description="Process some directories.")
    parser.add_argument("threshold", type=float, help="The filtered threshold for experiences")
    parser.add_argument("directory", type = str, help="The directory to process")
    parser.add_argument("filtered_directory", type= str, help="The directory for output")


    args = parser.parse_args()
    filter_threshold = args.threshold 
    filter_valuegain(args.directory, args.filtered_directory)

if __name__ == "__main__":
    main()