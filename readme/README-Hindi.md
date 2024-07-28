# Communicative Agents for Software Development

<p align="center">
  <img src='../misc/logo1.png' width=550>
</p>


<p align="center">
    【📚 <a href="../wiki.md">विकि</a> | 🚀 <a href="../wiki.md#visualizer">स्थानीय डेमो</a> | 👥 <a href="../Contribution.md">समुदाय निर्मित सॉफ्टवेयर</a> | 🔧 <a href="../wiki.md#customization">अनुकूलन</a>】
</p>

## 📖 Overview

- **ChatDev** एक **वर्चुअल सॉफ्टवेयर कंपनी** के रूप में खड़ी है जो विभिन्न **बुद्धिमान एजेंटों** होल्डिंग के माध्यम से संचालित होता है|
  मुख्य कार्यकारी अधिकारी सहित विभिन्न भूमिकाएँ <img src='../visualizer/static/figures/ceo.png' height=20>, मुख्य उत्पाद अधिकारी <img src='../visualizer/static/figures/cpo.png' height=20>, मुख्य तकनीकी अधिकारी <img src='../visualizer/static/figures/cto.png' height=20>, प्रोग्रामर <img src='../visualizer/static/figures/programmer.png' height=20>, reviewer <img src='../visualizer/static/figures/reviewer.png' height=20>, टेस्टर <img src='../visualizer/static/figures/tester.png' height=20>, कला डिजाइनर <img src='../visualizer/static/figures/designer.png' height=20>. इन
   एजेंट एक बहु-एजेंट संगठनात्मक संरचना बनाते हैं और "डिजिटल दुनिया में क्रांति लाने" के मिशन से एकजुट होते हैं
   प्रोग्रामिंग के माध्यम से।" ChatDev के एजेंट विशेष कार्यात्मक सेमिनारों में भाग लेकर **सहयोग** करते हैं,
   जिसमें डिज़ाइनिंग, कोडिंग, परीक्षण और दस्तावेज़ीकरण जैसे कार्य शामिल हैं।
- चैटडेव का प्राथमिक उद्देश्य **उपयोग में आसान**, **अत्यधिक अनुकूलन योग्य** और **विस्तार योग्य** ढांचा पेश करना है।
   जो बड़े भाषा मॉडल (एलएलएम) पर आधारित है और सामूहिक बुद्धि का अध्ययन करने के लिए एक आदर्श परिदृश्य के रूप में कार्य करता है।
<p align="center">
  <img src='../misc/company.png' width=600>
</p>

## 🎉 News

* **25 सितंबर, 2023: **गिट** सुविधा अब उपलब्ध है**, जो प्रोग्रामर को सक्षम बनाती है <img src='../visualizer/static/figures/programmer.png' height=20> संस्करण नियंत्रण के लिए GitHub का उपयोग करना। इस सुविधा को सक्षम करने के लिए, बस सेट करें ``"git_management"`` को  ``"True"`` में ``ChatChainConfig.json``.
  <p align="center">
  <img src='../misc/github.png' width=600>
  </p>
