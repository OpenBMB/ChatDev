# Communicative Agents for Software Development with Local LLM

## Overview from ChatDev
- **ChatDev** stands as a **virtual software company** that operates through various **intelligent agents** holding
  different roles, including Chief Executive Officer <img src='online_log/static/figures/ceo.png' height=20>, Chief Product Officer <img src='online_log/static/figures/cpo.png' height=20>, Chief Technology Officer <img src='online_log/static/figures/cto.png' height=20>, programmer <img src='online_log/static/figures/programmer.png' height=20>, reviewer <img src='online_log/static/figures/reviewer.png' height=20>, tester <img src='online_log/static/figures/tester.png' height=20>, art designer <img src='online_log/static/figures/designer.png' height=20>. These
  agents form a multi-agent organizational structure and are united by a mission to "revolutionize the digital world
  through programming." The agents within ChatDev **collaborate** by participating in specialized functional seminars,
  including tasks such as designing, coding, testing, and documenting.
- The primary objective of ChatDev is to offer an **easy-to-use**, **highly customizable** and **extendable** framework,
  which is based on large language models (LLMs) and serves as an ideal scenario for studying collective intelligence.

## Overview from Simulation
- The main goal of the Simulation is to provide the **ChatDev** framework with a local Large Language Model (LLM), thereby unlocking numerous possibilities.


## Quickstart

### Quickstart with terminal

To get started, follow these steps:

1. **Clone the GitHub Repository:** Begin by cloning the repository using the command:
   ```
   git clone https://github.com/sumedhrasal/simulation.git
   ```
2. **Set Up Python Environment:** Ensure you have a version 3.9 or higher Python environment. You can create and
   activate this environment using the following commands, replacing `sim_env` with your preferred environment
   name:
   ```
   conda create -n sim_env python=3.9 -y
   conda activate sim_env
   ```
3. **Install Dependencies:** Move into the `simulation` directory and install the necessary dependencies by running:
   ```
   cd simulation
   pip install -r requirements.txt
   ```
4. **Set Local LLM:** You are free to use any local Large Language Model (LLM) that supports OpenAI's endpoints. For my experiments, I utilized FastChat. You can find the installation steps at this link: https://github.com/lm-sys/FastChat. Please note to use a new conda environment for installing FastChat, as there might be conflicting dependencies.

5. **Run Local LLM:** You will need to run three commands to start your FastChat LLM.

  ```python
  python -m fastchat.serve.controller
  python -m fastchat.serve.model_worker --model-path vicuna-7b-v1.5 # assuming you have downloaded the vicuna weight file.
  python -m fastchat.serve.openai_api_server
  ```

6. **Build Your Software:** Use the following command to initiate the building of your software,
   replacing `[description_of_your_idea]` with your idea's description and `[project_name]` with your desired project
   name:
   On Unix/Linux:
   ```
   python run.py --task "[description_of_your_idea]" --name "[project_name]"
   ```
   On Windows:
   ```
   python run.py --task "[description_of_your_idea]" --name "[project_name]"
   ```

7. **Run Your Software:** Once generated, you can find your software in the `WareHouse` directory under a specific
   project folder, such as `project_name_DefaultOrganization_timestamp`. Run your software using the following command
   within that directory:
   On Unix/Linux:
   ```
   cd WareHouse/project_name_DefaultOrganization_timestamp
   python3 main.py
   ```
   On Windows:
   ```
   cd WareHouse/project_name_DefaultOrganization_timestamp
   python main.py
   ```

## 🔎 Citation

```
@misc{qian2023communicative,
      title={Communicative Agents for Software Development}, 
      author={Chen Qian and Xin Cong and Wei Liu and Cheng Yang and Weize Chen and Yusheng Su and Yufan Dang and Jiahao Li and Juyuan Xu and Dahai Li and Zhiyuan Liu and Maosong Sun},
      year={2023},
      eprint={2307.07924},
      archivePrefix={arXiv},
      primaryClass={cs.SE}
}
```
