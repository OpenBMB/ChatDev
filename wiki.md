# Wiki

## Quick Start Step By Step

### 1. Install `ChatDev`:

- Visit the [quickstart section](README.md#%EF%B8%8F-quickstart) of readme for installation instructions.

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
      --config CONFIG  Name of config, which is used to load configuration under CompanyConfig/; Please see CompanyConfig Section below
      --org ORG        Name of organization, your software will be generated in WareHouse/name_org_timestamp
      --task TASK      Prompt of your idea
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

- you can start a flask app first to get a local demo, including enhanced visualized logs, replay demo, and a simple
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

## Docker Start
- You can use docker for a quick and safe use of ChatDev. You will need some extra steps to allow executing GUI program in docker since ChatDev often create software with GUI and execute them in the Test Phase.

### Install Docker
- Please refer to the [Docker Official Website](https://www.docker.com/get-started/) for installing Docker.

### Prepare GUI connection between Host and Docker
- Take macOS for example,
  - install socat and xquartz, you may need to restart the computer after installing the xquartz
  ```commandline
  brew install socat xquartz
  ```
  - open xquartz and go into the settings, allow connections from network clients
    - ![xquartz](misc/xquartz.jpg)
  - run following command on the host computer and keep it.
  ```commandline
   socat TCP-LISTEN:6000,reuseaddr,fork UNIX-CLIENT:\"$DISPLAY\"
  ```
  - run following command on the host computer to check your ip (the address of inet).
  ```commandline
  ifconfig en0
  ```

### Build Docker images
- under the ChatDev folder, run
    ```commandline
    docker build -t chatdev:latest .
    ```
  it will generate a 400MB+ docker image named chatdev.

### Run Docker
- run following command to create and go into a container
    ```commandline
    docker run -it -p 8000:8000 -e OPENAI_API_KEY=YOUR_OPENAI_KEY -e DISPLAY=YOUR_IP:0 chatdev:latest
    ```
  ⚠️ You need to replace ``YOUR_OPENAI_KEY`` with your key and replace ``YOUR_IP`` with your inet address.
- Then you can just play with ChatDev running ``python3 run.py``.
- You can run ``python3 online_log/app.py &`` first to start a background program so that you can use online log with a WebUI.

### Copy the generated software out of Docker
- run 
    ```commandline
    docker cp container_id:/path/in/container /path/on/host
    ```
### Official Docker Image
- in preparation

## Customization

- You can customize your company in three kinds of granularity:
    - Customize ChatChain
    - Customize Phase
    - Customize Role
- Here is the overview architecture of ChatDev, which illustrates the relationships among the above three classes:

![arch](misc/arch.png)

- All the configuration content related to ChatDev (such as the background prompt of the agent employee, the work content of each Phase, and how the Phase is combined into a ChatChain), are called a **CompanyConfig** (because ChatDev is like a virtual software company). These CompanyConfigs are in the ChatDev project Under ``CompanyConfig/``. You can check this [directory](https://github.com/OpenBMB/ChatDev/tree/main/CompanyConfig). In this directory, you will see different CompanyConfig (such as Default, Art, Human). Generally speaking, each CompanyConfig will contain 3 configuration files.
  1. ChatChainConfig.json, which controls the overall development process of ChatDev, including which Phase each step is, how many times each Phase needs to be cycled, whether reflect is needed, etc.
  2. PhaseConfig.json, which controls each Phase, and corresponds to ``chatdev/phase.py`` or ``chatdev/composed_phase.py`` in the ChatDev project. The Python file realizes the specific working logic of each phase. The json file here contains the configuration of each phase, such as background prompt, which employees are participating in the phase, etc.
  3. RoleConfig.json contains the configuration of each employee (agent). Currently, it only contains the background prompt of each employee, which is a bunch of text containing placeholders.
- If a CompanyConfig does not contain all three configuration files (such as Art and Human), it means that the configuration files missing from this CompanyConfig are set according to Default. The official CompanyConfigs currently provided include:
  1. Default, default configuration
  2. Art, allows ChatDev to create image files according to needs, automatically generate image description prompts and call the openai Wenshengtu API to generate images
  3. Human, allowing human users to participate in ChatDev’s code review process

### Customize ChatChain

- see ``CompanyConfig/Default/ChatChainConfig.json``
- You can easily pick and organize phases to formulate a ChatChain from all phases (from ``chatdev/phase.py``
  or ``chatdev/composed_phase.py``)
  by modifying the json file

### Customize Phase

- This is the only part that needs to modify the code, and it brings much flexibility for customization.
- you just need to
    - implement your phase class (in the simplest case, only one functions need to be modified) extending the ``Phase``
      class
    - config this phase in ``PhaseConfig.json``, including writing phase prompt and assigning roles for this phase
- Customize SimplePhase
    - see ``CompanyConfig/Default/PhaseConfig.json`` for configuration, see ``chatdev/phase.py`` for implementing your
      own phase
    - each phase contains three steps:
        - generate phase environment from the whole chatchain environment
        - use phase environment to control the phase prompt and execute the chatting between roles in this phase (which
          usually does not need to be modified)
        - get a seminar conclusion from the chatting, and use it to update the whole chatchain environment
    - below is a simple example phase on choosing the programming language of the software:
        - generate phase environment: we pick task, modality and ideas from the chatchain environment
        - execute the phase: no need to implement, which is defined in the Phase class
        - update chatchain environment: we get seminar conclusion (which language) and update the 'language' key in the
          chatchain environment
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
        - see ``CompanyConfig/Default/ChatChainConfig.json`` for configuration and see ``chatdev/composed_phase.py`` for
          implementation.
        - **⚠️ Attention** We do not support Nested Composition yet so do not put ComposePhase in ComposePhase.
        - ComposePhase contains multiple SimplePhase, and can be conducted in loop.
        - ComposePhase has no Phase json but in the chatchain json file you can define which SimplePhase is in this
          ComposePhase, such as:
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
          chat_env update (the same as SimplePhase, but for the whole ComposePhase) and the condition for stopping the
          loop (optional):
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
- **⚠️ Attention** You need to keep at least "Chief Executive Officer" and "Counselor" in your own ``RoleConfig.json``
  to make Reflection work.

## ChatChain Parameters

- *clear_structure*: clean cache folders.
- *brainstorming*: TBD
- *gui_design*: whether create gui for software.
- *git_management*: open git management on software project or not.
- *self_improve*: flag for self-improvement on user input prompt. It is a special chatting that LLM plays as a prompt
  engineer to improve the user input prompt. **⚠️ Attention** Model generated prompts contains uncertainty and there may
  be a deviation from the requirement meaning contained in the original prompt.
- params in SimplePhase:
    - *max_turn_step*: Max number of chatting turn. You can increase max_turn_step for better performance but it will
      take longer time to finish the phase.
    - *need_reflect*: Flag for reflection. Reflection is a special phase that automatically executes after a phase. It
      will start a chatting between counselor and CEO to refine the conclusion of phase chatting.
- params in ComposedPhase
    - *cycleNum*: Number of cycles to execute SimplePhase in this ComposedPhase.

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

## CompanyConfig

### Default
![demo](misc/ChatChain_Visualization_Default.png)
- As shown in the ChatChain visualization of Default setting, ChatDev will produce a software in the order of:
  - Demand Analysis: decide the modality of the software
  - Language Choose: decide the programming language
  - Coding: write the code
  - CodeCompleteAll: complete the missing function/class
  - CodeReview: review and modify the code
  - Test: run the software and modify the code based on the test report
  - EnvironmentDoc: write the environment doc
  - Manual: write the manual
- You can use default setting using ``python3 run.py --config "Default"``.

### Art
![demo](misc/ChatChain_Visualization_Art.png)
- Compared to Default, Art setting add a phase before CodeCompleteAll called Art
- The Art phase will first discuss the name and description of the images assets, then use ``openai.Image.create`` to generate the images based on description.
- You can use default setting using ``python3 run.py --config "Art"`` or just ignore the config parameter.

### Human-Agent Interaction
![demo](misc/ChatChain_Visualization_Human.png)
- Compared to Default, in ***Human-Agent-Interaction*** mode you can play as reviewer and asks programmer agent to modify the code based on your comments.
- It adds a Phase called HumanAgentInteraction after the  dCodeReview Phase.
- You can use ***Human-Agent-Interaction*** setting using ``python3 run.py --config "Human"``.
- When chatdev executes to this Phase, on the command interface you will see a hint that ask for input.
- You can run your software in the ``WareHouse/`` and see if it satisfies your need. Then you can type anything you want (bug fix or new feature) in the command interface, then press Enter:
![Human_command](misc/Human_command.png)
- For example
  - We first run the ChatDev with task "design a gomoku game"
  - Then we type "Please add a restart button" in the HumanAgentInteraction Phase, adding the first feature
  - In the second loop of HumanAgentInteraction, we add another feature by typing "Please add a current status bar showing whose turn it is".
  - At last, we early exit this mode by typing "End".
  - Below shows all three versions.
    - <img src='misc/Human_v1.png' height=250>&nbsp;&nbsp;&nbsp;&nbsp;<img src='misc/Human_v2.png' height=250>&nbsp;&nbsp;&nbsp;&nbsp;<img src='misc/Human_v3.png' height=250>

### Git Mode
- Simply set ``"git_management"`` to ``"True"`` in ``ChatChainConfig.json`` enables the Git Mode, in which ChatDev will make the generated software folder a git repository and automatically make all commits.
- Every change made on the code of generated software will create a commit, including:
  - The initial commit, created after the ``Coding`` phase completed, with a commit message ``Finish Coding``.
  - Complete ``ArtIntegration`` phase, with a commit message ``Finish Art Integration``.
  - Complete ``CodeComplete`` phase, with a commit message ``Code Complete #1/2/3 Finished``(if the CodeComplete is executed in three loops).
  - Complete ``CodeReviewModification`` phase, with a commit message ``Review #1/2/3 Finished``(if the CodeReviewModification is executed in three loops).
  - Complete ``CodeReviewHuman`` phase, with a commit message ``Human Review #1/2/3 Finished``(if the CodeReviewHuman is executed in three loops).
  - Complete ``TestModification`` phase, with a commit message ``Test #1/2/3 Finished``(if the TestModification is executed in three loops).
  - All phases completed, with a commit message ``Final Version``.
- On the terminal and online log UI you can see the git summary at the end of process.
  -  <img src='misc/git_summary_terminal.png' height=250>&nbsp;&nbsp;&nbsp;&nbsp;<img src='misc/git_summary_onlinelog.png' height=250>
  - You can also search ``git Information`` in the log file to see when did commit happen.
- ⚠️ There are a few things worth noting about Git Mode:
  - ChatDev is a git project, and we need to create another git project in the generated software folder, so we use ``git submodule`` to make this "git over git" function. A ``.gitmodule`` file will be created.
    - under the software folder, you can add/commit/push/checkout the software project just like a normal git project, and your commits would not modify the ChatDev git history.
    - under the ChatDev folder, the new software has been added to the ChatDev as a whole folder.
  - The generated log file would not be added into the software git project, since the log is closed and moved to the software folder after the final commit. We have to do this because the log should record all the git commits, including the final one. So the git operations must be done before the log finalized. You will always see a log file to be added and committed in the software folder, like:
    - ![img.png](misc/the_log_left.png)
  - When you perform ``git add .`` under the ChatDev project, There will be information like (taking Gomoku for example):
    ```commandline
    Changes to be committed:
        (use "git restore --staged <file>..." to unstage)
            new file:   .gitmodules
            new file:   WareHouse/Gomoku_GitMode_20231025184031

    Changes not staged for commit:
        (use "git add <file>..." to update what will be committed)
        (use "git restore <file>..." to discard changes in working directory)
        (commit or discard the untracked or modified content in submodules)
            modified:   WareHouse/Gomoku_GitMode_20231025184031 (untracked content)
    ```
    If you add and commit the software log file under the software folder, there will be no ``Changes not staged for commit:``
  - Some phase executions may not change the code, and thereby there is no commit. For example, the software is tested without problems and there is no modification, so the test phase would leave no commit.
  
