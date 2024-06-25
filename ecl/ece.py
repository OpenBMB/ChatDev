
import os
import json
import re
import numpy as np
import argparse
point = 0.95
eliminate_threshold = 0.95


def retrieve_eliminate(Path_directory,UsedMemory_directory,Evolved_directory):
    experiences_use = []
    content = []
    content1 = []
    experiences_total = []
    usetime_total = []
    exp_dict = {}
    eliminated_exp = []

    directories = [os.path.join(Path_directory, d) for d in os.listdir(Path_directory) if os.path.isdir(os.path.join(Path_directory, d))]
    for subdir in directories:
        directory = subdir
        logdir = [filename for filename in os.listdir(directory) if filename.endswith(".log")]
        logdir = os.path.join(directory, logdir[0])
        content1 = open(logdir, "r", encoding='UTF-8').read()

        pattern1 = re.compile(r'the source code MIDs is (.*?),', re.S)
        experiences_sourceMIDs = re.findall(pattern1, content1)
        pattern2 = re.compile(r'the target code MIDs is (.*?)\n',re.S)
        experiences_targetMIDs = re.findall(pattern2, content1)
        pattern3 = re.compile(r'And the (.*?) similarity is',re.S)
        experiences_type = re.findall(pattern3,content1)
        for i in range(0,len(experiences_sourceMIDs)):
            sourceMID = experiences_sourceMIDs[i]
            targetMID = experiences_targetMIDs[i]
            type = experiences_type[i]
            experiences_use.append((sourceMID,targetMID,type))

    with open(UsedMemory_directory) as file:
        content1 = json.load(file)
        new_content = []
        for memorypiece in content1:
            experiences = memorypiece.get("experiences")
            if experiences != None:
                experiences_total.extend(experiences)
                for experience in experiences:
                    experience["use_time"] = 0
        for experience in experiences_use:
            for experience_t in experiences_total:
                if experience[0] == experience_t["sourceMID"] and experience[1] == experience_t["targetMID"]:
                    experience_t["use_time"] += 1
        for i,experience_t in enumerate(experiences_total):
            usetime_total.append(experience_t["use_time"])
            exp_dict[i] = experience_t["use_time"]
        file.close()

    usetime_sort = sorted(usetime_total)[::-1]
    total = np.sum(usetime_sort)
    for i in range(len(usetime_sort)):
        if np.sum(usetime_sort[:i])/total >= point:
            # print("α：",i)
            alpha= i
            break
    index=0
    for k in sorted(exp_dict,key=exp_dict.__getitem__,reverse=True):
        if index <= alpha:
            eliminated_exp.append(experiences_total[k])
            index += 1
        else:
            break

    for memorypiece in content1:
        experiences = memorypiece.get("experiences")
        retrieve_eliminated_experienceList = []
        if experiences != None:
            for experience in experiences:
                if experience in eliminated_exp:
                    retrieve_eliminated_experienceList.append(experience)

        memorypiece["experiences"] = retrieve_eliminated_experienceList
        new_content.append(memorypiece)

    with open(Evolved_directory, 'w') as file:
        json.dump(new_content, file)


# Quality score gain Elimination
def gain_eliminate(NewMemory_directory,Evolved_directory):
    content2 = []
    with open(NewMemory_directory) as file:
        content2 = json.load(file)
        new_content2 = []
        for memorypiece in content2:
            experiences = memorypiece.get("experiences")
            gain_eliminated_experienceList = []

            if experiences != None:
                # print("origin:", len(experiences))
                for experience in experiences:
                    valueGain = experience.get("valueGain")
                    # print(valueGain)
                    if valueGain >= eliminate_threshold:
                        gain_eliminated_experienceList.append(experience)
                # print(len(experiences))
                memorypiece["experiences"] = gain_eliminated_experienceList
                new_content2.append(memorypiece)
            else:
                new_content2.append(memorypiece)
        file.close()

    with open(Evolved_directory, 'r') as file:
        new_content = json.load(file)

    new_content = new_content + new_content2

    with open(Evolved_directory, 'w') as file:
        json.dump(new_content, file)



def recount_experience(Evolved_directory):
    with open(Evolved_directory, 'r') as file:
        content = json.load(file)

    with open(Evolved_directory, 'w') as file:
        i = 0
        for memorypiece in content:
            memorypiece["total"] = i
            i += 1
        json.dump(content, file)

def main():
    parser = argparse.ArgumentParser(description="Process memory with some directories.")
    parser.add_argument("Path_directory", type = str, help="The directory of software")
    parser.add_argument("UsedMemory_directory", type=str, help="The directory of MemoryCards")
    parser.add_argument("NewMemory_directory", type=str, help="The directory of NewMemoryCards")
    parser.add_argument("Evolved_directory", type= str, help="The directory for output")


    args = parser.parse_args()
    retrieve_eliminate(args.Path_directory,args.UsedMemory_directory,args.Evolved_directory)
    gain_eliminate(args.NewMemory_directory,args.Evolved_directory)
    recount_experience(args.Evolved_directory)

if __name__ == "__main__":
    main()
