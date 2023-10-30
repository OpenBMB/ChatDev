# Communicative Agents for Software Development

<p align="center">
  <img src='../misc/logo1.png' width=550>
</p>

<p align="center">
    【İngilizce | <a href="readme/README-Chinese.md">Çince</a> | <a href="readme/README-Japanese.md">Japonca</a> | <a href="readme/README-Korean.md">Korece</a> | <a href="readme/README-Filipino.md">Filipince</a> | <a href="readme/README-French.md">Fransızca</a> | <a href="readme/README-Slovak.md">Slovakça</a> | <a href="readme/README-Portekizce.md">Portekizce</a> | <a href="readme/README-İspanyolca.md">İspanyolca</a> | <a href="readme/README-Hollanda.md">Hollandaca</a> | <a href="readme/README-Hintçe.md">Hintçe</a>】
</p>
<p align="center">
    【📚 <a href="wiki.md">Wiki</a> | 🚀 <a href="wiki.md#yerel-demo">Yerel Demo</a> | 👥 <a href="Katki.md">Topluluk Tarafından Geliştirilen Yazılım</a> | 🔧 <a href="wiki.md#özelleştirme">Özelleştirme</a>】
</p>

## 📖 Genel Bakış

- **ChatDev**, farklı rolleri olan çeşitli **akıllı ajanlar** aracılığıyla işleyen bir **sanal yazılım şirketi** olarak duruyor, bu roller arasında İcra Kurulu Başkanı <img src='../online_log/static/figures/ceo.png' height=20>, Baş Ürün Sorumlusu <img src='../online_log/static/figures/cpo.png' height=20>, Baş Teknoloji Sorumlusu <img src='../online_log/static/figures/cto.png' height=20>, programcı <img src='../online_log/static/figures/programmer.png' height=20>, inceleyici <img src='../online_log/static/figures/reviewer.png' height=20>, testçi <img src='../online_log/static/figures/tester.png' height=20>, sanat tasarımcısı <img src='../online_log/static/figures/designer.png' height=20> bulunur. Bu ajanlar çoklu ajan organizasyon yapısı oluşturur ve "programlama yoluyla dijital dünyayı devrimleştirmek" misyonuyla birleşirler. ChatDev içindeki ajanlar, özel işlevsel seminerlere katılarak işbirliği yaparlar, bu seminerler tasarım, kodlama, test etme ve belgeleme gibi görevleri içerir.
- ChatDev'in asıl amacı, büyük dil modellerine (LLM'ler) dayanan ve kolektif zeka çalışmaları için ideal bir senaryo olarak hizmet veren, **kullanımı kolay**, **yüksek özelleştirilebilir** ve **genişletilebilir** bir çerçeve sunmaktır.

<p align="center">
  <img src='../misc/company.png' width=600>
</p>

## 🎉 Haberler

