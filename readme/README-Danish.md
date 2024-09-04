# Communicative Agents for Software Development

<p align="center">
  <img src='./misc/logo1.png' width=550>
</p>

<p align="center">
    【English   | <a href="readme/README-Chinese.md">Chinese</a> | <a href="readme/README-Japanese.md">Japanese</a> | <a href="readme/README-Korean.md">Korean</a> | <a href="readme/README-Filipino.md">Filipino</a> | <a href="readme/README-French.md">French</a> | <a href="readme/README-Slovak.md">Slovak</a> | <a href="readme/README-Portuguese.md">Portuguese</a> | <a href="readme/README-Spanish.md">Spanish</a> | <a href="readme/README-Dutch.md">Dutch</a> | <a href="readme/README-Turkish.md">Turkish</a> | <a href="readme/README-Hindi.md">Hindi</a> | <a href="readme/README-Bahasa-Indonesia.md">Bahasa Indonesia</a> | <a href="readme/README-Russian.md">Russian</a> 】
</p>
<p align="center">
    【📚 <a href="wiki.md">Wiki</a> | 🚀 <a href="wiki.md#visualizer">Visualizer</a> | 👥 <a href="Contribution.md">Community Built Software</a> | 🔧 <a href="wiki.md#customization">Customization</a> | 👾 <a href="https://discord.gg/bn4t2Jy6TT")>Discord</a>】

</p>
## 📖 Oversigt

- **ChatDev** står som et **virtuelt softwarefirma**, der opererer gennem forskellige **intelligente agenter** holding.
  forskellige roller, herunder Chief Executive Officer <img src='visualizer/static/figures/ceo.png' højde=20>, Chief Product Officer <img src='visualizer/static/figures/cpo.png' højde=20>, Chief Technology Officer <img src='visualizer/static/figures/cto.png' højde=20>, programmør <img src='visualizer/static/figures/programmer.png' højde=20>, reviewer <img src='visualizer/static/figures/reviewer.png' højde=20>, tester <img src='visualizer/statisk/figurer/tester.png' højde=20>, kunstdesigner <img src='visualizer/statisk/figurer/designer.png' højde=20>. Disse
  Agenter danner en organisationsstruktur med flere agenter og er forenet af en mission om at "revolutionere den digitale verden
  gennem programmering." Agenterne i ChatDev **samarbejder** ved at deltage i specialiserede funktionelle seminarer,
  herunder opgaver som design, kodning, test og dokumentation.
