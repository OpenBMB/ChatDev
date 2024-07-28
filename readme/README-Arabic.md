# Communicative Agents for Software Development

<p align="center">
  <img src='../misc/logo1.png' width=550>
</p>

<p align="center">
    【📚 <a href="wiki.md">الويكي</a> | 🚀 <a href="wiki.md#visualizer">عرض محلي</a> | 👥 <a href="Contribution.md">برامج تم تطويرها من قبل المجتمع</a> | 🔧 <a href="wiki.md#customization">تخصيص</a>】
</p>

## 📖 نظرة عامة

- **ChatDev** هي **شركة برمجيات افتراضية** تعمل من خلال مجموعة متنوعة من **وكلاء ذكيين** يشغلون
  أدوارًا مختلفة، بما في ذلك المدير التنفيذي الرئيسي <img src='../visualizer/static/figures/ceo.png' height=20>، المدير التنفيذي للمنتج <img src='../visualizer/static/figures/cpo.png' height=20>، المدير التنفيذي للتكنولوجيا <img src='../visualizer/static/figures/cto.png' height=20>، مبرمج <img src='../visualizer/static/figures/programmer.png' height=20>، مراجع <img src='../visualizer/static/figures/reviewer.png' height=20>، اختبار <img src='../visualizer/static/figures/tester.png' height=20>، مصمم فني <img src='../visualizer/static/figures/designer.png' height=20>. تشكل هؤلاء
  الوكلاء هيكل تنظيمي متعدد الوكلاء وموحد من خلال مهمة "ثورة عالم البرمجة الرقمي". يتعاون وكلاء ChatDev
  من خلال المشاركة في ندوات وظيفية متخصصة، بما في ذلك مهام التصميم والبرمجة والاختبار والتوثيق.
- الهدف الرئيسي لـ ChatDev هو تقديم إطار عمل سهل الاستخدام، قابل للتخصيص بشكل كبير وقابل للتوسيع،
  والذي يعتمد على نماذج لغوية كبيرة (LLMs) ويعتبر سيناريو مثالي لدراسة الذكاء الجماعي.

<p align="center">
  <img src='../misc/company.png' width=600>
</p>

## 🎉 أخبار

