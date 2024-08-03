# Communicative Agents for Software Development

<p align="center">
  <img src='./misc/logo1.png' width=550>
</p>


<p align="center">
    【📚 <a href="wiki.md">Wiki</a> | 🚀 <a href="wiki.md#visualizer">Visualizer</a> | 👥 <a href="Contribution.md">Community Built Software</a> | 🔧 <a href="wiki.md#customization">Customization</a> | 👾 】

</p>

## 📖 Overview

- **WEB-AI-Startr.Team** stands as a **virtual software company** that operates through various **intelligent agents** holding
  different roles, including Chief Executive Officer <img src='visualizer/static/figures/ceo.png' height=20>, Chief Product Officer <img src='visualizer/static/figures/cpo.png' height=20>, Chief Technology Officer <img src='visualizer/static/figures/cto.png' height=20>, programmer <img src='visualizer/static/figures/programmer.png' height=20>, reviewer <img src='visualizer/static/figures/reviewer.png' height=20>, tester <img src='visualizer/static/figures/tester.png' height=20>, art designer <img src='visualizer/static/figures/designer.png' height=20>. 
  
  These
  agents form a multi-agent organizational structure and are united by a mission to "revolutionize the digital world
  through programming." The agents within Startr.Team **collaborate** by participating in specialized functional seminars,
  including tasks such as designing, coding, testing, and documenting.
- The primary objective of Startr.Team is to offer an **easy-to-use**, **highly customizable** and **extendable** framework,
  which is based on large language models (LLMs) and serves as an ideal scenario for studying collective intelligence.

<p align="center">
  <img src='./misc/company.png' width=600>
</p>

## 🎉 News

