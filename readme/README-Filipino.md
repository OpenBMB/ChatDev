# Communicative Agents for Software Development

<p align="center">
  <img src='../misc/logo1.png' width=550>
</p>


<p align="center">
    【📚 <a href="../wiki.md">Wiki</a> | 🚀 <a href="../wiki.md#local-demo">Lokal na Demo</a> | 👥 <a href="../Contribution.md">Komunidad ng Kontribusyon sa Software</a> | 🔧 <a href="../wiki.md#customization">Kostomisasyon</a>】
</p>

## 📖 Pangkalahatan

- Ang **ChatDev** ay isang **birtwal na kumpanya ng software** na nag-ooperate sa pamamagitan ng iba't-ibang **matalinong ahente** na may iba't-ibang mga papel, kabilang ang Chief Executive Officer <img src='../online_log/static/figures/ceo.png' height=20>, Chief Product Officer <img src='../online_log/static/figures/cpo.png' height=20>, Chief Technology Officer <img src='../online_log/static/figures/cto.png' height=20>, programmer <img src='../online_log/static/figures/programmer.png' height=20>, reviewer <img src='../online_log/static/figures/reviewer.png' height=20>, tester <img src='../online_log/static/figures/tester.png' height=20>, at art designer <img src='../online_log/static/figures/designer.png' height=20>. Ang mga ahente na ito ay bumubuo ng isang multi-agent na istruktura ng organisasyon at nagkakaisa sa isang misyon na "baguhin ang digital na mundo sa pamamagitan ng programming." Ang mga ahente sa loob ng ChatDev ay **nagkakaisa** sa pamamagitan ng pagsali sa mga espesyalisadong seminar na may mga gawain tulad ng pagdi-disenyo, pagko-coding, pagte-test, at pagsusuri.
- Ang pangunahing layunin ng ChatDev ay mag-alok ng isang **madaling gamitin**, **mabilis ma-customize**, at **napapalawak** na framework, na batay sa malalaking modelo ng wika (LLMs) at naglilingkod bilang isang ideal na scenario para pag-aralan ang kolektibong kaalaman.

<p align="center">
  <img src='../misc/company.png' width=600>
</p>

## 📰 Balita

* **Setyembre 25, 2023: Ang **Git** na feature ay available na**, nagbibigay-daan sa programmer <img src='../online_log/static/figures/programmer.png' height=20> na gamitin ang GitHub para sa version control. Upang paganahin ang feature na ito, i-set ang ``"git_management"`` sa ``"True"`` sa ``ChatChainConfig.json``.
  <p align="center">
  <img src='../misc/github.png' width=600>
  </p>
