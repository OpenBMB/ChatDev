# Communicative Agents for Software Development

<p align="center">
  <img src='../misc/logo1.png' width=550>
</p>


<p align="center">
    【📚 <a href="../wiki.md">Wiki</a> | 🚀 <a href="../wiki.md#local-demo">Lokalne Demo</a> | 👥 <a href="../Contribution.md">Softvér vytvorený komunitou</a> | 🔧 <a href="../wiki.md#customization">Prispôsobenie</a>】
</p>

## 📖 Prehľad

- **ChatDev** je **virtuálna softvérová spoločnosť**, ktorá pôsobí prostredníctvom rôznych **inteligentných agentov**.
  rôznych funkcií, vrátane riaditeľa <img src='../online_log/static/figures/ceo.png' height=20>, produktového riaditeľa <img src='../online_log/static/figures/cpo.png' height=20>, technologického riaditeľa <img src="online_log/static/figures/cto.png" height=20>, programátor <img src='../online_log/static/figures/programmer.png' height=20>, recenzent <img src='../online_log/static/figures/reviewer.png' height=20>, tester <img src='../online_log/static/figures/tester.png' height=20>, výtvarník <img src='../online_log/static/figures/designer.png' height=20>. Týto
  agenti tvoria multiagentovú organizačnú štruktúru a spája ich poslanie "revolučne zmeniť digitálny svet
  prostredníctvom programovania." Agenti v rámci ChatDev **spolupracujú** účasťou na špecializovaných funkčných seminároch,
  vrátane úloh, ako je navrhovanie, kódovanie, testovanie a dokumentovanie.
- Hlavným cieľom ChatDev je ponúknuť **jednoduchý**, **vysoko prispôsobiteľný** a **rozšíriteľný** framework,
  ktorý je založený na veľkých jazykových modeloch (LLM) a slúži ako ideálny scenár na štúdium kolektívnej inteligencie.
<p align="center">
  <img src='../misc/company.png' width=600>
</p>

## 🎉 Novinky

* september 25. 2023: Teraz je k dispozícii funkcia **Git**, ktorá umožňuje programátorovi <img src='../online_log/static/figures/programmer.png' height=20> využívať GitHub na version control. Ak chcete túto funkciu povoliť, jednoducho nastavte ``"git_management"`` na ``"True"`` v súbore ``ChatChainConfig.json``.
  <p align="center">
  <img src='../misc/github.png' width=600>
  </p>