* June 12, 2024: We introduce Multi-Agent Collaboration Networks (MacNet) 🎉, which utilize directed acyclic graphs 
to facilitate effective task-oriented collaboration among agents through linguistic interactions 🤖🤖. MacNet supports 
cooperation across various topologies and among more than a thousand agents without exceeding context limits. More 
versatile and scalable, MacNet can be considered a more advanced version of WEB-AI-Startr.Team's chain-shaped topology. 
Our preprint paper is available at [https://arxiv.org/abs/2406.07155](https://arxiv.org/abs/2406.07155). This technique 
will soon be incorporated into this repository, enhancing support for diverse organizational structures and offering 
richer solutions beyond software development (e.g., logical reasoning, data analysis, story generation, and more).
  <p align="center">
  <img src='./misc/macnet.png' width=500>
  </p>

<details>
<summary>Old News</summary>

* May 07, 2024, we introduced "Iterative Experience Refinement" (IER), a novel method where instructor and assistant agents enhance shortcut-oriented experiences to efficiently adapt to new tasks. This approach encompasses experience acquisition, utilization, propagation, and elimination across a series of tasks. Our preprint paper is available at https://arxiv.org/abs/2405.04219, and this technique will soon be incorporated into WEB-AI-Startr.Team.
  <p align="center">
  <img src='./misc/ier.png' width=220>
  </p>

* January 25, 2024: We have integrated Experiential Co-Learning Module into WEB-AI-Startr.Team. Please see the [Experiential Co-Learning Guide](wiki.md#co-tracking).

* December 28, 2023: We present Experiential Co-Learning, an innovative approach where instructor and assistant agents accumulate shortcut-oriented experiences to effectively solve new tasks, reducing repetitive errors and enhancing efficiency.  Check out our preprint paper at https://arxiv.org/abs/2312.17025 and this technique will soon be integrated into WEB-AI-Startr.Team.
  <p align="center">
  <img src='./misc/ecl.png' width=860>
  </p>

* December 15, 2023: We have introduced the **Experiential Co-Learning Module** into WEB-AI-Startr.Team. Please see the [Experiential Co-Learning Guide](wiki.md#co-tracking).

* November 2, 2023: Startr.Team is now supported with a new feature: incremental development, which allows agents to develop upon existing codes. Try `--config "incremental" --path "[source_code_directory_path]"` to start it.
  <p align="center">
  <img src='./misc/increment.png' width=700>
  </p>

* October 26, 2023: Startr.Team is now supported with Docker for safe execution (thanks to contribution from [ManindraDeMel](https://github.com/ManindraDeMel)). Please see [Docker Start Guide](wiki.md#docker-start).
  <p align="center">
  <img src='./misc/docker.png' width=400>
  </p>
* September 25, 2023: The **Git** mode is now available, enabling the programmer <img src='visualizer/static/figures/programmer.png' height=20> to utilize Git for version control. To enable this feature, simply set ``"git_management"`` to ``"True"`` in ``ChatChainConfig.json``. See [guide](wiki.md#git-mode).
  <p align="center">
  <img src='./misc/github.png' width=600>
  </p>
- September 20, 2023: The **Human-Agent-Interaction** mode is now available! You can get involved with the Startr.Team team by playing the role of reviewer <img src='visualizer/static/figures/reviewer.png' height=20> and making suggestions to the programmer <img src='visualizer/static/figures/programmer.png' height=20>;
  try ``python3 run.py --task [description_of_your_idea] --config "Human"``. See [guide](wiki.md#human-agent-interaction) and [example](WareHouse/Website_HumanAgentInteraction_20230920135038).
  <p align="center">
  <img src='./misc/Human_intro.png' width=600>
  </p>
- September 1, 2023: The **Art** mode is available now! You can activate the designer agent <img src='visualizer/static/figures/designer.png' height=20> to generate images used in the software;
  try ``python3 run.py --task [description_of_your_idea] --config "Art"``. See [guide](wiki.md#art) and [example](WareHouse/gomokugameArtExample_THUNLP_20230831122822).
- August 28, 2023: The system is publicly available.
- August 17, 2023: The v1.0.0 version was ready for release.
- July 30, 2023: Users can customize ChatChain, Phase, and Role settings. Additionally, both online Log mode and replay
  mode are now supported.
- July 16, 2023: The [preprint paper](https://arxiv.org/abs/2307.07924) associated with this project was published.
- June 30, 2023: The initial version of the Startr.Team repository was released.
</details>

## ❓ What Can Startr.Team Do?

## ⚡️ Quickstart

### 💻️ Quickstart with Web

#TODO: Add web start guide

### 🖥️ Quickstart with terminal

To get started, follow these steps:

1. **Clone the GitHub Repository:** Begin by cloning the repository using the command:

   ```
   git clone 
   ```

2. **Set Up Python Environment:** 

   ```

   ```

3. **Install Dependencies:** Move into the `Startr.Team` directory and install the necessary dependencies by running:

   ```
   cd WEB-AI-Startr.Team
   pipenv install
   ```

4. **Set OpenAI API Key:** Export your OpenAI API key as an environment variable. Replace `"your_OpenAI_API_key"` with
   your actual API key. Remember that this environment variable is session-specific, so you need to set it again if you
   open a new terminal session.

  Alternativly and for a more permanent solution, copy the .env.example file to .env and add your API keys to it.

   On Unix/Linux:

   ```
   export OPENAI_API_KEY="your_OpenAI_API_key"
   ```

   On Windows:

   ```
   $env:OPENAI_API_KEY="your_OpenAI_API_key"
   ```

5. **Build Your Software:** Use the following command to initiate the building of your software,
   replacing `[description_of_your_idea]` with your idea's description and `[project_name]` with your desired project
   name:
 

   ```
   pipenv run python run.py --task "[description_of_your_idea]" --name "[project_name]"
   ```

  

6. **Run Your Software:** Once generated, you can find your software in the `WareHouse` directory under a specific
   project folder, such as `project_name_DefaultOrganization_timestamp`. 
   
   It's best to follow the generated README.md file for further instructions.

   For static sites, you can run the following command to start a local server:

   ```
    cd WareHouse/project_name_DefaultOrganization_timestamp
    python3 -m http.server
    ```


### 🐳 Quickstart with Docker

- We use Startr.sh for Docker deployment. To get started, follow these steps:

`bash <(curl -sL startr.sh) run` 

Startr.sh quickly deploys the WEB-AI-Startr.Team Docker container. You can access the web page for visualization and configuration at http://localhost:5000/.

## ✨️ Advanced Skills

For more detailed information, please refer to our [Wiki](wiki.md), where you can find:

- An introduction to all command run parameters.
- A straightforward guide for setting up a local web visualizer demo, which can visualize real-time logs, replayed logs, and ChatChain.
- An overview of the Startr.Team framework.
- A comprehensive introduction to all advanced parameters in ChatChain configuration.
- Guides for customizing WEB-AI-Startr.Team, including:
  - ChatChain: Design your own software development process (or any other process), such
      as ``DemandAnalysis -> Coding -> Testing -> Manual``.
  - Phase: Design your own phase within ChatChain, like ``DemandAnalysis``.
  - Role: Defining the various agents in your company, such as the ``Chief Executive Officer``.

## 🤗 Share Your Software

**Code**: We are enthusiastic about your interest in participating in our open-source project. If you come across any
problems, don't hesitate to report them. Feel free to create a pull request if you have any inquiries or if you are
prepared to share your work with us! Your contributions are highly valued. Please let me know if there's anything else
you need assistance!

**Company**: Creating your own customized "Startr.Team Company" is a breeze. This personalized setup involves three simple
configuration JSON files. Check out the example provided in the ``CompanyConfig/Default`` directory. For detailed
instructions on customization, refer to our [Wiki](wiki.md).

**Software**: Whenever you develop software using WEB-AI-Startr.Team, a corresponding folder is generated containing all the
essential information. Sharing your work with us is as simple as making a pull request. Here's an example: execute the
command ``python3 run.py --task "design a 2048 game" --name "2048"  --org "THUNLP" --config "Default"``. This will
create a software package and generate a folder named ``/WareHouse/2048_THUNLP_timestamp``. Inside, you'll find:

- All the files and documents related to the 2048 game software
- Configuration files of the company responsible for this software, including the three JSON config files
  from ``CompanyConfig/Default``
- A comprehensive log detailing the software's building process that can be used to replay (``timestamp.log``)
- The initial prompt used to create this software (``2048.prompt``)

**See community contributed software [here](Contribution.md)!**

## 👨‍💻‍ Contributors

<a href="https://github.com/OpenCoca/WEB-AI-Startr.Team/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=OpenCoca/WEB-AI-Startr.Team" />
</a>

Made with [contrib.rocks](https://contrib.rocks).

## 🔎 Citation



## ⚖️ License

See our LICENSE file for more information.

## 🤝 Acknowledgments

We would like to express our gratitude to the following individuals and organizations for their contributions to this

## 📬 Contact

If you have any questions, feedback, or would like to get in touch, please feel free to reach out to us via email at [contact.us@startr.team](mailto:contact.us@startr.team).