- **26 أكتوبر 2023: تم دعم ChatDev الآن بواسطة Docker للتنفيذ الآمن** (بفضل مساهمة من [ManindraDeMel](https://github.com/ManindraDeMel)). يرجى الرجوع إلى [دليل بدء Docker](../wiki.md#docker-start).
  <p align="center">
  <img src='../misc/docker.png' width=400>
  </p>
- 25 سبتمبر 2023: وضع **Git** متاح الآن، مما يتيح للمبرمج <img src='../visualizer/static/figures/programmer.png' height=20> استخدام Git لمراقبة الإصدار. لتمكين هذه الميزة، قم ببساطة بتعيين ``"git_management"`` إلى ``"True"`` في ``ChatChainConfig.json``. راجع [الدليل](../wiki.md#git-mode).
  <p align="center">
  <img src='../misc/github.png' width=600>
  </p>
- 20 سبتمبر 2023: وضع **تفاعل الإنسان مع الوكيل** متاح الآن! يمكنك المشاركة مع فريق ChatDev من خلال لعب دور المراجع <img src='../visualizer/static/figures/reviewer.png' height=20> وتقديم اقتراحات للمبرمج <img src='../visualizer/static/figures/programmer.png' height=20>;
  جرب ``python3 run.py --task [وصف فكرتك] --config "Human"``. راجع [الدليل](../wiki.md#human-agent-interaction) و[المثال](../WareHouse/Gomoku_HumanAgentInteraction_20230920135038).
  <p align="center">
  <img src

='../misc/Human_intro.png' width=600>
  </p>
- 1 سبتمبر 2023: وضع **الفن** متاح الآن! يمكنك تنشيط وكيل المصمم <img src='../visualizer/static/figures/designer.png' height=20> لإنشاء صور تستخدم في البرمجيات;
  جرب ``python3 run.py --task [وصف فكرتك] --config "Art"``. راجع [الدليل](../wiki.md#art) و[المثال](../WareHouse/gomokugameArtExample_THUNLP_20230831122822).
- 28 أغسطس 2023: النظام متاح الآن للجمهور.
- 17 أغسطس 2023: الإصدار v1.0.0 كان جاهزًا للإصدار.
- 30 يوليو 2023: يمكن للمستخدمين تخصيص إعدادات ChatChain و Phase و Role. بالإضافة إلى ذلك، يتم دعم وضع السجل الأونلاين ووضع الاستعادة
  الآن.
- 16 يوليو 2023: تم نشر [ورقة مسبقة الطبع](https://arxiv.org/abs/2307.07924) مرتبطة بهذا المشروع.
- 30 يونيو 2023: تم إصدار النسخة الأولية من مستودع ChatDev.

## ❓ ماذا يمكن أن يفعل ChatDev؟

![intro](../misc/intro.png)

<https://github.com/OpenBMB/ChatDev/assets/11889052/80d01d2f-677b-4399-ad8b-f7af9bb62b72>

## ⚡️ بدء سريع

### 🖥️ بدء سريع باستخدام الطرفية

للبدء، اتبع هذه الخطوات:

1. **استنساخ مستودع GitHub:** ابدأ بنسخ المستودع باستخدام الأمر:

   ```

   git clone <https://github.com/OpenBMB/ChatDev.git>

   ```

2. **إعداد بيئة Python:** تأكد من وجود بيئة Python بإصدار 3.9 أو أعلى. يمكنك إنشاء هذه البيئة وتفعيلها باستخدام الأوامر التالية، مستبدلًا "ChatDev_conda_env" بالاسم المفضل لبيئتك:

   ```

   conda create -n ChatDev_conda_env python=3.9 -y
   conda activate ChatDev_conda_env

   ```

3. **تثبيت التبعيات:** انتقل إلى دليل "ChatDev" وقم بتثبيت التبعيات اللازمة بتشغيل:

   ```

   cd ChatDev
   pip3 install -r requirements.txt

   ```

4. **تعيين مفتاح واجهة برمجة التطبيقات (API) الخاص بـ OpenAI:** قم بتصدير مفتاح واجهة برمجة التطبيقات (API) الخاص بك كمتغير بيئي. استبدل "your_OpenAI_API_key" بمفتاح API الفعلي الخاص بك. تذكر أن هذا المتغير البيئي محدد لجلسة معينة، لذا يجب عليك ضبطه مرة أخرى إذا قمت بفتح جلسة طرفية جديدة.
   على نظام Unix/Linux:

   ```

   export OPENAI_API_KEY="your_OpenAI_API_key"

   ```

   على نظام Windows:

   ```

   $env:OPENAI_API_KEY="your_OpenAI_API_key"

   ```

5. **بناء برمجياتك:** استخدم الأمر التالي لبدء بناء برمجياتك، مستبدلًا "[وصف فكرتك]" بوصف فكرتك و"[اسم المشروع]" بالمشروع المطلوب:
   على نظام Unix/Linux:

   ```

   python3 run.py --task "[وصف فكرتك]" --name "[اسم المشروع]"

   ```

   على نظام Windows:

   ```

   python run.py --task "[وصف فكرتك]" --name "[اسم المشروع]"

   ```

6. **تشغيل البرمجيات الخاصة بك:** بمجرد إنشاءها، يمكنك العثور على برمجياتك في دليل "WareHouse" تحت مجلد مشروع معين، مثل "project_name_DefaultOrganization_timestamp". قم بتشغيل البرمجيات باستخدام الأمر التالي داخل ذلك الدليل:
   على نظام Unix/Linux:

   ```

   cd WareHouse/project_name_DefaultOrganization_timestamp
   python3 main.py

   ```

   على نظام Windows:

   ```

   cd WareHouse/project_name_DefaultOrganization_timestamp
   python main.py

   ```

### 🐳 بدء سريع باستخدام Docker

- نشكر [ManindraDeMel](https://github.com/ManindraDeMel) على دعم Docker. يرجى الرجوع إلى [دليل بدء Docker](../wiki.md#docker-start).

## ✨️ مهارات متقدمة

لمزيد من المعلومات التفصيلية، يرجى الرجوع إلى [ويكي](../wiki.md) لدينا، حيث يمكنك العثور على:

- مقدمة إلى جميع معلمات تشغيل الأوامر.
- دليل مباشر لإعداد عرض ويب محلي، يشمل سجلات مرئية محسنة وعرض تكراري وأداة بصرية بسيطة لـ ChatChain.
- نظرة عامة على إطار ChatDev.
- مقدمة شاملة لجميع المعلمات المتقدمة في تكوين ChatChain.
- دلائل لتخصيص ChatDev، بما في ذلك:
  - ChatChain: قم بتصميم عملية تطوير البرمجيات الخاصة بك (أو أي عملية أخرى)، مثل "DemandAnalysis -> Coding -> Testing -> Manual".
  - Phase: قم بتصميم مرحلة خاصة بك ضمن ChatChain، مثل "DemandAnalysis".
  - Role: حدد مختلف الوكلاء في شركتك، مثل "الرئيس التنفيذي".

## 🤗 شارك ببرمجياتك

**الكود**: نحن متحمسون لاهتمامك بالمشاركة في مشروعنا مفتوح المصدر. إذا واجهت أي مشاكل، فلا تتردد في الإبلاغ عنها. لا تتردد في إنشاء طلب استدراج إذا كان لديك أي استفسارات أو إذا كنت مستعدًا لمشاركة عملك معنا! تقديرنا الكبير لمساهماتك. يرجى إعلامي إذا كان هناك أي شيء آخر تحتاجه!

**الشركة**: إنشاء "شركة ChatDev" المخصصة الخاصة بك أمر سهل. يتضمن هذا الإعداد الشخصي ثلاثة ملفات JSON تكوينية بسيطة. تحقق من المثال المقدم في دليل "CompanyConfig/Default". للتعليمات التفصيلية حول التخصيص، يرجى الرجوع إلى [ويكي](../wiki.md) لدينا.

**البرمجيات**: في كل مرة تطوّر فيها برمجيات باستخدام ChatDev، يتم إنشاء مجلد مقابل يحتوي على جميع المعلومات الأساسية. مشاركة عملك معنا بسيطة مثل إنشاء طلب استدراج. إليك مثال: قم بتنفيذ الأمر "python3 run.py --task 'تصميم لعبة 2048' --name '2048' --org 'THUNLP' --config 'Default'". سيتم بذلك إنشاء حزمة برمجية وإنشاء مجلد بالاسم "/WareHouse/2048_THUNLP_timestamp". بداخله، ستجد:

- جميع الملفات والوثائق المتعلقة ببرمجية لعبة 2048
- ملفات تكوين الشركة المسؤولة عن هذه البرمجية، بما في ذلك ثلاث ملفات تكوين JSON من "CompanyConfig/Default"
- سجل شامل يوثق عملية بناء البرمجية يمكن استخدامه للعب المسجل (timestamp.log)
- الاستفهام الأولي المستخدم لإنشاء هذه البرمجية (2048.prompt)

**راجع البرمجيات المساهمة من قبل المجتمع [هنا](../Contribution.md)!**

## 👨‍💻‍ مساهمون

<a href="https://github.com/OpenBMB/ChatDev/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=OpenBMB/ChatDev" />
</a>

صُنع بواسطة [contrib.rocks](https://contrib.rocks).

## 🔎 الاقتباس

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

## ⚖️ الترخيص

- ترخيص الشفرة المصدرية: تخضع شفرة مصدر مشروعنا لترخيص Apache 2.0. هذا الترخيص يسمح باستخدام وتعديل وتوزيع الشفرة، بشرط الامتثال لبعض الشروط المحددة في ترخي

ص Apache 2.0.

- ترخيص البيانات: البيانات ذات الصلة المستخدمة في مشروعنا مرخصة بموجب CC BY-NC 4.0. يسمح هذا الترخيص صراحة باستخدام البيانات لأغراض غير تجارية. نحن نود التأكيد على أن أي نماذج تم تدريبها باستخدام هذه البيانات يجب أن تلتزم صارمًا بقيود الاستخدام غير التجاري ويجب استخدامها حصرًا لأغراض البحث.

## 🤝 الشكر
<a href="http://nlp.csai.tsinghua.edu.cn/"><img src="../misc/thunlp.png" height=50pt></a>&nbsp;&nbsp;
<a href="https://modelbest.cn/"><img src="../misc/modelbest.png" height=50pt></a>&nbsp;&nbsp;
<a href="https://github.com/OpenBMB/AgentVerse/"><img src="../misc/agentverse.png" height=50pt></a>&nbsp;&nbsp;
<a href="https://aibrb.com/introducing-herbie-your-super-employee-for-streamlined-productivity/"><img src="https://aibrb.com/wp-content/uploads/2023/09/Featured-on-AIBRB.com-white-1.png"  height=50pt></a>

## 📬 اتصل بنا

إذا كان لديك أي أسئلة أو تعليقات أو ترغب في التواصل معنا، فلا تتردد في الوصول إلينا عبر البريد الإلكترون [qianc62@gmail.com](mailto:qianc62@gmail.com)
