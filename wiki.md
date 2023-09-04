# Wiki

## Quick Start Step By Step

### 1. Install `ChatDev`:

- **Clone the GitHub Repository:** Begin by cloning the repository using the command:
   ```
   git clone https://github.com/OpenBMB/ChatDev.git
   ```
- **Set Up Python Environment:** Ensure you have a Python environment of version 3.9 or higher. You can create and
  activate this environment using the following commands, replacing `ChatDev_conda_env` with your preferred environment
  name:
   ```
   conda create -n ChatDev_conda_env python=3.9 -y
   conda activate ChatDev_conda_env
   ```
- **Install Dependencies:** Move into the `ChatDev` directory and install the necessary dependencies by running:
   ```
   cd ChatDev
   pip3 install -r requirements.txt
   ```
- **Set OpenAI API Key:** Export your OpenAI API key as an environment variable. Replace `"your_OpenAI_API_key"` with
  your actual API key. Remember that this environment variable is session-specific, so you'll need to set it again if
  you open a new terminal session.
  On Unix/Linux:
   ```
   export OPENAI_API_KEY="your_OpenAI_API_key"
   ```
  On Windows:
   ```
   $env:OPENAI_API_KEY="your_OpenAI_API_key"
   ```

### 2. Start building software in one command:

- **Build Your Software:** Use the following command to initiate the building of your software,
  replacing `[description_of_your_idea]` with your idea's description and `[project_name]` with your desired project
  name:
   ```
   python3 run.py --task "[description_of_your_idea]" --name "[project_name]"
   ```

- here is the full params of run.py

    ```commandline
    usage: run.py [-h] [--config CONFIG] [--org ORG] [--task TASK] [--name NAME] [--model MODEL]
    
    argparse
    
    optional arguments:
      -h, --help       show this help message and exit
      --config CONFIG  Name of config, which is used to load configuration under CompanyConfig/
      --org ORG        Name of organization, your software will be generated in WareHouse/name_org_timestamp
      --task TASK      Prompt of software
      --name NAME      Name of software, your software will be generated in WareHouse/name_org_timestamp
      --model MODEL    GPT Model, choose from {'GPT_3_5_TURBO','GPT_4','GPT_4_32K'}
    ```

### 3. Check your software

- the generated software is under ``WareHouse/NAME_ORG_timestamp``, including:
    - all the files and manuals of this software
    - config files of company which made this software, including three config json files
    - full log of the software building process
    - prompt to make this software
- A case of todo software is just like below, which is located in ``/WareHouse/todo_THUNLP_20230822165503``
    ```
    .
    ├── 20230822165503.log # log file
    ├── ChatChainConfig.json # Configuration
    ├── PhaseConfig.json # Configuration
    ├── RoleConfig.json # Configuration
    ├── todo.prompt # User query prompt
    ├── meta.txt # Software building meta information
    ├── main.py # Generated Software Files
    ├── manual.md # Generated Software Files
    ├── todo_app.py # Generated Software Files
    ├── task.py # Generated Software Files
    └── requirements.txt # Generated Software Files
    ```
- Usually you just need to install requirements and run main.py to use your software
    ```commandline
    cd WareHouse/project_name_DefaultOrganization_timestamp
    pip3 install -r requirements.txt
    python3 main.py
    ```

## Local Demo

- you can start a flask app fist get a local demo, including enhanced visualized logs, replay demo, and a simple
  ChatChain Visualizer.

```
python3 online_log/app.py
```

