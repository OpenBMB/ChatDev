# Communicative Agents for Software Development

<p align="center">
  <img src='./misc/logo1.png' width=550>
</p>

<p align="center">
    【English | <a href="README-Chinese.md">Chinese</a> | <a href="README-Japanese.md">Japanese</a> | <a href="README-Korean.md">Korean</a> | <a href="README-Filipino.md">Filipino</a> | <a href="README-French.md">French</a> | <a href="README-Slovak.md">Slovak</a>】
</p>
<p align="center">
    【📚 <a href="wiki.md">Wiki</a> | 🚀 <a href="wiki.md#local-demo">Local Demo</a> | 👥 <a href="Contribution.md">Community Built Software</a> | 🔧 <a href="wiki.md#customization">Customization</a>】
</p>

## 📖 Prehľad

- **ChatDev** je **virtuálna softvérová spoločnosť**, ktorá pôsobí prostredníctvom rôznych **inteligentných agentov**.
  rôznych funkcií, vrátane výkonného riaditeľa <img src='online_log/static/figures/ceo.png' height=20>, produktového riaditeľa <img src='online_log/static/figures/cpo.png' height=20>, technologického riaditeľa <img src='online_log/static/figures/cto. png" height=20>, programátor <img src='online_log/static/figures/programmer.png' height=20>, recenzent <img src='online_log/static/figures/reviewer.png' height=20>, tester <img src='online_log/static/figures/tester.png' height=20>, výtvarník <img src='online_log/static/figures/designer.png' height=20>. Tieto
  agenti tvoria multiagentovú organizačnú štruktúru a spája ich poslanie "revolučne zmeniť digitálny svet".
  prostredníctvom programovania." Agenti v rámci ChatDev **spolupracujú** účasťou na špecializovaných funkčných seminároch,
  vrátane úloh, ako je navrhovanie, kódovanie, testovanie a dokumentovanie.
- Hlavným cieľom ChatDev je ponúknuť **jednoduchý**, **vysoko prispôsobiteľný** a **rozšíriteľný** rámec,
  ktorý je založený na veľkých jazykových modeloch (LLM) a slúži ako ideálny scenár na štúdium kolektívnej inteligencie.
<p align="center">
  <img src='./misc/company.png' width=600>
</p>

## 🎉 Novinky

* ** 25. septembra 2023: Teraz je k dispozícii funkcia **Git**, ktorá umožňuje programátorovi <img src='online_log/static/figures/programmer.png' height=20> využívať GitHub na kontrolu verzií. Ak chcete túto funkciu povoliť, jednoducho nastavte ``"git_management"`` na ``"True"`` v súbore ``ChatChainConfig.json``.
  <p align="center">
  <img src='./misc/github.png' width=600>
  </p>
