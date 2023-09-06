# Communicative Agents for Software Development

<p align="center">
  <img src='./misc/logo1.png' width=600>
</p>

<p align="center">
    【English | <a href="README-Chinese.md">Chinese</a> | <a href="README-Japanese.md">Japanese</a> | <a href="README-Korean.md">Korean</a>】
</p>

## 📖 Overview

- **ChatDev** stands as a **virtual software company** that operates through various **intelligent agents** holding
  different roles, including Chief Executive Officer, Chief Technology Officer, Programmer, Tester, and more. These
  agents form a multi-agent organizational structure and are united by a mission to "revolutionize the digital world
  through programming." The agents within ChatDev **collaborate** by participating in specialized functional seminars,
  including tasks such as designing, coding, testing, and documenting.
- The primary objective of ChatDev is to offer an **easy-to-use**, **highly customizable** and **extendable** framework,
  which is based on large language models (LLMs) and serves as an ideal scenario for studying collective intelligence.

## 📰 News

* **September 1, 2023: The Art mode is available now! You can use agent to generate images used in the software,
  try ``python3 run.py --config "Art"``.** See [example](WareHouse/gomokugameArtExample_THUNLP_20230831122822) here.
* August 28, 2023: The system is publicly available.
* August 17, 2023: The V1.0.0 version was ready for release.
* July 30, 2023: Users can customize ChatChain, Phase, and Role settings. Additionally, both online Log mode and replay
  mode are now supported.
* July 16, 2023: The [preprint paper](https://arxiv.org/abs/2307.07924) associated with this project was published.
* June 30, 2023: The initial version of the `ChatDev` repository was released.

## ❓ What Can ChatDev Do?

![intro](misc/intro.png)

https://github.com/OpenBMB/ChatDev/assets/11889052/80d01d2f-677b-4399-ad8b-f7af9bb62b72

## ⚡️ Quickstart

To get started, follow these steps:

1. **Clone the GitHub Repository:** Begin by cloning the repository using the command:
   ```
   git clone https://github.com/OpenBMB/ChatDev.git
   ```
2. **Set Up Python Environment:** Ensure you have a version 3.9 or higher Python environment. You can create and
   activate this environment using the following commands, replacing `ChatDev_conda_env` with your preferred environment
   name:
   ```
   conda create -n ChatDev_conda_env python=3.9 -y
   conda activate ChatDev_conda_env
   ```
3. **Install Dependencies:** Move into the `ChatDev` directory and install the necessary dependencies by running:
   ```
   cd ChatDev
   pip3 install -r requirements.txt
   ```
4. **Set OpenAI API Key:** Export your OpenAI API key as an environment variable. Replace `"your_OpenAI_API_key"` with
   your actual API key. Remember that this environment variable is session-specific, so you need to set it again if you
   open a new terminal session.
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
   python3 run.py --task "[description_of_your_idea]" --name "[project_name]"
   ```
6. **Run Your Software:** Once generated, you can find your software in the `WareHouse` directory under a specific
   project folder, such as `project_name_DefaultOrganization_timestamp`. Run your software using the following command
   within that directory:
   ```
   cd WareHouse/project_name_DefaultOrganization_timestamp
   python3 main.py
   ```

## ✨️ Advanced Skills

For more detailed information, please refer to our [Wiki](wiki.md), where you can find:

- An introduction to all command run parameters.
- A straightforward guide for setting up a local web demo, which includes enhanced visualized logs, a replay demo, and a
  simple ChatChain Visualizer.
- An overview of the ChatDev framework.
- A comprehensive introduction to all advanced parameters in ChatChain configuration.
- Guides for customizing ChatDev, including:
    - ChatChain: Design your own software development process (or any other process), such
      as ``DemandAnalysis -> Coding -> Testing -> Manual``.
    - Phase: Design your own phase within ChatChain, like ``DemandAnalysis``.
    - Role: Defining the various agents in your company, such as the ``Chief Executive Officer``.

## 🤗 Share Your Software!

**Code**: We are enthusiastic about your interest in participating in our open-source project. If you come across any
problems, don't hesitate to report them. Feel free to create a pull request if you have any inquiries or if you are
prepared to share your work with us! Your contributions are highly valued. Please let me know if there's anything else
you need assistance!

**Company**: Creating your own customized "ChatDev Company" is a breeze. This personalized setup involves three simple
configuration JSON files. Check out the example provided in the ``CompanyConfig/Default`` directory. For detailed
instructions on customization, refer to our [Wiki](wiki.md).

**Software**: Whenever you develop software using ChatDev, a corresponding folder is generated containing all the
essential information. Sharing your work with us is as simple as making a pull request. Here's an example: execute the
command ``python3 run.py --task "design a 2048 game" --name "2048"  --org "THUNLP" --config "Default"``. This will
create a software package and generate a folder named ``/WareHouse/2048_THUNLP_timestamp``. Inside, you'll find:

- All the files and documents related to the 2048 game software
- Configuration files of the company responsible for this software, including the three JSON config files
  from ``CompanyConfig/Default``
- A comprehensive log detailing the software's building process that can be used to replay (``timestamp.log``)
- The initial prompt used to create this software (``2048.prompt``)

**See community contributed software [here](Contribution.md)!**

### Software Contributors

<a href="https://github.com/qianc62"><img src="https://avatars.githubusercontent.com/u/48988402?v=4" alt="Contributor" style="width:5%; border-radius: 50%;"/></a>
<a href="https://github.com/thinkwee"><img src="https://avatars.githubusercontent.com/u/11889052?v=4" alt="Contributor" style="width:5%; border-radius: 50%;"/></a>
<a href="https://github.com/NA-Wen"><img src="https://avatars.githubusercontent.com/u/92134380?v=4" alt="Contributor" style="width:5%; border-radius: 50%;"/></a>
<a href="https://github.com/lijiahao2022"><img src="https://avatars.githubusercontent.com/u/111221887?v=4" alt="Contributor" style="width:5%; border-radius: 50%;"/></a>
<a href="https://github.com/GeekyWizKid"><img src="https://avatars.githubusercontent.com/u/133981481?v=4" alt="Contributor" style="width:5%; border-radius: 50%;"/></a>

## 📑 Citation

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

## ⚖️ License

- The purpose of ChatDev is exclusively for research purposes.
- The source code is licensed under Apache 2.0.
- The datasets are licensed under CC BY NC 4.0, which allows for non-commercial use only. It is important to note that
  any models trained using these datasets should not be employed for purposes other than research.

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=openbmb/chatdev&type=Date)](https://star-history.com/#openbmb/chatdev&Date)