* Setyembre 20, 2023: Ang **Human-Agent-Interaction** mode ay available na! Maaari kang makilahok sa ChatDev team sa pamamagitan ng pagganap ng papel ng reviewer <img src='../online_log/static/figures/reviewer.png' height=20> at pagbibigay ng mga suhestiyon sa programmer <img src='../online_log/static/figures/programmer.png' height=20>; subukan ang ``python3 run.py --task [description_ng_ideya_mo] --config "Human"``. Tingnan ang [gabay](../wiki.md#human-agent-interaction) at [halimbawa](../WareHouse/Gomoku_HumanAgentInteraction_20230920135038).
  <p align="center">
  <img src='../misc/Human_intro.png' width=600>
  </p>
* Setyembre 1, 2023: Ang **Art** mode ay available na! Maaari mong paganahin ang ahenteng designer <img src='../online_log/static/figures/designer.png' height=20> upang lumikha ng mga imahe na ginagamit sa software; subukan ang ``python3 run.py --task [description_ng_ideya_mo] --config "Art"``. Tingnan ang [gabay](../wiki.md#art) at [halimbawa](../WareHouse/gomokugameArtExample_THUNLP_20230831122822).
* Agosto 28, 2023: Ang sistema ay magagamit na ng publiko.
* Agosto 17, 2023: Ang bersyon v1.0.0 ay handa na para ilabas.
* Hulyo 30, 2023: Maaaring baguhin ng mga user ang mga ChatChain, Phase, at Role settings. Bukod dito, sinusuportahan na rin ang online Log mode at replay mode.
* Hulyo 16, 2023: Ang [preprint na papel](https://arxiv.org/abs/2307.07924) na nauugnay sa proyektong ito ay nailathala.
* Hunyo 30, 2023: Inilabas ang unang bersyon ng repository ng ChatDev.

## ❓ Ano ang Kayang Gawin ng ChatDev?

![intro](../misc/intro.png)

https://github.com/OpenBMB/ChatDev/assets/11889052/80d01d2f-677b-4399-ad8b-f7af9bb62b72

## ⚡️ Mabilis na Pagsisimula

Upang magsimula, sundan ang mga hakbang na ito:

1. **I-Clone ang GitHub Repository:** Simulan sa pamamagitan ng pagkopya ng repository gamit ang command:
```
git clone https://github.com/OpenBMB/ChatDev.git
```

2. **I-set Up ang Python Environment:** Siguruhing mayroon kang Python environment na bersyon 3.9 o mas mataas. Maaari mong lumikha at paganahin ang environment na ito gamit ang mga sumusunod na command, pinalitan ang `ChatDev_conda_env` ng iyong napipiling pangalan ng environment:
```
conda create -n ChatDev_conda_env python=3.9 -y
conda activate ChatDev_conda_env
```

3. **I-install ang mga Kinakailangang Dependencies:** Pumunta sa direktoryo ng `ChatDev` at i-install ang mga kinakailangang dependencies sa pamamagitan ng pagtakbo ng:
```
cd ChatDev
pip3 install -r requirements.txt
```

4. **I-set ang OpenAI API Key:** I-export ang iyong OpenAI API key bilang isang environment variable. Palitan ang `"iyong_OpenAI_API_key"` ng iyong tunay na API key. Tandaan na ang environment variable na ito ay session-specific, kaya't kailangan mong iset ito ulit kung bubuksan mo ang isang bagong session ng terminal.
Sa Unix/Linux:
```
export OPENAI_API_KEY="iyong_OpenAI_API_key"
```
Sa Windows:
```
$env:OPENAI_API_KEY="iyong_OpenAI_API_key"
```

5. **Buoin ang Iyong Software:** Gamitin ang sumusunod na command upang simulan ang pagbuo ng iyong software, pinalitan ang `[description_ng_ideya_mo]` ng deskripsyon ng iyong ideya at `[project_name]` ng iyong napipiling pangalan ng proyekto:
```
Sa Unix/Linux:
python3 run.py --task "[description_ng_ideya_mo]" --name "[project_name]"
```
Sa Windows:
```
python run.py --task "[description_ng_ideya_mo]" --name "[project_name]"
```

6. **I-takbo ang Iyong Software:** Kapag nailikha na, maaari mong hanapin ang iyong software sa direktoryo ng `WareHouse` sa ilalim ng isang partikular na folder ng proyekto, tulad ng `project_name_DefaultOrganization_timestamp`. I-takbo ang iyong software gamit ang sumusunod na command sa loob ng direktoryong iyon:
Sa Unix/Linux:
```
cd WareHouse/project_name_DefaultOrganization_timestamp
python3 main.py
```
Sa Windows:
```
cd WareHouse/project_name_DefaultOrganization_timestamp
python main.py
```

## ✨️ Adbans na Kakayahan

Para sa mas detalyadong impormasyon, mangyaring tingnan ang aming [Wiki](../wiki.md), kung saan maaari mong mahanap:

- Isang introduksyon sa lahat ng mga parameter ng command run.
- Isang simpleng guide para sa pag-set up ng isang lokal na web demo, kabilang ang pinabuting mga visualized logs, isang replay demo, at isang simpleng ChatChain Visualizer.
- Isang pagsusuri ng framework ng ChatDev.
- Isang kumprehensibong introduksyon sa lahat ng mga advanced na parameter sa ChatChain configuration.
- Mga gabay para sa pagsasapanlipunan ng ChatDev, kabilang ang:
 - ChatChain: Mag-disenyo ng iyong sariling proseso sa pagpapaunlad ng software (o anumang ibang proseso), tulad ng ``DemandAnalysis -> Coding -> Testing -> Manual``.
 - Yugto: Mag-disenyo ng iyong sariling yugto sa loob ng ChatChain, tulad ng ``DemandAnalysis``.
 - Bahagi: Paghahanap ng iba't-ibang mga ahente sa iyong kumpanya, tulad ng ``Chief Executive Officer``.

## 🤗 Ibahagi ang Iyong Software!

**Code**: Nais naming malaman na nais mong makilahok sa aming proyektong open-source. Kung mayroon kang natuklasang mga problema, huwag kang mag-atubiling ireport ang mga ito. Mag-create ng pull request kung mayroon kang mga tanong o kung handa kang ibahagi ang iyong trabaho sa amin! Lubos naming pinahahalagahan ang iyong mga kontribusyon. Mangyaring ipaalam sa amin kung mayroon kang iba pang pangangailangan!

**Kumpanya**: Ang paglikha ng iyong sariling "Kompanya ng ChatDev" ay madali lamang. Ang personalisadong set-up na ito ay kinakailangan ng tatlong simpleng JSON configuration files. Tingnan ang halimbawa na ibinigay sa direktoryo ng ``CompanyConfig/Default``. Para sa detalyadong mga tagubilin sa pagsasapanlipunan, tingnan ang aming [Wiki](../wiki.md).

**Software**: Kapag nadevelop mo ang software gamit ang ChatDev, isang kaugnay na folder ay nalilikha na naglalaman ng lahat ng mga kinakailangan impormasyon. Ang pagbibigay ng iyong trabaho sa amin ay kasimplehan ng pag-create ng pull request. Narito ang isang halimbawa: i-execute ang command ``python3 run.py --task "magdisenyo ng 2048 game" --name "2048" --org "THUNLP" --config "Default"``. Ito ay lalikha ng isang software package at mag-generate ng isang folder na may pangalang ``/WareHouse/2048_THUNLP_timestamp``. Dito, makakakita ka ng:

- Lahat ng mga file at dokumento na may kaugnayan sa 2048 game software
- Configuration files ng kumpanyang responsable sa software na ito, kabilang ang tatlong JSON config files mula sa ``CompanyConfig/Default``
- Isang kumpletong log na nagdetalye ng proseso ng pagbuo ng software na maaaring gamitin sa replay (``timestamp.log``)
- Ang orihinal na prompt na ginamit upang lumikha ng software na ito (``2048.prompt``)

**Tingnan ang mga naambag na software ng komunidad [dito](../Contribution.md)!**

### Mga Kontribyutor ng Software

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

## 📑 Citation
```
@misc{qian2023communicative,
title={Komunikatibong mga Ahente para sa Pagpapaunlad ng Software},
author={Chen Qian at Xin Cong at Wei Liu at Cheng Yang at Weize Chen at Yusheng Su at Yufan Dang at Jiahao Li at Juyuan Xu at Dahai Li at Zhiyuan Liu at Maosong Sun},
year={2023},
eprint={2307.07924},
archivePrefix={arXiv},
primaryClass={cs.SE}
}
```

## ⚖️ Lisensya

- Lisensya ng Source Code: Ang source code ng aming proyekto ay may lisensyang Apache 2.0. Ito ay nagbibigay ng pahintulot sa paggamit, pagbabago, at pamamahagi ng code, sa ilalim ng ilang kondisyon na inilahad sa Apache 2.0 License.
- Estado ng Open-Source na Proyekto: Ang proyektong ito ay tunay na open-source; gayunpaman, ang designation na ito ay pangunahing para sa mga non-commercial na layunin. Habang inaanyayahan namin ang kolaborasyon at mga kontribusyon mula sa komunidad para sa pagsasaliksik at non-commercial na mga aplikasyon, mahalaga na tandaan na anumang paggamit ng mga bahagi ng proyekto para sa mga layunin ng negosyo ay nangangailangan ng mga hiwalay na kasunduang pang-lisensya.
- Lisensya ng Data: Ang kaugnay na datos na ginamit sa aming proyekto ay may lisensyang CC BY-NC 4.0. Ang lisensyang ito ay malinaw na nagpapahintulot sa non-commercial na paggamit ng data. Nais naming bigyang-diin na ang anumang mga modelo na naitrain gamit ang mga datasets na ito ay dapat na mahigpit na sumusunod sa restriction ng non-commercial usage at dapat gamitin lamang para sa layuning pananaliksik.

## Kasaysayan ng Stars

[![Star History Chart](https://api.star-history.com/svg?repos=openbmb/chatdev&type=Date)](https://star-history.com/#openbmb/chatdev&Date)

## Makipag-ugnay

Kung mayroon kang anumang mga tanong, puna, o nais makipag-ugnay, huwag kang mag-atubiling makipag-ugnay sa amin sa pamamagitan ng email sa [chatdev.openbmb@outlook.com](mailto:chatdev.openbmb@outlook.com)