* 20. septembra 2023: Režim **Human-Agent-Interaction** je teraz k dispozícii! Môžete sa zapojiť do tímu ChatDev tým, že budete hrať úlohu recenzenta <img src='online_log/static/figures/reviewer.png' height=20> a predkladať návrhy programátorovi <img src='online_log/static/figures/programmer.png' height=20>;
  skúste ``python3 run.py --task [description_of_your_idea] --config "Human"``. Pozri [návod](wiki.md#human-agent-interaction) a [príklad](WareHouse/Gomoku_HumanAgentInteraction_20230920135038).
  <p align="center">
  <img src='./misc/Human_intro.png' width=600>
  </p>
* 1. septembra 2023: Režim **Art** je už k dispozícii! Môžete si aktivovať agenta dizajnéra <img src='online_log/static/figures/designer.png' height=20> na generovanie obrázkov používaných v programe;
  skúste ``python3 run.py --task [description_of_your_idea] --config "Art"``. Pozri [návod](wiki.md#art) a [príklad](WareHouse/gomokugameArtExample_THUNLP_20230831122822).
* 28. august 2023: Systém je verejne dostupný.
* 17. augusta 2023: Verzia v1.0.0 bola pripravená na vydanie.
* 30. júla 2023: Používatelia si môžu prispôsobiť nastavenia ChatChain, Phase a Role. Okrem toho je k dispozícii režim online záznamu aj replay
  režim sú teraz podporované.
* 16. júla 2023: Bol uverejnený článok [preprint paper](https://arxiv.org/abs/2307.07924) súvisiaci s týmto projektom.
* 30. júna 2023: Bola vydaná počiatočná verzia repozitára ChatDev.

## ❓ Čo dokáže ChatDev?

![intro](misc/intro.png)

https://github.com/OpenBMB/ChatDev/assets/11889052/80d01d2f-677b-4399-ad8b-f7af9bb62b72

## ⚡️ Quickstart

Ak chcete začať, postupujte podľa týchto krokov:

1. **Klonovanie úložiska GitHub:** Začnite klonovaním úložiska pomocou príkazu:
   ```
   git clone https://github.com/OpenBMB/ChatDev.git
   ```
2. **Nastavenie prostredia Python:** Uistite sa, že máte prostredie Python vo verzii 3.9 alebo vyššej. Môžete vytvoriť a
   toto prostredie aktivovať pomocou nasledujúcich príkazov, pričom `ChatDev_conda_env` nahradíte preferovaným prostredím
   name (názov):
   ```
   conda create -n ChatDev_conda_env python=3.9 -y
   conda activate ChatDev_conda_env
   ```
3. **Inštalácia závislostí:** Presuňte sa do adresára `ChatDev` a nainštalujte potrebné závislosti spustením:
   ```
   cd ChatDev
   pip3 install -r requirements.txt
   ```
4. **Nastavenie kľúča API OpenAI:** Exportujte svoj kľúč API OpenAI ako premennú prostredia. Nahraďte `"your_OpenAI_API_key"`
   svojím skutočným kľúčom API. Nezabudnite, že táto premenná prostredia je špecifická pre reláciu, takže ju musíte nastaviť znova, ak
   otvoríte novú reláciu terminálu.
   V systéme Unix/Linux:
   ```
   export OPENAI_API_KEY="your_OpenAI_API_key"
   ```
   V systéme Windows:
   ```
   $env:OPENAI_API_KEY="your_OpenAI_API_key"
   ```
5. **Zostavenie softvéru:** Na spustenie zostavovania softvéru použite nasledujúci príkaz,
   pričom `[description_of_your_idea]` nahradíte opisom svojho nápadu a `[project_name]` požadovaným projektom
   name:
   V systéme Unix/Linux:
   ```
   python3 run.py --task "[description_of_your_idea]" --name "[project_name]"
   ```
   V systéme Windows:
   ```
   python run.py --task "[description_of_your_idea]" --name "[project_name]"
   ```
6. **Spustenie softvéru:** Po vygenerovaní nájdete svoj softvér v adresári `WareHouse` pod konkrétnym
   priečinku projektu, napríklad `názov_projektu_Východisková_organizácia_časová značka`. Spustite svoj softvér pomocou nasledujúceho príkazu
   v tomto adresári:
   V systéme Unix/Linux:
   ```
   cd WareHouse/project_name_DefaultOrganization_timestamp
   python3 main.py
   ```
   Na Windowse
   ```
   cd WareHouse/project_name_DefaultOrganization_timestamp
   python main.py
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

## 👨‍💻‍ Software Contributors

<a href="https://github.com/qianc62"><img src="https://avatars.githubusercontent.com/u/48988402?v=4" alt="Contributor" style="width:5%; border-radius: 50%;"/></a>
<a href="https://github.com/thinkwee"><img src="https://avatars.githubusercontent.com/u/11889052?v=4" alt="Contributor" style="width:5%; border-radius: 50%;"/></a>
<a href="https://github.com/NA-Wen"><img src="https://avatars.githubusercontent.com/u/92134380?v=4" alt="Contributor" style="width:5%; border-radius: 50%;"/></a>
<a href="https://github.com/JiahaoLi2003"><img src="https://avatars.githubusercontent.com/u/111221887?v=4" alt="Contributor" style="width:5%; border-radius: 50%;"/></a>
<a href="https://github.com/Alphamasterliu"><img src="https://avatars.githubusercontent.com/u/110011045?v=4" alt="Contributor" style="width:5%; border-radius: 50%;"/></a>
<a href="https://github.com/GeekyWizKid"><img src="https://avatars.githubusercontent.com/u/133981481?v=4" alt="Contributor" style="width:5%; border-radius: 50%;"/></a>
<a href="https://github.com/Munsif-Raza-T"><img src="https://avatars.githubusercontent.com/u/76085202?v=4" alt="Contributor" style="width:5%; border-radius: 50%;"/></a>
<a href="https://github.com/djbritt"><img src="https://avatars.githubusercontent.com/u/28036018?v=4" alt="Contributor" style="width:5%; border-radius: 50%;"/></a>
<a href="https://github.com/Classified3939"><img src="https://avatars.githubusercontent.com/u/102702965?v=4" alt="Contributor" style="width:5%; border-radius: 50%;"/></a>
<a href="https://github.com/chenilim"><img src="https://avatars.githubusercontent.com/u/46905241?v=4" alt="Contributor" style="width:5%; border-radius: 50%;"/></a>
<a href="https://github.com/delconis"><img src="https://avatars.githubusercontent.com/u/5824478?v=4" alt="Contributor" style="width:5%; border-radius: 50%;"/></a>
<a href="https://github.com/eMcQuill"><img src="https://avatars.githubusercontent.com/u/139025701?v=4" alt="Contributor" style="width:5%; border-radius: 50%;"/></a>

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

## ⚖️ License

- Source Code Licensing: Our project's source code is licensed under the Apache 2.0 License. This license permits the use, modification, and distribution of the code, subject to certain conditions outlined in the Apache 2.0 License.
- Project Open-Source Status: The project is indeed open-source; however, this designation is primarily intended for non-commercial purposes. While we encourage collaboration and contributions from the community for research and non-commercial applications, it is important to note that any utilization of the project's components for commercial purposes necessitates separate licensing agreements.
- Data Licensing: The related data utilized in our project is licensed under CC BY-NC 4.0. This license explicitly permits non-commercial use of the data. We would like to emphasize that any models trained using these datasets should strictly adhere to the non-commercial usage restriction and should be employed exclusively for research purposes.

## 🌟 Star History

[![Star History Chart](https://api.star-history.com/svg?repos=openbmb/chatdev&type=Date)](https://star-history.com/#openbmb/chatdev&Date)


## 🤝 Acknowledgments
<a href="http://nlp.csai.tsinghua.edu.cn/"><img src="misc/thunlp.png" height=50pt></a>&nbsp;&nbsp;
<a href="https://modelbest.cn/"><img src="misc/modelbest.png" height=50pt></a>&nbsp;&nbsp;
<a href="https://github.com/OpenBMB/AgentVerse/"><img src="misc/agentverse.png" height=50pt></a>&nbsp;&nbsp;
<a href="https://aibrb.com/introducing-herbie-your-super-employee-for-streamlined-productivity/"><img src="https://aibrb.com/wp-content/uploads/2023/09/Featured-on-AIBRB.com-white-1.png"  height=50pt></a>

## 📬 Contact

If you have any questions, feedback, or would like to get in touch, please feel free to reach out to us via email at [chatdev.openbmb@outlook.com](mailto:chatdev.openbmb@outlook.com)