* september 20. 2023: Režim **Human-Agent-Interaction** je teraz k dispozícii! Môžete sa zapojiť do tímu ChatDev tým, že budete hrať úlohu recenzenta <img src='../online_log/static/figures/reviewer.png' height=20> a predkladať návrhy programátorovi <img src='../online_log/static/figures/programmer.png' height=20>;
  skúste ``python3 run.py --task [description_of_your_idea] --config "Human"``. Pozri [návod](../wiki.md#human-agent-interaction) a [príklad](../WareHouse/Gomoku_HumanAgentInteraction_20230920135038).
  <p align="center">
  <img src='../misc/Human_intro.png' width=600>
  </p>
* september 1. 2023: Režim **Art** je už k dispozícii! Môžete si aktivovať agenta dizajnéra <img src='../online_log/static/figures/designer.png' height=20> na generovanie obrázkov používaných v programe;
  skúste ``python3 run.py --task [description_of_your_idea] --config "Art"``. Pozri [návod](../wiki.md#art) a [príklad](../WareHouse/gomokugameArtExample_THUNLP_20230831122822).
* august 28. 2023: Systém je verejne dostupný.
* august 17. 2023: Verzia v1.0.0 bola pripravená na vydanie.
* júl 30. 2023: Používatelia si môžu prispôsobiť nastavenia ChatChain, Phase a Role. Okrem toho je k dispozícii režim online záznamu aj replay
  režim sú teraz podporované.
* júl 16. 2023: Bol uverejnený článok [preprint paper](https://arxiv.org/abs/2307.07924) súvisiaci s týmto projektom.
* jún 30. 2023: Bola vydaná počiatočná verzia repozitára ChatDev.

## ❓ Čo dokáže ChatDev?

![intro](../misc/intro.png)

https://github.com/OpenBMB/ChatDev/assets/11889052/80d01d2f-677b-4399-ad8b-f7af9bb62b72

## ⚡️ Rýchly štart
Ak chcete začať, postupujte podľa týchto krokov:

1. **Naklonovať GitHub repozitár:** Začnite klonovaním repozitára pomocou príkazu:
   ```
   git clone https://github.com/OpenBMB/ChatDev.git
   ```
2. **Nastavenie prostredia Python:** Uistite sa, že máte prostredie Python vo verzii 3.9 alebo vyššej. Môžete vytvoriť a
   aktivovať toto prostredie pomocou nasledujúcich príkazov, pričom `ChatDev_conda_env` nahradíte preferovaným menom prostredia
   :
   ```
   conda create -n ChatDev_conda_env python=3.9 -y
   conda activate ChatDev_conda_env
   ```
3. **inštalácia knižníc:** Presuňte sa do adresára `ChatDev` a nainštalujte potrebné knižnice spustením:
   ```
   cd ChatDev
   pip3 install -r requirements.txt
   ```
4. **Nastavenie kľúča API OpenAI:** Exportujte svoj kľúč API OpenAI ako premennú prostredia. Nahraďte `"vas_OpenAI_API_kluc"`
   svojím skutočným kľúčom API. **Nezabudnite, že táto premenná prostredia je špecifická pre reláciu, takže ju musíte nastaviť znova, ak**
   **otvoríte novú reláciu terminálu.**
   V systéme Unix/Linux:
   ```
   export OPENAI_API_KEY="vas_OpenAI_API_kluc"
   ```
   V systéme Windows:
   ```
   $env:OPENAI_API_KEY="vas_OpenAI_API_kluc"
   ```
5. **Generovanie softvéru:** Na spustenie generovania softvéru použite nasledujúci príkaz,
   pričom `[popis_vášho_nápadu]` nahradíte opisom svojho nápadu a `[meno_projektu]` požadovaným menom projektu:
   Na systéme Unix/Linux:
   ```
   python3 run.py --task "[popis_vášho_nápadu]" --name "[meno_projektu]"
   ```
   Na systéme Windows:
   ```
   python run.py --task "[popis_vášho_nápadu]" --name "[meno_projektu]"
   ```
6. **Spustenie softvéru:** Po vygenerovaní nájdete svoj softvér v adresári `WareHouse` pod konkrétnym
   priečinku projektu, napríklad `moj_projekt_DefaultOrganization_20231010224405`. Spustite svoj softvér pomocou nasledujúceho príkazu
   v tomto adresári:
   V systéme Unix/Linux:
   ```
   cd WareHouse/moj_projekt_DefaultOrganization_20231010224405
   python3 main.py
   ```
   Na Windowse
   ```
   cd WareHouse/moj_projekt_DefaultOrganization_20231010224405
   python main.py
   ```

## ✨️ Pokročilé zručnosti

Podrobnejšie informácie nájdete na našej [Wiki](../wiki.md), kde nájdete:

- Úvod do všetkých parametrov spúšťania príkazov.
- Jednoduchý návod na nastavenie miestnej webovej ukážky, ktorá obsahuje rozšírené vizualizované protokoly, ukážku prehrávania a
  jednoduchý vizualizér ChatChain.
- Prehľad ChatDev frameworku.
- Komplexný úvod do všetkých pokročilých parametrov konfigurácie ChatChain.
- Návody na prispôsobenie ChatDev vrátane:
    - ChatChain: Navrhnite si vlastný proces vývoja softvéru (alebo akýkoľvek iný proces), napr.
      ako ``Analýza dopytu -> Kódovanie -> Testovanie -> Manuálne``.
    - Fáza: Navrhnite si vlastnú fázu v rámci ChatChain, napríklad ``DemandAnalysis``.
    - Rola: Definovanie rôznych zástupcov vo vašej spoločnosti, napríklad ``Hlavný výkonný riaditeľ``.

## 🤗 Zdieľajte svoj softvér!

**Kód**: Sme nadšení z vášho záujmu o účasť na našom open-source projekte. Ak narazíte na akýkoľvek
problémy, neváhajte ich nahlásiť. Neváhajte a vytvorte žiadosť o stiahnutie, ak máte nejaké otázky alebo ak ste
pripravení podeliť sa s nami o svoju prácu! Vaše príspevky si veľmi ceníme. Dajte mi prosím vedieť, ak potrebujete pomoc!

**Spoločnosť**: Vytvorenie vlastnej prispôsobenej "ChatDev Company" je hračka. Toto personalizované nastavenie zahŕňa tri jednoduché
konfiguračné súbory JSON. Pozrite si príklad uvedený v adresári ``CompanyConfig/Default``. Podrobný
návod na prispôsobenie nájdete na našej [Wiki](../wiki.md).

**Softvér**: Vždy, keď vyvíjate softvér pomocou ChatDev, vytvorí sa príslušný priečinok obsahujúci všetky
dôležité informácie. Zdieľanie vašej práce s nami je také jednoduché ako pull request. Tu je príklad: vykonajte
príkaz ``python3 run.py --task "design a 2048 game" --name "2048" --org "THUNLP" --config "Default"``. Tým sa
vytvorí softvérový balík a vygeneruje priečinok s názvom ``/WareHouse/2048_THUNLP_timestamp``. V ňom nájdete:

- Všetky súbory a dokumenty týkajúce sa softvéru hry 2048
- Konfiguračné súbory spoločnosti zodpovednej za tento softvér vrátane troch konfiguračných súborov JSON
  z ``CompanyConfig/Default``
- Komplexný protokol s podrobnými informáciami o procese vytvárania softvéru, ktorý možno použiť na prehrávanie (``timestamp.log``)
- Počiatočny "prompt" alebo zadanie použite na vytvorenie tohto softvéru (``2048.prompt``)

**Pozrite si softvér poskytnutý komunitou [tu](../Contribution.md)!**

## 👨‍💻‍ Kontributory softvéru

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
<a href="https://github.com/Aizhouym"><img src="https://avatars.githubusercontent.com/u/105852026?v=4" alt="Contributor" style="width:5%; border-radius: 50%;"/></a>

## 🔎 Citát

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

- Licencovanie zdrojového kódu: Zdrojový kód nášho projektu je licencovaný pod licenciou Apache 2.0. Táto licencia povoľuje používanie, modifikáciu a šírenie kódu za určitých podmienok uvedených v licencii Apache 2.0.
- Stav projektu ako open-source: Projekt je skutočne open-source, toto označenie je však primárne určené na nekomerčné účely. Hoci podporujeme spoluprácu a príspevky komunity na výskum a nekomerčné aplikácie, je dôležité poznamenať, že akékoľvek využitie komponentov projektu na komerčné účely si vyžaduje samostatné licenčné zmluvy.
- Licencovanie údajov: Súvisiace údaje použité v našom projekte sú licencované pod CC BY-NC 4.0. Táto licencia výslovne povoľuje nekomerčné použitie údajov. Chceli by sme zdôrazniť, že akékoľvek modely vycvičené pomocou týchto súborov údajov by mali striktne dodržiavať obmedzenie nekomerčného použitia a mali by sa používať výlučne na výskumné účely.

## 🌟 Star Historia

[![Star History Chart](https://api.star-history.com/svg?repos=openbmb/chatdev&type=Date)](https://star-history.com/#openbmb/chatdev&Date)


## 🤝 Poďakovania
<a href="http://nlp.csai.tsinghua.edu.cn/"><img src="../misc/thunlp.png" height=50pt></a>&nbsp;&nbsp;
<a href="https://modelbest.cn/"><img src="../misc/modelbest.png" height=50pt></a>&nbsp;&nbsp;
<a href="https://github.com/OpenBMB/AgentVerse/"><img src="../misc/agentverse.png" height=50pt></a>&nbsp;&nbsp;
<a href="https://aibrb.com/introducing-herbie-your-super-employee-for-streamlined-productivity/"><img src="https://aibrb.com/wp-content/uploads/2023/09/Featured-on-AIBRB.com-white-1.png"  height=50pt></a>

## 📬 Kontakt

Ak máte akékoľvek otázky, spätnú väzbu alebo by ste nás chceli kontaktovať, neváhajte nás kontaktovať e-mailom na adrese [chatdev.openbmb@outlook.com](mailto:chatdev.openbmb@outlook.com)