* 20 सितंबर, 2023: **ह्यूमन-एजेंट-इंटरैक्शन** मोड अब उपलब्ध है! आप समीक्षक की भूमिका निभाकर ChatDev टीम से जुड़ सकते हैं <img src='../visualizer/static/figures/reviewer.png' height=20> और प्रोग्रामर को सुझाव देना <img src='../visualizer/static/figures/programmer.png' height=20>;
  कोशिश ``python3 run.py --task [आपके_विचार_का_वर्णन] --config "Human"``. देखना [मार्गदर्शक](../wiki.md#human-agent-interaction) and [उदाहरण](../WareHouse/Gomoku_HumanAgentInteraction_20230920135038).
  <p align="center">
  <img src='../misc/Human_intro.png' width=600>
  </p>
* 1 सितंबर, 2023: **कला** मोड अब उपलब्ध है! आप डिज़ाइनर एजेंट को सक्रिय कर सकते हैं <img src='../visualizer/static/figures/designer.png' height=20> सॉफ़्टवेयर में प्रयुक्त छवियाँ उत्पन्न करने के लिए;
  कोशिश ``python3 run.py --task [आपके_विचार_का_वर्णन] --config "Art"``. देखना [मार्गदर्शक](../wiki.md#art) and [उदाहरण](../WareHouse/gomokugameArtExample_THUNLP_20230831122822).
* 28 अगस्त, 2023: सिस्टम सार्वजनिक रूप से उपलब्ध है।
* 17 अगस्त, 2023: v1.0.0 संस्करण रिलीज़ के लिए तैयार था।
* 30 जुलाई, 2023: उपयोगकर्ता चैटचेन, चरण और भूमिका सेटिंग्स को अनुकूलित कर सकते हैं। इसके अतिरिक्त, ऑनलाइन लॉग मोड और रीप्ले दोनों
  मोड अब समर्थित हैं.
* 16 जुलाई, 2023: [प्रीप्रिंट पेपर](https://arxiv.org/abs/2307.07924) इस परियोजना से सम्बंधित प्रकाशित किया गया था।
* 30 जून, 2023: ChatDev रिपॉजिटरी का प्रारंभिक संस्करण जारी किया गया।

## ❓ ChatDev क्या कर सकता है?

![परिचय](../misc/intro.png)

https://github.com/OpenBMB/ChatDev/assets/11889052/80d01d2f-677b-4399-ad8b-f7af9bb62b72

## ⚡️ जल्दी शुरू

आरंभ करने के लिए, इन चरणों का पालन करें:

1. **गिटहब रिपॉजिटरी को क्लोन करें:** कमांड का उपयोग करके रिपॉजिटरी को क्लोन करके शुरू करें:
   ```
   git clone https://github.com/OpenBMB/ChatDev.git
   ```
2. **पायथन पर्यावरण सेट करें:** सुनिश्चित करें कि आपके पास संस्करण 3.9 या उच्चतर पायथन वातावरण है। आप बना सकते हैं और
    निम्नलिखित कमांड का उपयोग करके इस वातावरण को सक्रिय करें, `ChatDev_conda_env` को अपने पसंदीदा वातावरण से बदलें
    नाम:
   ```
   conda create -n ChatDev_conda_env python=3.9 -y
   conda activate ChatDev_conda_env
   ```
3. **निर्भरताएँ स्थापित करें:** `ChatDev` निर्देशिका में जाएँ और चलाकर आवश्यक निर्भरताएँ स्थापित करें:
   ```
   cd ChatDev
   pip3 install -r requirements.txt
   ```
4. **OpenAI API कुंजी सेट करें:** अपनी OpenAI API कुंजी को एक पर्यावरण चर के रूप में निर्यात करें। `"your_OpenAI_API_key"` को इसके साथ बदलें
    आपकी वास्तविक एपीआई कुंजी। याद रखें कि यह पर्यावरण चर सत्र-विशिष्ट है, इसलिए यदि आपको इसे फिर से सेट करना होगा
    एक नया टर्मिनल सत्र खोलें.
    यूनिक्स/लिनक्स पर:
   ```
   export OPENAI_API_KEY="your_OpenAI_API_key"
   ```
   विंडोज़ पर:
   ```
   $env:OPENAI_API_KEY="your_OpenAI_API_key"
   ```
5. **अपना सॉफ़्टवेयर बनाएं:** अपने सॉफ़्टवेयर का निर्माण शुरू करने के लिए निम्नलिखित कमांड का उपयोग करें,
    `[आपके_विचार_का_वर्णन]` को अपने विचार के विवरण से और `[परियोजना_का_नाम]` को अपने इच्छित प्रोजेक्ट से बदलें
    नाम:
    यूनिक्स/लिनक्स पर:
   ```
   python3 run.py --task "[आपके_विचार_का_वर्णन]" --name "[परियोजना_का_नाम]"
   ```
   विंडोज़ पर:
   ```
   python run.py --task "[आपके_विचार_का_वर्णन]" --name "[परियोजना_का_नाम]"
   ```
6. **अपना सॉफ़्टवेयर चलाएँ:** एक बार जेनरेट होने के बाद, आप अपना सॉफ़्टवेयर एक विशिष्ट के अंतर्गत `वेयरहाउस` निर्देशिका में पा सकते हैं
    प्रोजेक्ट फ़ोल्डर, जैसे `project_name_DefaultOrganization_timestamp`. निम्नलिखित कमांड का उपयोग करके अपना सॉफ़्टवेयर चलाएँ
    उस निर्देशिका के भीतर:
    यूनिक्स/लिनक्स पर:
   ```
   cd WareHouse/project_name_DefaultOrganization_timestamp
   python3 main.py
   ```
   विंडोज़ पर:
   ```
   cd WareHouse/project_name_DefaultOrganization_timestamp
   python main.py
   ```

## ✨️ उन्नत कौशल

अधिक विस्तृत जानकारी के लिए कृपया हमारा संदर्भ लें [विकि](../wiki.md), आप कहां पा सकते हैं:

- सभी कमांड रन पैरामीटर का परिचय।
- स्थानीय वेब डेमो स्थापित करने के लिए एक सीधी मार्गदर्शिका, जिसमें उन्नत विज़ुअलाइज़्ड लॉग, एक रीप्ले डेमो और शामिल हैं
  सरल चैटचेन विज़ुअलाइज़र।
- चैटदेव ढांचे का अवलोकन।
- चैटचेन कॉन्फ़िगरेशन में सभी उन्नत मापदंडों का व्यापक परिचय।
- ChatDev को अनुकूलित करने के लिए मार्गदर्शिकाएँ, जिनमें शामिल हैं:
    - चैटचेन: अपनी स्वयं की सॉफ़्टवेयर विकास प्रक्रिया (या कोई अन्य प्रक्रिया) डिज़ाइन करें
       ``डिमांडएनालिसिस -> कोडिंग -> टेस्टिंग -> मैनुअल`` के रूप में।
    - चरण: चैटचेन के भीतर अपना स्वयं का चरण डिज़ाइन करें, जैसे ``डिमांडएनालिसिस``
    - भूमिका: आपकी कंपनी में विभिन्न एजेंटों को परिभाषित करना, जैसे ``मुख्य कार्यकारी अधिकारी``

## 🤗 अपना सॉफ़्टवेयर साझा करें!

**कोड**: हम हमारे ओपन-सोर्स प्रोजेक्ट में भाग लेने में आपकी रुचि को लेकर उत्साहित हैं। यदि आपको कोई मिलता है
समस्याएँ, उन्हें रिपोर्ट करने में संकोच न करें। यदि आपके पास कोई पूछताछ है या आप हैं तो बेझिझक एक पुल अनुरोध बनाएं
अपना काम हमारे साथ साझा करने के लिए तैयार हैं! आपका योगदान अत्यधिक मूल्यवान है. कृपया मुझे बताएं कि क्या कुछ और है
आपको सहायता की आवश्यकता है!

**कंपनी**: अपनी स्वयं की अनुकूलित "चैटडेव कंपनी" बनाना बहुत आसान है। इस वैयक्तिकृत सेटअप में तीन सरल शामिल हैं
कॉन्फ़िगरेशन JSON फ़ाइलें। ``CompanyConfig/Default`` निर्देशिका में दिए गए उदाहरण को देखें। विस्तृत के लिए
अनुकूलन पर निर्देश, हमारा संदर्भ लें [विकि](../wiki.md).

**सॉफ़्टवेयर**: जब भी आप चैटडेव का उपयोग करके सॉफ़्टवेयर विकसित करते हैं, तो एक संबंधित फ़ोल्डर उत्पन्न होता है जिसमें सभी शामिल होते हैं
आवश्यक जानकारी। अपना काम हमारे साथ साझा करना पुल अनुरोध करने जितना ही सरल है। यहाँ एक उदाहरण है: निष्पादित करें
कमांड ``python3 run.py --task "डिज़ाइन ए 2048 गेम" --नाम "2048" --org "THUNLP" --config "डिफ़ॉल्ट"``। यह करेगा
एक सॉफ़्टवेयर पैकेज बनाएं और ``/WareHouse/2048_THUNLP_timestamp`` नाम का एक फ़ोल्डर बनाएं। अंदर, आप पाएंगे:

- 2048 गेम सॉफ़्टवेयर से संबंधित सभी फ़ाइलें और दस्तावेज़
- इस सॉफ़्टवेयर के लिए ज़िम्मेदार कंपनी की कॉन्फ़िगरेशन फ़ाइलें, जिनमें तीन JSON कॉन्फ़िगरेशन फ़ाइलें शामिल हैं
   ``CompanyConfig/Default`` से
- सॉफ़्टवेयर की निर्माण प्रक्रिया का विवरण देने वाला एक व्यापक लॉग जिसका उपयोग पुनः चलाने के लिए किया जा सकता है (``timestamp.log``)
- इस सॉफ़्टवेयर को बनाने के लिए उपयोग किया जाने वाला प्रारंभिक प्रॉम्प्ट (``2048.prompt``)

**समुदाय द्वारा योगदान किया गया सॉफ़्टवेयर देखें [यहाँ](../Contribution.md)!**

## 👨‍💻‍ सॉफ्टवेयर योगदानकर्ता

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

## 🔎 उद्धरण

```
@misc{qian2023communicative,
      title={Communicative Agents for Software Development}, 
      author={Chen Qian and Xin Cong and Wei Liu and Cheng Yang and Weize Chen and Yusheng Su and Yufan Dang and Jiahao Li and Juyuan Xu and Dahai Li and Zhiyuan Liu and Maosong Sun},
      year={2023},
      eprint={2307.07924},
      archivePrefix={arXiv},
      primaryClass={cs.SE}
}

@misc{qian2023experiential,
      title={Experiential Co-Learning of Software-Developing Agents}, 
      author={Chen Qian and Yufan Dang and Jiahao Li and Wei Liu and Weize Chen and Cheng Yang and Zhiyuan Liu and Maosong Sun},
      year={2023},
      eprint={2312.17025},
      archivePrefix={arXiv},
      primaryClass={cs.CL}
}
```

## ⚖️ लाइसेंस

- सोर्स कोड लाइसेंसिंग: हमारे प्रोजेक्ट का सोर्स कोड अपाचे 2.0 लाइसेंस के तहत लाइसेंस प्राप्त है। यह लाइसेंस अपाचे 2.0 लाइसेंस में उल्लिखित कुछ शर्तों के अधीन, कोड के उपयोग, संशोधन और वितरण की अनुमति देता है।
- डेटा लाइसेंसिंग: हमारे प्रोजेक्ट में उपयोग किया गया संबंधित डेटा CC BY-NC 4.0 के तहत लाइसेंस प्राप्त है। यह लाइसेंस स्पष्ट रूप से डेटा के गैर-व्यावसायिक उपयोग की अनुमति देता है। हम इस बात पर जोर देना चाहेंगे कि इन डेटासेट का उपयोग करके प्रशिक्षित किसी भी मॉडल को गैर-व्यावसायिक उपयोग प्रतिबंध का सख्ती से पालन करना चाहिए और विशेष रूप से अनुसंधान उद्देश्यों के लिए नियोजित किया जाना चाहिए।



## 🤝 स्वीकृतियाँ
<a href="http://nlp.csai.tsinghua.edu.cn/"><img src="../misc/thunlp.png" height=50pt></a>&nbsp;&nbsp;
<a href="https://modelbest.cn/"><img src="../misc/modelbest.png" height=50pt></a>&nbsp;&nbsp;
<a href="https://github.com/OpenBMB/AgentVerse/"><img src="../misc/agentverse.png" height=50pt></a>&nbsp;&nbsp;
<a href="https://aibrb.com/introducing-herbie-your-super-employee-for-streamlined-productivity/"><img src="https://aibrb.com/wp-content/uploads/2023/09/Featured-on-AIBRB.com-white-1.png"  height=50pt></a>

## 📬 संपर्क

यदि आपके पास कोई प्रश्न, प्रतिक्रिया है, या संपर्क करना चाहते हैं, तो कृपया बेझिझक हमें ईमेल के माध्यम से संपर्क करें [qianc62@gmail.com](mailto:qianc62@gmail.com)
