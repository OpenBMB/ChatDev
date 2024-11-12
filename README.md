# Scaling Large-Language-Model-based Multi-Agent Collaboration

<p align="center">
  <img src='./misc/macnet.png' width=550>
</p>

## 📖 Overview

MacNet is a specialized branch of [ChatDev](https://github.com/OpenBMB/ChatDev) that focuses on supporting the research of agent scaling on arbitrary topologies using the Multi-Agent Collaboration Networks (MacNet) framework. MacNet utilizes directed acyclic graphs to facilitate effective task-oriented collaboration among agents through linguistic interactions. It supports cooperation across various topologies and among a large number of agents without exceeding context limits.

## ⚡️ Quickstart

To get started with MacNet, follow these steps:

  <p align="center">
    <img src='./misc/topo.png' width=550>
  </p>

1. **Generate Graph Structure:** Run `generate_graph.py` to generate the desired graph structure for your multi-agent collaboration network. You can customize the number of nodes and the topology of the graph. For example:

   ```
   python generate_graph.py --node_num 10 --topology tree 
   ```

2. **Configure MacNet:** The `generate_graph.py` will automatically update the graph config in the `config.yaml` file. You can check other parameters for deploying agents, including the LLM backend and prompt. Additionally, MacNet supports the **SRDD_Profile** dataset, which is a large-scale agent role prompt dataset. It allows you to randomly select system profile prompts for the deployed agents in the topology based on the software category. To use SRDD_Profile, specify the category using the `--type` parameter when running `run.py`.

  <p align="center">
    <img src='./misc/agent_deploy.png' width=400>
  </p>

3. **Run MacNet:** Execute `run.py` to deploy agents on the specified graph topology and generate software based on the configuration in `config.yaml`. During this process, you can observe the complete graph structure, the code changes occurring from one node to another, and the corresponding agent suggestions. MacNet will run agents on the graph in the topological order. You can observe the code changes in each node transition and agent suggestions on each edge in real-time.


   ```
   python run.py --task "Develop a basic Gomoku game." --name "Gomoku" [--type <software_category>]
   ```

   - `--task`: Specifies the prompt or description of the software to be developed.
   - `--name`: Specifies the name of the software project.
   - `--type` (optional): Specifies the software category for selecting system profile prompts from the SRDD_Profile dataset.

  <p align="center">
    <img src='./misc/topo_order.png' width=800>
  </p>
  

4. **Access Generated Software:** After the execution of `run.py`, the generated software can be found in the `WareHouse` directory. Each software project will have its own folder with a timestamp.

5. **View Logs:** The complete logs of the MacNet execution can be found in the `MacNetLog` directory. The logs are organized by timestamp and provide detailed information about the multi-agent collaboration process.

## 🌰 Example
- Example of various generated topologies:

<p align="center">
  <img src='./misc/topo_example2.png' width=550>
</p>

<p align="center">
  <img src='./misc/topo_example.png' width=550>
</p>

- Example of the MacNet running process, including the suggestions and code diffs between agents on adjacent nodes:
<p align="center">
  <img src='./misc/running_example.png' width=800>
</p>

- Example of the generated software:
<p align="center">
  <img src='./misc/software_example.png' width=800>
</p>

## 🔎 Citation

```
@article{qian2024scaling,
  title={Scaling Large-Language-Model-based Multi-Agent Collaboration},
  author={Chen Qian and Zihao Xie and Yifei Wang and Wei Liu and Yufan Dang and Zhuoyun Du and Weize Chen and Cheng Yang and Zhiyuan Liu and Maosong Sun}
  journal={arXiv preprint arXiv:2406.07155},
  year={2024}
}
```

## 🤝 Acknowledgments

MacNet is built upon the foundation of [ChatDev](https://github.com/OpenBMB/ChatDev), a project that aims to revolutionize software development through communicative agents.

## 📬 Contact

If you have any questions, feedback, or would like to get in touch, please feel free to reach out to us via email at [qianc62@gmail.com](mailto:qianc62@gmail.com).