then go to [Local Demo Website](http://127.0.0.1:8000/) to see an online visualized version of logs such as

![demo](misc/demo.png)

- You can also goto the [ChatChain Visualizer](http://127.0.0.1:8000/static/chain_visualizer.html) on this page and
  upload any ``ChatChainConfig.json`` under ``CompanyConfig/`` to get a visualization on this chain, such as:

![ChatChain Visualizer](misc/chatchain_vis.png)

- You can also goto the Chat Replay page to replay log file in the software folder
    - click the ``File Upload`` bottom to upload a log, then click ``Replay``
    - The replay only shows the dialogues in natural languages between agents, it will not contain debug logs.

![Replay](misc/replay.gif)

## Customization

- You can customize your company in three kinds of granularity:
    - Customize ChatChain
    - Customize Phase
    - Customize Role
- Here is the overview architecture of ChatDev, which illustrates the relationships among above three classes:

![arch](misc/arch.png)

### Customize ChatChain

- see ``CompanyConfig/Default/ChatChainConfig.json``
- You can easily pick and organize phases to formulate a ChatChain from all phases (from ``chatdev/phase.py`` or ``chatdev/composed_phase.py``)
  by modifying the json file

### Customize Phase

- This is the only part that needs to modify the code, and it brings much flexibility for customization.
- you just need to
    - implement your phase class (in the simplest case, only one functions need to be modified) extending the ``Phase`` class
    - config this phase in ``PhaseConfig.json``, including writing phase prompt and assigning roles for this phase
- Customize SimplePhase
    - see ``CompanyConfig/Default/PhaseConfig.json`` for configuration, see ``chatdev/phase.py`` for implementing your own phase
    - each phase contains three steps:
        - generate phase environment from the whole chatchain environment
        - use phase environment to control the phase prompt and execute the chatting between roles in this phase (which usually does not need to be modified)
        - get a seminar conclusion from the chatting, and use it to update the whole chatchain environment
    - below is a simple example phase on choosing the programming language of the software:
        - generate phase environment: we pick task, modality and ideas from the chatchain environment
        - execute the phase: no need to implement, which is defined in the Phase class
        - update chatchain environment: we get seminar conclusion (which language) and update the 'language' key in the chatchain environment
          ```python
          class LanguageChoose(Phase):
              def __init__(self, **kwargs):
                  super().__init__(**kwargs)

              def update_phase_env(self, chat_env):
                  self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                                         "modality": chat_env.env_dict['modality'],
                                         "ideas": chat_env.env_dict['ideas']})

              def update_chat_env(self, chat_env) -> ChatEnv:
                  if len(self.seminar_conclusion) > 0 and "<INFO>" in self.seminar_conclusion:
                      chat_env.env_dict['language'] = self.seminar_conclusion.split("<INFO>")[-1].lower().replace(".", "").strip()
                  elif len(self.seminar_conclusion) > 0:
                      chat_env.env_dict['language'] = self.seminar_conclusion
                  else:
                      chat_env.env_dict['language'] = "Python"
                  return chat_env
          ```
          The configuration of this phase is like:
          ```json
          "LanguageChoose": {
            "assistant_role_name": "Chief Technology Officer",
            "user_role_name": "Chief Executive Officer",
            "phase_prompt": [
              "According to the new user's task and some creative brainstorm ideas listed below: ",
              "Task: \"{task}\".",
              "Modality: \"{modality}\".",
              "Ideas: \"{ideas}\".",
              "We have decided to complete the task through an executable software implemented via a programming language. ",
              "As the {assistant_role}, to satisfy the new user's demand and make the software realizable, you should propose a concrete programming language. If python can complete this task via Python, please answer Python; otherwise, answer another programming language (e.g., Java, C++, etc,).",
              "Note that we must ONLY discuss the target programming language and do not discuss anything else! Once we all have expressed our opinion(s) and agree with the results of the discussion unanimously, any of us must actively terminate the discussion and conclude the best programming language we have discussed without any other words or reasons, using the format: \"<INFO> *\" where \"*\" represents a programming language."
            ]
          }
          ```
    - Customize ComposePhase
        - see ``CompanyConfig/Default/ChatChainConfig.json`` for configuration and see ``chatdev/composed_phase.py`` for implementation.
        - **⚠️ Attention** We do not support Nested Composition yet so do not put ComposePhase in ComposePhase.
        - ComposePhase contains multiple SimplePhase, and can be conducted in loop.
        - ComposePhase has no Phase json but in the chatchain json file you can define which SimplePhase is in this ComposePhase, such as:
      ```json
        {
          "phase": "CodeReview",
          "phaseType": "ComposedPhase",
          "cycleNum": 2,
          "Composition": [
            {
              "phase": "CodeReviewComment",
              "phaseType": "SimplePhase",
              "max_turn_step": -1,
              "need_reflect": "False"
            },
            {
              "phase": "CodeReviewModification",
              "phaseType": "SimplePhase",
              "max_turn_step": -1,
              "need_reflect": "False"
            }
          ]
        }
      ```
        - You also need to implement your own ComposePhase class, which you need to decide the phase_env update and
          chat_env update (the same as SimplePhase, but for the whole ComposePhase) and the condition for stopping the loop (optional):
      ```python
      class Test(ComposedPhase):
          def __init__(self, **kwargs):
              super().__init__(**kwargs)

          def update_phase_env(self, chat_env):
              self.phase_env = dict()

          def update_chat_env(self, chat_env):
              return chat_env

          def break_cycle(self, phase_env) -> bool:
              if not phase_env['exist_bugs_flag']:
                  log_and_print_online(f"**[Test Info]**\n\nAI User (Software Test Engineer):\nTest Pass!\n")
                  return True
              else:
                  return False
      ```

### Customize Role

- see ``CompanyConfig/Default/RoleConfig.json``
- you can use placeholders for using phase environment, which is the same as PhaseConfig.json
- **⚠️ Attention** You need to keep at least "Chief Executive Officer" and "Counselor" in your own ``RoleConfig.json`` to make Reflection work.

## ChatChain params

- clear_structure: clean cache folders.
- brainstorming: TBD
- gui_design: whether create gui for software.
- git_management: open git management on software project or not.
- self_improve: flag for self-improvement on user input prompt. It is a special chatting that LLM plays as a prompt
  engineer to improve the user input prompt. **⚠️ Attention** Model generated prompts contains uncertainty and there may
  be a deviation from the requirement meaning contained in the original prompt.
- params in SimplePhase:
    - max_turn_step: Max number of chatting turn. You can increase max_turn_step for better performance but it will take longer time to finish the phase.
    - need_reflect: Flag for reflection. Reflection is a special phase that automatically executes after a phase. It
      will start a chatting between counselor and CEO to refine the conclusion of phase chatting.
- params in ComposedPhase
    - cycleNum: Number of cycles to execute SimplePhase in this ComposedPhase.

## Project Structure

```commandline
├── CompanyConfig # Configuration Files for ChatDev, including ChatChain, Phase and Role config json.
├── WareHouse # Folder for generated software
├── camel # Camel RolePlay component
├── chatdev # ChatDev core code
├── misc # assets of example and demo
├── online_log # Demo Folder
├── run.py # Entry of ChatDev
├── requirements.txt
├── README.md
└── wiki.md
```
