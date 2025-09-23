import subprocess
import time
import torch
import numpy as np
import re
import os
import signal
import math

from model import query_gpt
from model.embedding import OpenAIEmbedding
from utils.file_utils import read_code, read_text

FLOAT_TOLERANCE = 1e-3
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        

class BenchmarkEvaluator:
    @staticmethod
    def commongen_coverage(concepts, text_path):
        generated_text = read_text(text_path)
        generated_text = generated_text.lower()
        concepts = [concept.lower() for concept in concepts]
        missing_concepts = [concept for concept in concepts if not re.search(rf'\b{re.escape(concept)}\b', generated_text, re.IGNORECASE)]
        if missing_concepts:
            return 1 - len(missing_concepts)/len(concepts)
        return 1

    @staticmethod
    def commongen_gpt_score(concepts, text_path):
        generated_text = read_text(text_path)
        prompt = '''
        As a strict StoryMaster, your task is to meticulously evaluate the quality of stories across three primary dimensions: Grammar and Fluency, Context Relevance, and Logic Consistency. Each dimension will be rated on a refined scale from 1 (average) to 4 (perfect), ensuring that only stories of superior quality achieve the highest scores.

        Implement Your Evaluation Mechanism with Enhanced Rigor:

        Grammar and Fluency (Assess the story's linguistic precision and narrative flow):
        Score 1 (solid): The story is free of grammatical errors, but the narrative lacks the stylistic variety and eloquence that elevate writing to a higher tier.
        Score 2 (proficient): The narrative demonstrates a strong command of grammar and a coherent flow, yet it does not showcase the level of linguistic artistry found in superior works.
        Score 3 (excellent): The story exhibits a refined sense of grammar and a compelling narrative flow, with sentence structures that are engaging and demonstrate a high level of craft.
        Score 4 (masterful): The story is a testament to linguistic excellence, with sentence structures that are not only clear and elegant but also exhibit a creative and sophisticated use of language that captivates and inspires.

        Context Relevance (Examine the coherence, interconnectedness, and depth of content within the story):
        Score 1 (solid): The story establishes a basic framework of context relevance, but it does not delve into the intricacies of character and thematic development that enrich the narrative.
        Score 2 (proficient): The narrative demonstrates a clear connection between elements, yet it lacks the depth and multi-layered content that would distinguish it as truly exceptional.
        Score 3 (excellent): The story interweaves elements with a high degree of relevance, creating a narrative that is coherent and features content that is well-developed and insightful.
        Score 4 (masterful): The story achieves an extraordinary level of context relevance, with every element artfully woven into a narrative that is not only coherent but also profound in its exploration of themes and characters, offering a rich and immersive experience.

        Logic Consistency (Scrutinize the narrative for logical integrity and internal consistency):
        Score 1 (solid): The story maintains a logical structure, but there may be occasional lapses in plausibility or minor inconsistencies that slightly undermine its credibility.
        Score 2 (proficient): The narrative is generally logical, with a clear progression of events and character actions, yet it does not reach the level of seamless consistency expected of a superior story.
        Score 3 (excellent): The story exhibits a strong logical consistency, with events and character actions that are well-aligned and plausible, contributing to a coherent and believable plot.
        Score 4 (masterful): The story is characterized by impeccable logical consistency, with every event and character action meticulously aligned to create a plot that is not only coherent but also demonstrates a deep understanding of causality and human behavior.'''

        prompt += '\nStory:\n' + generated_text
        response_text, _ = query_gpt(prompt)
        pattern = r'\d+'
        remedy_prompt = 'Extract the score in each dimension in format: (Grammar and Fluency Score: X. Context Relevance Score: X. Logic Consistency Score: X. Overall Score Score: X.) of the following content.'
        remedy_prompt += response_text
        remedy_respond,_ = query_gpt(remedy_prompt)
        score_list = re.findall(pattern, remedy_respond)
        my_float_list = [float(item) for item in score_list]
        score_list = [item/4 for item in my_float_list]
        score_list = score_list[:3]
        while len(score_list) != 3:
            score_list.append(0)
        return score_list

    @staticmethod
    def check_commongen(concepts, text_path):
        # Metric implementation inspired by self-refine project:
        # https://github.com/madaan/self-refine/tree/main/src/commongen
        coverage = BenchmarkEvaluator.commongen_coverage(concepts, text_path)
        coverage = torch.tensor(coverage, dtype=torch.float32, device=DEVICE)  
        scores = BenchmarkEvaluator.commongen_gpt_score(concepts, text_path)
        grammar = torch.tensor(scores[0], dtype=torch.float32, device=DEVICE)  
        relevance = torch.tensor(scores[1], dtype=torch.float32, device=DEVICE)  
        consistency = torch.tensor(scores[2], dtype=torch.float32, device=DEVICE)  
        metrics = {"grammar": grammar, "relevance": relevance, "consistency": consistency, "coverage": coverage}
        mean_score = torch.tensor(sum(scores) / 3, dtype=torch.float32, device=DEVICE)    
        if coverage == 0:
            return -1.0, metrics
        else:
            return coverage*mean_score, metrics
        
    
    @staticmethod
    def check_srdd(code_path, text):
        # Metric implementation inspired by ChatDev project:
        # https://github.com/OpenBMB/ChatDev
        path = code_path
        code = read_code(path)
        consistency = BenchmarkEvaluator.srdd_consistency(text, code)
        completeness = BenchmarkEvaluator.srdd_completeness(code)
        executability, _ = BenchmarkEvaluator.srdd_executability(path)
        executability = 1 if executability else 0
        executability = torch.tensor(executability, dtype=torch.float32, device=DEVICE)  
        consistency = torch.tensor(consistency, dtype=torch.float32, device=DEVICE)  
        completeness = torch.tensor(completeness, dtype=torch.float32, device=DEVICE)  
        metrics = {"consistency": consistency, "completeness": completeness, "executability": executability}
        if executability:
            alignment = consistency * completeness
            return alignment, metrics
        else:
            return -1.0, metrics
    
    @staticmethod
    def srdd_consistency(text, code):
        code = BenchmarkEvaluator.remove_comments(code)
        text = re.sub(r'^[^\n]*\n', '', text)
        text_embedding = OpenAIEmbedding.get_embedding(text)
        code_embedding = OpenAIEmbedding.get_embedding(code)
        similarity = BenchmarkEvaluator.get_cosine_similarity(text_embedding, code_embedding)
        return similarity

    @staticmethod
    def srdd_completeness(code):
        lines = code.split("\n")
        lines = [line for line in lines if
                "password" not in line.lower() and "passenger" not in line.lower() and "passed" not in line.lower() and "passes" not in line.lower()]
        lines = [line for line in lines if "pass" in line.lower() or "todo" in line.lower()]
        if len(lines) > 0:
            return 0.0
        return 1.0

    @staticmethod 
    def srdd_executability(work_path):
        def robust_kill(process):
            """Robustly kill the process based on the OS."""
            if process.poll() is None:  # Check if the process is still running
                if os.name == 'nt':  # For Windows
                    os.kill(process.pid, signal.SIGTERM)
                    time.sleep(1)  
                    if process.poll() is None:  
                        os.kill(process.pid, signal.CTRL_BREAK_EVENT)
                else:  # For Linux/macOS
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)  
                    time.sleep(1)  
                    if process.poll() is None:  
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        try:
            if not os.path.exists(work_path):
                return False, "The file path does not exist."
            if os.name == 'nt':  
                command = f" python {work_path}"
                process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
            else:  
                command = f"python3 {work_path}"
                process = subprocess.Popen(command, shell=True, preexec_fn=os.setsid, stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE)

            try:
                out, err = process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                robust_kill(process)
                return True, "The process completes without encountering any errors."

            return_code = process.returncode
            output = out.decode('utf-8', errors='ignore')
            error_output = err.decode('utf-8', errors='ignore')

            # If the process is still running after the timeout
            if process.poll() is None:
                robust_kill(process)  
            return_code = process.returncode

            # Handle return code and output
            if return_code == 0:
                # Clean up file paths in the output for readability
                work_path = os.getcwd()
                output = output.replace(work_path, "")
                return True, output
            else:
                # Handle errors in the output
                if error_output:
                    work_path = os.getcwd()
                    if "Traceback".lower() in error_output.lower():
                        errs = error_output.replace(work_path + "/", "").replace(work_path, "")
                        return False, errs
                return False, error_output

        except subprocess.CalledProcessError as e:
            return False, f"CalledProcessError: {str(e)}"
        except Exception as ex:
            return False, f"An unexpected error occurred: {str(ex)}"


    @staticmethod
    def get_cosine_similarity(embeddingi, embeddingj):
        embeddingi = np.array(embeddingi)
        embeddingj = np.array(embeddingj).T
        cos_sim = embeddingi.dot(embeddingj) / (np.linalg.norm(embeddingi) * np.linalg.norm(embeddingj))
        return cos_sim
    
    @staticmethod
    def remove_comments(string):
        def remove_comments_by_regex(string, regex):
            lines = string.split("\n")
            lines = [line for line in lines if not line.strip().startswith("#")]
            string = "\n".join(lines)
            comments = []
            matches = re.finditer(regex, string, re.DOTALL)
            for match in matches:
                group1 = match.group(1)
                comments.append(group1)
            for comment in comments + ["''''''\n"]:
                string = string.replace(comment, "")
            return string

        string = remove_comments_by_regex(string, r"'''(.*?)'''")
        string = remove_comments_by_regex(string, r"\"\"\"(.*?)\"\"\"")
        return string

    
    @staticmethod
    def check_mmlu(final_ans, true_ans):
        if final_ans is None or true_ans is None:
            return False
        if len(final_ans) == 0:
            return False
        pattern = r'answer is\s+([A-Z])'
        match = re.search(pattern, final_ans)
        if match:
            final = match.group(1).strip()
            if final==true_ans:
                return True
        
        pattern = r'is\s+([A-Z])'
        match = re.search(pattern, final_ans)
        if match:
            final = match.group(1).strip()
            if final==true_ans:
                return True

        final_ans = final_ans.strip().lower()
        true_ans = true_ans.strip().lower()
        if final_ans == true_ans:
            return True
        
        final_ans_lines = final_ans.split('\n')
        ans = []
        residual = []
        for li, al in enumerate(final_ans_lines):
            ans.append(al)
            if 'answer is' in al:
                break
        residual = list(final_ans_lines[li + 1:])
        ans = '\n'.join(ans)
        residual = '\n'.join(residual)
        
        pattern = 'the answer is ('
        pred = ans.split(pattern)
        
        if len(pred) > 1:
            pred = BenchmarkEvaluator.extract_letter(pred[1])
            gold = BenchmarkEvaluator.extract_letter(true_ans)
            return pred[0] == gold
        else:
            pred = BenchmarkEvaluator.extract_letter(ans)
            gold = BenchmarkEvaluator.extract_letter(true_ans)
            return pred == gold
    
    @staticmethod
    def check_gsm8k(final_ans, true_ans):
        if final_ans is None or true_ans is None:   
            return False
        if isinstance(final_ans, str):
            final_num = BenchmarkEvaluator.extract_number(final_ans)
            if final_num is None:
                return False
        else:
            final_num = float(final_ans)
        true_num = float(true_ans)
        
        if not (math.isfinite(final_num) and math.isfinite(true_num)):
            return False  

        # Accuracy computation adapted from: https://github.com/reasoning-machines/pal/blob/main/scripts/gsm_eval.py
        is_correct = abs(float(final_num) - float(true_num)) < FLOAT_TOLERANCE 
        if not is_correct:
            is_correct = (round(float(final_num)) == round(float(true_num)))
            if is_correct:
                 return is_correct
            if abs(int(float(final_num))) > 100 and abs(int(float(true_num))) > 100:
                is_correct = (int(float(final_num)) == int(float(true_num)))
        return is_correct
    
    @staticmethod
    def extract_math_answer(text):
        if text is None:
            return text
        if isinstance(text, str):
            final_num = BenchmarkEvaluator.extract_number(text)
        else:
            final_num = float(text)
        return final_num
    
    @staticmethod
    def extract_choice_answer(text):
        if text is None:
            return text
        # First pattern: 'answer is X' 
        pattern = r'answer is\s+([A-Z])'
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
        
        # Second pattern: 'is X'
        pattern = r'is\s+([A-Z])'
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
        
        # Third pattern: '(X)' or 'The answer is (X)'
        pattern = r'\(([A-Z])\)'
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
        
        # Fourth pattern: 'X'
        if len(text) == 1:
            pattern = r'[A-Z]'
            match = re.search(pattern, text)
            if match:
                return match.group(0).strip()

        return text.strip()
    
    @staticmethod
    def normalize_string(s):
        return ''.join(s.split()).lower()

    @staticmethod
    def extract_number(text):
        matches = re.findall(r'-?\d+\.\d+|-?\d+', text)
        return float(matches[0]) if matches else None

    @staticmethod
    def extract_ground_truth(text):
        return text.split('####')[-1].strip()
    
    @staticmethod
    def extract_letter(text):
            pattern = r'\((\w)\)'
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()  
            return text.strip()  