# AutoM8 - ChatDev with God Mode

## 📖 Overview

- This is a fork to the original [ChatDev](https://github.com/OpenBMB/ChatDev) project.
- In AutoM8, we introduced the God mode, where the human can interact and give instructions to the AI agents.

## ⚡️ Quickstart

To get started, follow these steps:

1. **Clone the GitHub Repository:** Begin by cloning the repository using the command:
   ```
   git clone git@github.com:shawnzhesun/AutoM8.git
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
5. **Start AutoM8:** Open the AutoM8 URL at http://127.0.0.1:8000/static/god_mode.html