- **26 Ekim 2023: ChatDev artık güvenli yürütme için Docker ile destekleniyor** (katkı sağlayan [ManindraDeMel](https://github.com/ManindraDeMel) sayesinde). Lütfen [Docker Başlangıç Kılavuzu'na](wiki.md#docker-start) bakınız.
  <p align="center">
  <img src='../misc/docker.png' width=400>
  </p>
- 25 Eylül 2023: **Git** modu artık kullanılabilir durumda, programcının <img src='../online_log/static/figures/programmer.png' height=20> sürüm kontrolü için Git'i kullanmasına izin verir. Bu özelliği etkinleştirmek için sadece ``ChatChainConfig.json`` içinde ``"git_management"`` değerini ``"True"`` olarak ayarlamanız yeterlidir. [Kılavuza](wiki.md#git-mode) bakınız.
  <p align="center">
  <img src='../misc/github.png' width=600>
  </p>
- 20 Eylül 2023: **İnsan-Ajan-İletişimi** modu artık kullanılabilir! ChatDev ekibine katılarak inceleyici <img src='../online_log/static/figures/reviewer.png' height=20> rolünü üstlenebilir ve programcıya <img src='../online_log/static/figures/programmer.png' height=20> önerilerde bulunabilirsiniz; ``python3 run.py --task [fikrinizin açıklaması] --config "İnsan"`` komutunu deneyin. [Kılavuza](wiki.md#human-agent-interaction) ve [örneğe](WareHouse/Gomoku_HumanAgentInteraction_20230920135038) bakınız.
  <p align="center">
  <img src='../misc/Human_intro.png' width=600>
  </p>
- 1 Eylül 2023: **Sanat** modu şimdi kullanılabilir! Yazılımda kullanılan görselleri oluşturmak için tasarımcı ajanını <img src='../online_log/static/figures/designer.png' height=20> etkinleştirebilirsiniz; ``python3 run.py --task [fikrinizin açıklaması] --config "Sanat"`` komutunu deneyin. [Kılavuza](wiki.md#art) ve [örneğe](WareHouse/gomokugameArtExample_THUNLP_20230831122822) bakınız.
- 28 Ağustos 2023: Sistem halka açık durumda.
- 17 Ağustos 2023: v1.0.0 sürümü hazırlandı.
- 30 Temmuz 2023: Kullanıcılar ChatChain, Aşama ve Rol ayarlarını özelleştirebilirler. Ayrıca, hem çevrimiçi Log modu hem de yeniden oynatma mod

u desteklenmektedir.

- 16 Temmuz 2023: Bu projeye ilişkin [önyazı](https://arxiv.org/abs/2307.07924) yayımlandı.
- 30 Haziran 2023: ChatDev deposunun ilk sürümü yayınlandı.

## ❓ ChatDev Ne Yapabilir?

![intro](../misc/intro.png)

<https://github.com/OpenBMB/ChatDev/assets/11889052/80d01d2f-677b-4399-ad8b-f7af9bb62b72>

## ⚡️ Hızlı Başlangıç

### 🖥️ Terminal ile Hızlı Başlangıç

Başlamak için şu adımları izleyin:

1. **GitHub Deposunu Klonlayın:** İlk olarak, depoyu şu komutla klonlayarak başlayın:

   ```

   git clone <https://github.com/OpenBMB/ChatDev.git>

   ```

2. **Python Ortamını Kurun:** Python 3.9 veya daha yüksek bir sürüme sahip bir Python ortamınız olduğundan emin olun. Aşağıdaki komutları kullanarak bu ortamı oluşturabilir ve etkinleştirebilirsiniz, `ChatDev_conda_env` yerine tercih ettiğiniz ortam adını kullanın:

   ```

   conda create -n ChatDev_conda_env python=3.9 -y
   conda activate ChatDev_conda_env

   ```

3. **Bağımlılıkları Yükleyin:** `ChatDev` dizinine gidin ve aşağıdaki komutu kullanarak gerekli bağımlılıkları yükleyin:

   ```

   cd ChatDev
   pip3 install -r requirements.txt

   ```

4. **OpenAI API Anahtarını Ayarlayın:** OpenAI API anahtarınızı bir çevre değişkeni olarak belirtin. `"your_OpenAI_API_key"` yerine gerçek API anahtarınızı kullanın. Bu çevre değişkeni oturum özgüdür, bu nedenle yeni bir terminal oturumu açarsanız tekrar ayarlamanız gerekecektir.
   Unix/Linux'ta:

   ```

   export OPENAI_API_KEY="your_OpenAI_API_key"

   ```

   Windows'ta:

   ```

   $env:OPENAI_API_KEY="your_OpenAI_API_key"

   ```

5. **Yazılımınızı Oluşturun:** Aşağıdaki komutu kullanarak yazılımınızın oluşturulmasını başlatmak için şu komutu kullanın, `[fikrinizin açıklaması]` ile fikir açıklamanızı ve `[proje_adı]` ile istediğiniz proje adınızı kullanın:
   Unix/Linux'ta:

   ```

   python3 run.py --task "[fikrinizin açıklaması]" --name "[proje_adı]"

   ```

   Windows'ta:

   ```

   python run.py --task "[fikrinizin açıklaması]" --name "[proje_adı]"

   ```

6. **Yazılımınızı Çalıştırın:** Oluşturulduktan sonra yazılımınızı, belirli bir projenin klasörü altında, örneğin `project_name_DefaultOrganization_timestamp` adlı bir proje klasöründe bulabilirsiniz. Bu dizindeki komutu kullanarak yazılımınızı çalıştırın:
   Unix/Linux'ta:

   ```

   cd WareHouse/proje_adı_VarsayılanOrganizasyon_zamanDamgası
   python3 main.py

   ```

   Windows'ta:

   ```

   cd WareHouse/proje_adı_VarsayılanOrganizasyon_zamanDamgası
   python main.py

   ```

### 🐳 Docker ile Hızlı Başlangıç

- Docker desteği sağlayan [ManindraDeMel](https://github.com/ManindraDeMel) için teşekkür ederiz. Lütfen [Docker Başlangıç Kılavuzu'na](wiki.md#docker-start) bakınız.

## ✨️ Gelişmiş Yetenekler

Daha ayrıntılı bilgi için [Wiki](wiki.md)'mize başvurabilirsiniz, burada şunları bulabilirsiniz:

- Tüm komut çalıştırma parametrelerine giriş.
- Gelişmiş görselleştirilmiş günlükler, yeniden oynatma demosu ve basit bir ChatChain Görselleştirici içeren yerel web demo kurulumu için basit bir kılavuz.
- ChatDev çerçevesinin genel bir tanımı.
- ChatChain yapılandırmasındaki tüm gelişmiş parametrelerin kapsamlı bir tanıtımı.
- ChatDev'i özelleştirmek için kılavuzlar, bunlar şunları içerir:
  - ChatChain: Kendi yazılım geliştirme sürecinizi (veya başka bir süreci) tasarlayın, böylece ``TalepAnalizi -> Kodlama -> Test -> El ile`` gibi.
  - Aşama: ChatChain içinde kendi aşamanızı tasarlayın, örneğin ``TalepAnalizi``.
  - Rol: Şirketinizdeki çeşitli ajanları tanımlayın, örneğin ``İcra Kurulu Başkanı``.

## 🤗 Yazılımınızı Paylaşın

**Kod**: Açık kaynak projemize katılmak isteğinizden dolayı heyecanlıyız. Herhangi bir sorunla karşılaşırsanız, çekinmeden bildirin. Eğer herhangi bir sorunuz varsa veya çalışmanızı bizimle paylaşmaya hazırsanız, bir çekme isteği oluşturmanızdan çekinmeyin! Katkılarınız büyük bir değere sahiptir. Başka bir ihtiyacınız varsa lütfen bana bildirin!

**Şirket**: Kendi özelleştirilmiş "ChatDev Şirketi"ni oluşturmak çok kolaydır. Bu kişiselleştirilmiş kurulum, üç basit yapılandırma JSON dosyasını içerir. ``CompanyConfig/Default`` dizininde verilen örneğe bakın. Özelleştirme hakkında detaylı talimatlar için [Wiki](wiki.md) sayfamıza göz atın.

**Yazılım**: ChatDev kullanarak yazılım geliştirdiğinizde, ilgili bilgileri içeren bir klasör oluşturulur. Çalışmanızı bizimle paylaşmak, bir çekme isteği oluşturmak kadar basittir. İşte bir örnek: ``python3 run.py --task "2048 oyunu tasarla" --name "2048" --org "THUNLP" --config "Default"`` komutunu çalıştırın. Bu, bir yazılım paketi oluşturur ve ``/WareHouse/2048_THUNLP_timestamp`` adında bir klasör oluşturur. İçinde şunları bulacaksınız:

- 2048 oyun yazılımıyla ilgili tüm dosyalar ve belgeler
- Bu yazılımdan sorumlu şirketin yapılandırma dosyaları, içerisinde üç JSON yapılandırma dosyası bulunan ``CompanyConfig/Default``
- Yazılımın oluşturulma sürecini ayrıntılı olarak açıklayan kapsamlı bir günlük (``timestamp.log``)
- Bu yazılımın oluşturulmasında kullanılan ilk prompt (``2048.prompt``)

**Topluluk tarafından sağlanan yazılımları buradan görüntüleyin [burada](Contribution.md)!**

## 👨‍💻‍ Katkıda Bulunanlar

<a href="https://github.com/OpenBMB/ChatDev/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=OpenBMB/ChatDev" />
</a>

[contrib.rocks](https://contrib.rocks) ile oluşturulmuştur.

## 🔎 Alıntı

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

## ⚖️ Lisans

- Kaynak Kodu Lisansı: Projemizin kaynak kodu Apache 2.0 Lisansı altında lisanslanmıştır. Bu lisans, belirli koşullar dahilinde kodun kullanımını, değiştirilmesini ve dağıtılmasını izin verir.
- Proje Açık Kaynak Durumu: Proje gerçekten açık kaynaktır; ancak bu tanım öncelikle ticari olmayan amaçlar için tasarlanmıştır. Topluluktan işbirliği ve katkılara teşvik etsek de, projenin bileşenlerinin ticari amaçlar için kullanılması ayrı lisans anlaşmalarını gerektirir.
- Veri Lisansı: Projemizde kullanılan ilgili veri CC BY-NC 4.0 lisansı altında lisanslanmıştır. Bu lisans verinin ticari olmayan kullanımına açıkça izin verir. Bu veri kullanan modellerin kesinlikle ticari kullanım kısıtlamasına uyması ve sadece araştırma amaçları için kullanılması gerektiğini vurgulamak isteriz.

## 🌟 Yıldız Geçmişi

[![Yıldız Geçmişi Grafiği](https://api.star-history.com/svg?repos=openbmb/chatdev&type=Date)](https://star-history.com/#openbmb/chatdev&Date)

## 🤝 Teşekkürler

<a href="http://nlp.csai.tsinghua.edu.cn/"><img src="../misc/thunlp.png" height=50pt></a>&nbsp;&nbsp;
<a href="https://modelbest.cn/"><img src="../misc/modelbest.png" height=50pt></a>&nbsp;&nbsp;
<a href="https://github.com/OpenBMB/AgentVerse/"><img src="../misc/agentverse.png" height=50pt></a>&nbsp;&nbsp;
<a href="https://aibrb.com/introducing-herbie-your-super-employee-for-streamlined-productivity/"><img src="https://aibrb.com/wp-content/uploads/2023/09/Featured-on-AIBRB.com-white-1.png" height=50pt></a>

## 📬 İletişim

Herhangi bir sorunuz, geri bildiriminiz veya iletişime geçmek isterseniz, lütfen bize [chatdev.openbmb@outlook.com](mailto:chatdev.openbmb@outlook.com) adresi üzerinden ulaşmaktan çekinmeyin.
