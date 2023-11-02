# Communicative Agents for Software Development

<p align="center">
  <img src='../misc/logo1.png' width=550>
</p>

<p align="center">
    【📚 <a href="../wiki.md">Wiki</a> | 🚀 <a href="../wiki.md#local-demo">Lokale Demo</a> | 👥 <a href="../Contribution.md">Community Gebouwde Software</a> | 🔧 <a href="../wiki.md#customization">Aanpassing</a>】
</p>

## 📖 Overzicht

- **ChatDev** fungeert als een **virtueel softwarebedrijf** dat werkt met verschillende **intelligente agenten** die verschillende rollen vervullen, waaronder Chief Executive Officer <img src='../online_log/static/figures/ceo.png' height=20>, Chief Product Officer <img src='../online_log/static/figures/cpo.png' height=20>, Chief Technology Officer <img src='../online_log/static/figures/cto.png' height=20>, programmeur <img src='../online_log/static/figures/programmer.png' height=20>, recensent <img src='../online_log/static/figures/reviewer.png' height=20>, tester <img src='../online_log/static/figures/tester.png' height=20>, kunstontwerper <img src='../online_log/static/figures/designer.png' height=20>. Deze agenten vormen een multi-agent organisatiestructuur en zijn verenigd door een missie om "de digitale wereld te revolutioneren door middel van programmeren." De agenten binnen ChatDev **werken samen** door deel te nemen aan gespecialiseerde functionele seminars, waaronder taken zoals ontwerpen, coderen, testen en documenteren.
- Het primaire doel van ChatDev is het aanbieden van een **eenvoudig te gebruiken**, **zeer aanpasbaar** en **uitbreidbaar** framework, dat is gebaseerd op grote taalmodellen (LLM's) en dient als een ideaal scenario voor het bestuderen van collectieve intelligentie.
<p align="center">
  <img src='../misc/company.png' width=600>
</p>

## 🎉 Nieuws

* **25 september 2023: De **Git**-functie is nu beschikbaar**, waardoor de programmeur <img src='../online_log/static/figures/programmer.png' height=20> GitHub kan gebruiken voor versiebeheer. Om deze functie in te schakelen, stelt u eenvoudigweg ``"git_management"`` in op ``"True"`` in ``ChatChainConfig.json``.
  <p align="center">
  <img src='../misc/github.png' width=600>
  </p>
* 20 september 2023: De **Human-Agent-Interaction**-modus is nu beschikbaar! U kunt deelnemen aan het ChatDev-team door de rol van recensent <img src='../online_log/static/figures/reviewer.png' height=20> te spelen en suggesties te doen aan de programmeur <img src='../online_log/static/figures/programmer.png' height=20>; probeer ``python3 run.py --task [beschrijving_van_uw_idee] --configuratie "Human"``. Zie [handleiding](../wiki.md#human-agent-interactie) en [voorbeeld](../WareHouse/Gomoku_HumanAgentInteraction_20230920135038).
  <p align="center">
  <img src='../misc/Human_intro.png' width=600>
  </p>
* 1 september 2023: De **Art**-modus is nu beschikbaar! U kunt de ontwerpagent <img src='../online_log/static/figures/designer.png' height=20> activeren om afbeeldingen te genereren die in de software worden gebruikt; probeer ``python3 run.py --task [beschrijving_van_uw_idee] --configuratie "Art"``. Zie [handleiding](../wiki.md#art) en [voorbeeld](../WareHouse/gomokugameArtExample_THUNLP_20230831122822).
* 28 augustus 2023: Het systeem is nu openbaar beschikbaar.
* 17 augustus 2023: De v1.0.0-versie was gereed voor release.
* 30 juli 2023: Gebruikers kunnen ChatChain-, Fase- en Rolvermeldingen aanpassen. Bovendien worden zowel online Log-modus als herhalingsmodus ondersteund.
* 16 juli 2023: Het [voorlopige paper](https://arxiv.org/abs/2307.07924) dat aan dit project is gekoppeld, is gepubliceerd.
* 30 juni 2023: De eerste versie van het ChatDev-repository werd uitgebracht.

## ❓ Wat kan ChatDev doen?

![intro](../misc/intro.png)

https://github.com/OpenBMB/ChatDev/assets/11889052/80d01d2f-677b-4399-ad8b-f7af9bb62b72

## ⚡️ Snel van start

Om aan de slag te gaan, volg deze stappen:

1. **Kloon de GitHub Repository:** Begin met het klonen van de repository met het volgende commando:
   	```
   	git clone https://github.com/OpenBMB/ChatDev.git
   	```
2. **Stel uw Python-omgeving in:** Zorg ervoor dat u een Python-omgeving van versie 3.9 of hoger heeft. U kunt deze omgeving maken en activeren met de volgende opdrachten, waarbij u 'ChatDev_conda_env' vervangt door uw gewenste omgevingsnaam:
   	```
   	conda create -n ChatDev_conda_env python=3.9 -y
   	conda activate ChatDev_conda_env
   	```
3. **Installeer de benodigde afhankelijkheden:** Ga naar de `ChatDev`-directory en installeer de benodigde afhankelijkheden door het volgende commando uit te voeren:
	```
	cd ChatDev
	pip3 install -r requirements.txt
 	```
4. **Stel uw OpenAI API-sleutel in:** Exporteer uw OpenAI API-sleutel als een omgevingsvariabele. Vervang `"uw_OpenAI_API-sleutel"` door uw daadwerkelijke API-sleutel. Onthoud dat deze omgevingsvariabele sessiespecifiek is, dus u moet deze opnieuw instellen als u een nieuwe terminalsessie opent.
	Op Unix/Linux:
	```
 	export OPENAI_API_KEY="uw_OpenAI_API-sleutel"
	```
	Op Windows:
	```
 	$env:OPENAI_API_KEY="uw_OpenAI_API-sleutel"
	```
5. **Bouw uw software:** Gebruik het volgende commando om het bouwen van uw software te starten, waarbij u '[beschrijving_van_uw_idee]' vervangt door de beschrijving van uw idee en '[projectnaam]' door uw gewenste projectnaam:
	Op Unix/Linux:
	```
	python3 run.py --task "[beschrijving_van_uw_idee]" --naam "[projectnaam]"
	```
	Op Windows:
	```
	python run.py --taak "[beschrijving_van_uw_idee]" --naam "[projectnaam]"
	```
6. **Voer uw software uit:** Zodra gegenereerd, kunt u uw software vinden in de `WareHouse`-directory onder een specifieke projectmap, zoals `projectnaam_DefaultOrganization_timestamp`. Voer uw software uit met het volgende commando binnen die directory:
	Op Unix/Linux:
	```
	cd WareHouse/projectnaam_DefaultOrganization_timestamp
	python3 main.py
	```
 	Op Windows:
	```
	cd WareHouse/projectnaam_DefaultOrganization_timestamp
	python main.py
	```

## ✨️ Geavanceerde Vaardigheden

Voor meer gedetailleerde informatie, verwijzen wij u graag naar onze [Wiki](../wiki.md), waar u kunt vinden:

- Een inleiding tot alle commando-uitvoeringsparameters.
- Een eenvoudige handleiding voor het opzetten van een lokale webdemo, inclusief verbeterde visuele logs, een herhalingdemo en een eenvoudige ChatChain Visualizer.
- Een overzicht van het ChatDev-framework.
- Een uitgebreide introductie tot alle geavanceerde parameters in de ChatChain-configuratie.
- Handleidingen voor het aanpassen van ChatDev, inclusief:
    - ChatChain: Ontwerp uw eigen softwareontwikkelingsproces (of elk ander proces), zoals ``DemandAnalysis -> Codering -> Testen -> Handmatig``.
    - Fase: Ontwerp uw eigen fase binnen ChatChain, zoals ``DemandAnalysis``.
    - Rol: Definieer de verschillende agenten in uw bedrijf, zoals de ``Chief Executive Officer``.

## 🤗 Deel je Software!

**Code**: We zijn enthousiast over je interesse om deel te nemen aan ons open-source project. Als je ergens problemen tegenkomt, aarzel dan niet om ze te melden. Voel je vrij om een pull-aanvraag te maken als je vragen hebt of als je bereid bent je werk met ons te delen! Jouw bijdragen worden zeer gewaardeerd. Laat me weten als er iets is waarbij je hulp nodig hebt!

**Bedrijf**: Het creëren van je eigen aangepaste "ChatDev-bedrijf" is een fluitje van een cent. Deze gepersonaliseerde opstelling omvat drie eenvoudige configuratie-JSON-bestanden. Bekijk het voorbeeld in de map ``CompanyConfig/Default``. Voor gedetailleerde instructies over aanpassing, verwijzen wij naar onze [Wiki](../wiki.md).

**Software**: Telkens wanneer je software ontwikkelt met ChatDev, wordt er een overeenkomstige map gegenereerd met alle essentiële informatie. Je werk met ons delen is net zo eenvoudig als een pull-aanvraag maken. Hier is een voorbeeld: voer het commando uit ``python3 run.py --task "ontwerp een 2048 spel" --naam "2048" --org "THUNLP" --configuratie "Default"``. Hiermee maak je een softwarepakket en genereert een map met de naam ``/WareHouse/2048_THUNLP_timestamp``. Daarin vind je:

- Alle bestanden en documenten met betrekking tot de 2048-game-software
- Configuratiebestanden van het bedrijf dat verantwoordelijk is voor deze software, inclusief de drie JSON-configuratiebestanden uit ``CompanyConfig/Default``
- Een uitgebreid logboek met details over het bouwproces van de software, dat kan worden gebruikt voor herhaling (``timestamp.log``)
- De oorspronkelijke prompt die is gebruikt om deze software te maken (``2048.prompt``)

**Bekijk door de gemeenschap bijgedragen software [hier](../Contribution.md)!**

## 👨‍💻‍ Software Bijdragers

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

## 🔎 Bronvermelding

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

## ⚖️ Licentie

- Licentie voor Broncode: De broncode van ons project valt onder de Apache 2.0-licentie. Deze licentie staat het gebruik, de aanpassing en de verspreiding van de code toe, met inachtneming van bepaalde voorwaarden zoals uiteengezet in de Apache 2.0-licentie.
- Open-Source Status van het Project: Het project is inderdaad open-source, maar deze aanduiding is primair bedoeld voor niet-commerciële doeleinden. Hoewel we samenwerking en bijdragen van de gemeenschap aanmoedigen voor onderzoeks- en niet-commerciële toepassingen, is het belangrijk op te merken dat elke commerciële toepassing van de projectonderdelen afzonderlijke licentieovereenkomsten vereist.
- Licentie voor Gegevens: De gerelateerde gegevens die in ons project worden gebruikt, vallen onder de CC BY-NC 4.0-licentie. Deze licentie staat uitdrukkelijk het niet-commerciële gebruik van de gegevens toe. Wij willen benadrukken dat modellen die met behulp van deze datasets zijn getraind, strikt moeten voldoen aan de beperkingen voor niet-commercieel gebruik en uitsluitend voor onderzoeksdoeleinden moeten worden ingezet.

## 🌟 Star Geschiedenis

[![Star History Chart](https://api.star-history.com/svg?repos=openbmb/chatdev&type=Date)](https://star-history.com/#openbmb/chatdev&Date)


## 🤝 Erkenningen
<a href="http://nlp.csai.tsinghua.edu.cn/"><img src="../misc/thunlp.png" height=50pt></a>&nbsp;&nbsp;
<a href="https://modelbest.cn/"><img src="../misc/modelbest.png" height=50pt></a>&nbsp;&nbsp;
<a href="https://github.com/OpenBMB/AgentVerse/"><img src="../misc/agentverse.png" height=50pt></a>&nbsp;&nbsp;
<a href="https://aibrb.com/introducing-herbie-your-super-employee-for-streamlined-productivity/"><img src="https://aibrb.com/wp-content/uploads/2023/09/Featured-on-AIBRB.com-white-1.png"  height=50pt></a>

## 📬 Contact

Als je vragen hebt, feedback wilt geven, of contact met ons wilt opnemen, aarzel dan niet om ons te mailen op [chatdev.openbmb@outlook.com](mailto:chatdev.openbmb@outlook.com)