- Det primære mål med ChatDev er at tilbyde en **brugervenlig**, **meget tilpasselig** og **udvidelig** ramme,
  som er baseret på store sprogmodeller (LLM'er) og fungerer som et ideelt scenarie til at studere kollektiv intelligens.

<p align="center">
  <img src='./misc/company.png' bredde=600>
</p>

## 🎉 Nyheder
* **25. juni 2024: 🎉For at fremme udviklingen inden for LLM-drevet multi-agent-samarbejde🤖🤖 og relaterede områder har ChatDev-teamet kurateret en samling af skelsættende artikler📄 præsenteret i et [open source](https://github.com/OpenBMB/ChatDev/tree/main/MultiAgentEbook) interaktivt e-bogsformat📚. Nu kan du udforske de seneste fremskridt på [E-bogens websted](https://thinkwee.top/multiagent_ebook) og downloade [papirliste](https://github.com/OpenBMB/ChatDev/blob/main/MultiAgentEbook/papers.csv).**
  <p align="center">
  <img src='./misc/ebook.png' width=800>
  </p>
* 12. juni 2024: Vi introducerer Multi-Agent Collaboration Networks (MacNet), 🎉 som bruger rettede acykliske grafer til at lette effektivt opgaveorienteret samarbejde mellem agenter gennem sproglige interaktioner 🤖🤖. MacNet understøtter samarbejde på tværs af forskellige topologier og mellem mere end tusind agenter uden at overskride kontekstgrænserne. MacNet er mere alsidig og skalerbar og kan betragtes som en mere avanceret version af ChatDevs kædeformede topologi. Vores preprint-papir er tilgængeligt på [https://arxiv.org/abs/2406.07155](https://arxiv.org/abs/2406.07155). Denne teknik vil snart blive inkorporeret i dette lager, hvilket forbedrer understøttelsen af forskellige organisationsstrukturer og tilbyder rigere løsninger ud over softwareudvikling (f.eks. logisk ræsonnement, dataanalyse, historiegenerering og mere).
  <p align="center">
  <img src='./misc/macnet.png' bredde=500>
  </p>

  <details>
<summary>Gamle nyheder</summary>

* Den 7. maj 2024 introducerede vi "Iterative Experience Refinement" (IER), en ny metode, hvor instruktører og assistentagenter forbedrer genvejsorienterede oplevelser for effektivt at tilpasse sig nye opgaver. Denne tilgang omfatter erfaringserhvervelse, udnyttelse, udbredelse og eliminering på tværs af en række opgaver. Vores preprint-papir er tilgængeligt hos https://arxiv.org/abs/2405.04219, og denne teknik vil snart blive inkorporeret i ChatDev.
  <p align="center">
  <img src='./misc/ier.png' width=220>
  </p>

  * 25. januar 2024: Vi har integreret erfaringsbaseret co-learning-modul i ChatDev. Se venligst [Erfaringsbaseret co-learning Guide](wiki.md#co-tracking).

* 28. december 2023: Vi præsenterer Experiential Co-Learning, en innovativ tilgang, hvor instruktører og assistentagenter akkumulerer genvejsorienterede oplevelser for effektivt at løse nye opgaver, reducere gentagne fejl og øge effektiviteten.  Tjek vores preprint-papir på https://arxiv.org/abs/2312.17025, og denne teknik vil snart blive integreret i ChatDev.
  <p align="center">
  <img src='./misc/ecl.png' width=860>
  </p>

  * November 15, 2023: We launched ChatDev as a SaaS platform that enables software developers and innovative entrepreneurs to build software efficiently at a very low cost and barrier to entry. Try it out at https://chatdev.modelbest.cn/.
  <p align="center">
  <img src='./misc/saas.png' width=560>
  </p>

* November 2, 2023: ChatDev is now supported with a new feature: incremental development, which allows agents to develop upon existing codes. Try `--config "incremental" --path "[source_code_directory_path]"` to start it.
  <p align="center">
  <img src='./misc/increment.png' width=700>
  </p>

  * 26. oktober 2023: ChatDev understøttes nu med Docker for sikker udførelse (takket være bidrag fra [ManindraDeMel](https://github.com/ManindraDeMel)). Se [Docker Start Guide](wiki.md#docker-start).
  <p align="center">
  <img src='./misc/docker.png' width=400>
  </p>
* 25. september 2023: **Git**-tilstanden er nu tilgængelig, hvilket gør det muligt for programmøren <img src='visualizer/static/figures/programmer.png' height=20> at bruge Git til versionskontrol. For at aktivere denne funktion skal du blot indstille ''"git_management"'' til ''"Sand"'' i ''ChatChainConfig.json''. Se [guide](wiki.md#git-mode).
  <p align="center">
  <img src='./misc/github.png' width=600>
  </p>

- 20. september 2023: **Human-Agent-Interaction**-tilstanden er nu tilgængelig! Du kan blive involveret i ChatDev-teamet ved at spille rollen som korrekturlæser <img src='visualizer/static/figures/reviewer.png' height=20> og komme med forslag til programmøren <img src='visualizer/static/figures/programmer.png' height=20>;
  prøv ''python3 run.py --task [description_of_your_idea] --config "Menneske"''. Se [guide](wiki.md#human-agent-interaction) og [eksempel](WareHouse/Gomoku_HumanAgentInteraction_20230920135038).
  <p align="center">
  <img src='./misc/Human_intro.png' width=600>
  </p>
- 1. september 2023: **Art**-tilstanden er tilgængelig nu! Du kan aktivere designeragenten <img src='visualizer/static/figures/designer.png' height=20> for at generere billeder, der bruges i softwaren;
  prøv ''python3 run.py --task [description_of_your_idea] --config "Art"''. Se [guide](wiki.md#art) og [eksempel](WareHouse/gomokugameArtExample_THUNLP_20230831122822).

- 28. august 2023: Systemet er offentligt tilgængeligt.
- 17. august 2023: V1.0.0-versionen var klar til udgivelse.
- 30. juli 2023: Brugere kan tilpasse ChatChain-, fase- og rolleindstillinger. Derudover kan både online logtilstand og genafspilning
  tilstand understøttes nu.
- 16. juli 2023: [preprint-papiret](https://arxiv.org/abs/2307.07924) i forbindelse med dette projekt blev offentliggjort.
- 30. juni 2023: Den oprindelige version af ChatDev-lageret blev frigivet.
</details>

## ❓ Hvad kan ChatDev gøre?

! [indledning] (diverse/intro.png)

<https://github.com/OpenBMB/ChatDev/assets/11889052/80d01d2f-677b-4399-ad8b-f7af9bb62b72>

## ⚡️ Hurtig start

### 💻️ Hurtig start med web

Få adgang til websiden til visualisering og konfigurationsbrug: https://chatdev.modelbest.cn/

### 🖥️ Hurtig start med terminal

Følg disse trin for at komme i gang:

1. **Klon GitHub-depotet:** Begynd med at klone depotet ved hjælp af kommandoen:

```
   Git Clone https://github.com/OpenBMB/ChatDev.git
   ```

2. **Konfigurer Python-miljø:** Sørg for, at du har et version 3.9 eller højere Python-miljø. Du kan oprette og
   Aktivér dette miljø ved hjælp af følgende kommandoer, og erstat 'ChatDev_conda_env' med dit foretrukne miljø
   Navn:

```
   conda create -n ChatDev_conda_env python=3.9 -y
   conda aktiver ChatDev_conda_env
```
3. **Installer afhængigheder:** Flyt ind i 'ChatDev'-mappen og installer de nødvendige afhængigheder ved at køre:

```
   cd ChatDev
   pip3 installer -r requirements.txt
```

4. **Indstil OpenAI API-nøgle:** Eksporter din OpenAI API-nøgle som en miljøvariabel. Erstat ""your_OpenAI_API_key"' med
   din faktiske API-nøgle. Husk, at denne miljøvariabel er sessionsspecifik, så du skal angive den igen, hvis du
   Åbn en ny terminalsession.
   På Unix/Linux:

```
   eksport OPENAI_API_KEY="your_OpenAI_API_key"
```

På Windows:

```
   $env:OPENAI_API_KEY="your_OpenAI_API_key"
```

5. **Byg din software:** Brug følgende kommando til at starte opbygningen af din software,
   erstatte '[description_of_your_idea]' med din idés beskrivelse og '[project_name]' med dit ønskede projekt
   Navn:
   På Unix/Linux:

```
   python3 run.py --task "[description_of_your_idea]" --name "[project_name]"
```

På Windows:

```
   python run.py --task "[description_of_your_idea]" --name "[project_name]"
```

6. **Kør din software:** Når den er genereret, kan du finde din software i 'WareHouse'-mappen under en specifik
   projektmappe, f.eks. 'project_name_DefaultOrganization_timestamp'. Kør din software ved hjælp af følgende kommando
   i denne mappe:
   På Unix/Linux:

```
   cd WareHouse/project_name_DefaultOrganization_timestamp
   python3 main.py
```

På Windows:

```
   cd WareHouse/project_name_DefaultOrganization_timestamp
   Python main.py
```

### 🐳 Hurtig start med Docker

- Vi takker [ManindraDeMel](https://github.com/ManindraDeMel) for at yde Docker-support. Se [Docker Start Guide](wiki.md#docker-start).

## ✨️ Avancerede færdigheder

For mere detaljeret information henvises til vores [Wiki](wiki.md), hvor du kan finde:

- En introduktion til alle kommandokørselsparametre.
- En ligetil guide til opsætning af en lokal webvisualiseringsdemo, som kan visualisere logfiler i realtid, genafspillede logfiler og ChatChain.
- En oversigt over ChatDev-rammen.
- En omfattende introduktion til alle avancerede parametre i ChatChain-konfiguration.
- Vejledninger til tilpasning af ChatDev, herunder:
  - ChatChain: Design din egen softwareudviklingsproces (eller enhver anden proces), såsom
      som ''DemandAnalysis -> Coding -> Testing -> Manual''.
  - Fase: Design din egen fase i ChatChain, som ''DemandAnalysis''.
  - Rolle: Definition af de forskellige agenter i din virksomhed, såsom ''Chief Executive Officer''.

## 🤗 Del din software

**Kode**: Vi er begejstrede for din interesse i at deltage i vores open source-projekt. Hvis du støder på nogen
problemer, tøv ikke med at rapportere dem. Du er velkommen til at oprette en pull-anmodning, hvis du har spørgsmål, eller hvis du er
Klar til at dele dit arbejde med os! Dine bidrag er højt værdsat. Lad mig vide, hvis der er andet
Du har brug for hjælp!

**Virksomhed**: Det er en leg at skabe din egen tilpassede "ChatDev Company". Denne personlige opsætning involverer tre enkle
konfiguration JSON-filer. Se eksemplet i mappen ''CompanyConfig/Default''. For detaljerede
instruktioner om tilpasning, se vores [Wiki](wiki.md).

**Software**: Når du udvikler software ved hjælp af ChatDev, genereres en tilsvarende mappe, der indeholder alle
væsentlige oplysninger. At dele dit arbejde med os er lige så simpelt som at lave en pull-anmodning. Her er et eksempel: Udfør
kommandoen ''python3 run.py --task "design et 2048-spil" --name "2048" --org "THUNLP" --config "Default"''. Dette vil
oprette en softwarepakke og generere en mappe med navnet ''/WareHouse/2048_THUNLP_timestamp''. Indeni finder du:

- Alle filer og dokumenter relateret til 2048-spilsoftwaren
- Konfigurationsfiler fra det firma, der er ansvarlig for denne software, inklusive de tre JSON-konfigurationsfiler
  fra ''CompanyConfig/Default''
- En omfattende log, der beskriver softwarens byggeproces, der kan bruges til at afspille (''timestamp.log'')
- Den første prompt, der blev brugt til at oprette denne software (''2048.prompt'')

**Se software bidraget med fællesskabet [her](Contribution.md)!**

## 👨 💻 Bidragydere

<a href="https://github.com/OpenBMB/ChatDev/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=OpenBMB/ChatDev" />
</a>

## 🔎 Citation

```
@article{chatdev,
      title = {ChatDev: Communicative Agents for Software Development},
      author = {Chen Qian and Wei Liu and Hongzhang Liu and Nuo Chen and Yufan Dang and Jiahao Li and Cheng Yang and Weize Chen and Yusheng Su and Xin Cong and Juyuan Xu and Dahai Li and Zhiyuan Liu and Maosong Sun},
      journal = {arXiv preprint arXiv:2307.07924},
      url = {https://arxiv.org/abs/2307.07924},
      year = {2023}
}
```

## ⚖️ Licens

- Kildekodelicens: Vores projekts kildekode er licenseret under Apache 2.0-licensen. Denne licens tillader brug, ændring og distribution af koden på visse betingelser, der er beskrevet i Apache 2.0-licensen.
- Datalicens: De relaterede data, der bruges i vores projekt, er licenseret under CC BY-NC 4.0. Denne licens tillader udtrykkeligt ikke-kommerciel brug af dataene. Vi vil gerne understrege, at alle modeller, der trænes ved hjælp af disse datasæt, nøje skal overholde den ikke-kommercielle brugsbegrænsning og udelukkende bør anvendes til forskningsformål.

## 🤝 Anerkendelser

<a href="http://nlp.csai.tsinghua.edu.cn/"><img src="misc/thunlp.png" height=50pt></a>&nbsp;&nbsp;
<a href="https://modelbest.cn/"><img src="misc/modelbest.png" height=50pt></a>&nbsp;&nbsp;
<a href="https://github.com/OpenBMB/AgentVerse/"><img src="misc/agentverse.png" height=50pt></a>&nbsp;&nbsp;
<a href="https://github.com/OpenBMB/RepoAgent"><img src="misc/repoagent.png"  height=50pt></a>
<a href="https://app.commanddash.io/agent?github=https://github.com/OpenBMB/ChatDev"><img src="misc/CommandDash.png" height=50pt></a>

## 📬 Kontakt os

Hvis du har spørgsmål, feedback eller gerne vil i kontakt, er du velkommen til at kontakte os via e-mail på [qianc62@gmail.com](mailto:qianc62@gmail.com)

