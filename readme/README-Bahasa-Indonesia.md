# Communicative Agents for Software Development

<p align="center">
  <img src='../misc/logo1.png' width=550>
</p>

<p align="center">
    【<a href="../README.md">Inggris</a> | Bahasa Indonesia  | <a href="readme/README-Chinese.md">Cina</a> | <a href="readme/README-Japanese.md">Jepang</a> | <a href="readme/README-Korean.md">Korea</a> | <a href="readme/README-Filipino.md">Filipina</a> | <a href="readme/README-Prancis.md">Prancis</a> | <a href="readme/README-Slovak.md">Slovakia</a> | <a href="readme/README-Portugis.md">Portugis</a> | <a href="readme/README-Spanyol.md">Spanyol</a> | <a href="readme/README-Belanda.md">Belanda</a> | <a href="readme/README-Hindi.md">Hindi</a>】
</p>
<p align="center">
    【📚 <a href="wiki.md">Wiki</a> | 🚀 <a href="wiki.md#demo-lokal">Demo Lokal</a> | 👥 <a href="Contribution.md">Perangkat Lunak Dibangun oleh Komunitas</a> | 🔧 <a href="wiki.md#penyesuaian">Penyesuaian</a>】
</p>

## 📖 Gambaran

- **ChatDev** berdiri sebagai **perusahaan perangkat lunak virtual** yang beroperasi melalui berbagai **agen cerdas** yang memiliki peran berbeda, termasuk Chief Executive Officer <img src='../visualizer/static/figures/ceo.png' height=20>, Chief Product Officer <img src='../visualizer/static/figures/cpo.png' height=20>, Chief Technology Officer <img src='../visualizer/static/figures/cto.png' height=20>, programmer <img src='../visualizer/static/figures/programmer.png' height=20>, reviewer <img src='../visualizer/static/figures/reviewer.png' height=20>, tester <img src='../visualizer/static/figures/tester.png' height=20>, desainer seni <img src='../visualizer/static/figures/designer.png' height=20>. Agen-agen ini membentuk struktur organisasi multi-agen dan bersatu dalam misi "merevolusi dunia digital melalui pemrograman." Agen-agen dalam ChatDev **bekerja sama** dengan berpartisipasi dalam seminar fungsional khusus, termasuk tugas-tugas seperti desain, pemrograman, pengujian, dan dokumentasi.
- Tujuan utama ChatDev adalah menawarkan kerangka kerja yang **mudah digunakan**, **dapat disesuaikan secara tinggi**, dan **dapat diperluas**, yang didasarkan pada model bahasa besar (Large Language Models atau LLMs) dan menjadi skenario ideal untuk mempelajari kecerdasan kolektif.

<p align="center">
  <img src='../misc/company.png' width=600>
</p>

## 🎉 Berita

- **26 Oktober 2023: ChatDev kini didukung oleh Docker untuk eksekusi yang aman** (berkat kontribusi dari [ManindraDeMel](https://github.com/ManindraDeMel)). Silakan lihat [Panduan Memulai Docker](wiki.md#memulai-docker).
  <p align="center">
  <img src='../misc/docker.png' width=400>
  </p>
- 25 September 2023: Mode **Git** kini tersedia, memungkinkan programmer <img src='../visualizer/static/figures/programmer.png' height=20> untuk menggunakan Git untuk kontrol versi. Untuk mengaktifkan fitur ini, cukup atur ``"git_management"`` menjadi ``"True"`` di ``ChatChainConfig.json``. Lihat [panduan](wiki.md#mode-git).
  <p align="center">
  <img src='../misc/github.png' width=600>
  </p>
- 20 September 2023: Mode **Interaksi Manusia-Agen** kini tersedia! Anda dapat terlibat dengan tim ChatDev dengan memainkan peran reviewer <img src='../visualizer/static/figures/reviewer.png' height=20> dan memberikan saran kepada programmer <img src='../visualizer/static/figures/programmer.png' height=20>; coba ``python3 run.py --task [deskripsi_ide_anda] --config "Manusia"``. Lihat [panduan](wiki.md#interaksi-manusia-agen) dan [contoh](WareHouse/Gomoku_HumanAgentInteraction_20230920135038).
  <p align="center">
  <img src='../misc/Human_intro.png' width=600>
  </p>
- 1 September 2023: Mode **Seni** kini tersedia! Anda dapat mengaktifkan agen desainer <img src='../visualizer/static/figures/designer.png' height=20> untuk menghasilkan gambar yang digunakan dalam perangkat lunak; coba ``python3 run.py --task [deskripsi_ide_anda] --config "Seni"``. Lihat [panduan](wiki.md#seni) dan [contoh](WareHouse/gomokugameArtExample_THUNLP_20230831122822).
- 28 Agustus 2023: Sistem tersedia untuk publik.
- 17 Agustus 2023: Versi v1.0.0 siap untuk dirilis.
- 30 Juli 2023: Pengguna dapat menyesuaikan pengaturan ChatChain, Fase, dan Peran. Selain itu, mode Log online dan mode pemutaran kini didukung.
- 16 Juli 2023: [Prapublikasi](https://arxiv.org/abs/2307.07924) terkait dengan proyek ini telah diterbitkan.
- 30 Juni 2023: Versi awal repositori ChatDev dirilis.

## ❓ Apa yang Dapat Dilakukan ChatDev?

![intro](../misc/intro.png)

<https://github.com/OpenBMB/ChatDev/assets/11889052/80d01d2f-677b-4399-ad8b-f7af9bb62b72>

## ⚡️ Memulai dengan Cepat

### 🖥️ Memulai dengan terminal

Untuk memulai, ikuti langkah-langkah berikut:

1. **Kloning Repositori GitHub:** Mulailah dengan mengkloning repositori menggunakan perintah berikut:

   ```

   git clone https://github.com/OpenBMB/ChatDev.git

   ```

2. **Menyiapkan Lingkungan Python:** Pastikan Anda memiliki lingkungan Python versi 3.9 atau lebih tinggi. Anda dapat membuat dan mengaktifkan lingkungan ini dengan perintah berikut, mengganti `ChatDev_conda_env` dengan nama lingkungan yang Anda inginkan:

   ```

   conda create -n ChatDev_conda_env python=3.9 -y
   conda activate ChatDev_conda_env

   ```

3. **Menginstal Dependensi:** Pindah ke direktori `ChatDev` dan instal dependensi yang diperlukan dengan menjalankan:

   ```

   cd ChatDev
   pip3 install -r requirements.txt

   ```

4. **Mengatur Kunci API OpenAI:** Export kunci API OpenAI Anda sebagai variabel lingkungan. Gantilah `"your_OpenAI_API_key"` dengan kunci API Anda yang sebenarnya. Ingatlah bahwa variabel lingkungan ini bersifat sesi-spesifik, sehingga Anda perlu mengaturnya lagi jika Anda membuka sesi terminal yang baru.
   Pada Unix/Linux:

   ```

   export OPENAI_API_KEY="your_OpenAI_API_key"

   ```

   Pada Windows:

   ```

   $env:OPENAI_API_KEY="your_OpenAI_API_key"

   ```

5. **Membangun Perangkat Lunak Anda:** Gunakan perintah berikut untuk memulai pembangunan perangkat lunak Anda, mengganti `[deskripsi_ide_anda]` dengan deskripsi ide Anda dan `[nama_proyek]` dengan nama proyek yang Anda inginkan:
   Pada Unix/Linux:

   ```

   python3 run.py --task "[deskripsi_ide_anda]" --name "[nama_proyek]"

   ```

   Pada Windows:

   ```

   python run.py --task "[deskripsi_ide_anda]" --name "[nama_proyek]"

   ```

6. **Menjalankan Perangkat Lunak Anda:** Setelah dibangun, Anda dapat menemukan perangkat lunak Anda di direktori `WareHouse` dalam folder proyek tertentu, seperti `project_name_DefaultOrganization_timestamp`. Jalankan perangkat lunak Anda dengan perintah berikut di dalam direktori tersebut:
   Pada Unix/Linux:

   ```

   cd WareHouse/project_name_DefaultOrganization_timestamp
   python3 main.py

   ```

   Pada Windows:

   ```

   cd WareHouse/project_name_DefaultOrganization_timestamp
   python main.py

   ```

### 🐳 Memulai dengan Docker

- Kami berterima kasih kepada [ManindraDeMel](https://github.com/ManindraDeMel) atas dukungan Docker. Silakan lihat [Panduan Memulai Docker](wiki.md#memulai-docker).

## ✨️ Keterampilan Lanjutan

Untuk informasi lebih rinci, silakan merujuk ke [Wiki](wiki.md) kami, di mana Anda dapat menemukan:

- Pengantar untuk semua parameter jalankan perintah.
- Panduan yang mudah untuk menyiapkan demo web lokal, yang mencakup log visual yang ditingkatkan, demo pemutaran, dan Visualizer ChatChain sederhana.
- Gambaran tentang kerangka kerja ChatDev.
- Pengantar komprehensif untuk semua parameter lanjutan dalam konfigurasi ChatChain.
- Panduan untuk menyesuaikan ChatDev, termasuk:
  - ChatChain: Desain proses pengembangan perangkat lunak Anda sendiri (atau proses lainnya), seperti ``DemandAnalysis -> Pemrograman -> Pengujian -> Manual``.
  - Fase: Desain fase Anda sendiri dalam ChatChain, seperti ``DemandAnalysis``.
  - Peran: Mendefinisikan berbagai agen dalam perusahaan Anda, seperti ``Chief Executive Officer``.

## 🤗 Bagikan Perangkat Lunak Anda

**Kode**: Kami sangat antusias tentang minat Anda untuk berpartisipasi dalam proyek sumber terbuka kami. Jika Anda mengalami masalah, jangan ragu untuk melaporkannya. Jangan ragu untuk membuat permintaan tarik (pull request) jika Anda memiliki pertanyaan atau jika Anda siap untuk berbagi pekerjaan Anda dengan kami! Kontribusi Anda sangat dihargai. Tolong beri tahu saya jika ada yang perlu Anda bantu!

**Perusahaan**: Membuat "Perusahaan ChatDev" khusus Anda sendiri sangat mudah. Penyiapan ini melibatkan tiga file JSON konfigurasi sederhana. Lihat contoh yang disediakan dalam direktori ``CompanyConfig/Default``. Untuk petunjuk lebih rinci tentang penyesuaian, lihat [Wiki](wiki.md) kami.

**Perangkat Lunak**: Setiap kali Anda mengembangkan perangkat lunak menggunakan ChatDev, folder yang sesuai akan dihasilkan yang berisi semua informasi penting. Berbagi pekerjaan Anda dengan kami sama mudahnya seperti membuat permintaan tarik. Berikut contohnya: jalankan perintah ``python3 run.py --task "mendesain game 2048" --name "2048"  --org "THUNLP" --config "Default"``. Ini akan membuat paket perangkat lunak dan menghasilkan folder bernama ``/WareHouse/2048_THUNLP_timestamp``. Di dalamnya, Anda akan menemukan:

- Semua file dan dokumen terkait perangkat lunak game 2048
- File konfigurasi perusahaan yang bertanggung jawab atas perangkat lunak ini, termasuk tiga file konfigurasi JSON dari ``CompanyConfig/Default``
- Log komprehensif yang mendetailkan proses pembangunan perangkat lunak yang dapat digunakan untuk pemutaran (``timestamp.log``)
- Prompt awal yang digunakan untuk membuat perangkat lunak ini (``2048.prompt``)

**Lihat perangkat lunak yang telah disumbangkan oleh komunitas [di sini](Contribution.md)!**

## 👨‍💻‍ Kontributor

<a href="https://github.com/OpenBMB/ChatDev/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=OpenBMB/ChatDev" />
</a>

Dibuat dengan [contrib.rocks](https://contrib.rocks).

## 🔎 Kutipan

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

## ⚖️ Lisensi

- Lisensi Kode Sumber: Kode sumber proyek kami dilisensikan di bawah Lisensi Apache 2.0. Lisensi ini mengizinkan penggunaan, modifikasi, dan distribusi kode, dengan syarat tertentu yang dijelaskan dalam Lisensi Apache 2.0.
- Lisensi Data: Data terkait yang digunakan dalam proyek kami dilisensikan di bawah CC BY-NC 4.0. Lisensi ini secara eksplisit mengizinkan penggunaan non-komersial data tersebut. Kami ingin menekankan bahwa model-model yang dilatih menggunakan dataset ini harus tunduk secara ketat pada pembatasan penggunaan non-komersial dan hanya boleh digunakan untuk tujuan penelitian.

## 🌟 Riwayat Bintang

[![Grafik Riwayat Bintang](https://api.star-history.com/svg?repos=openbmb/chatdev&type=Date)](https://star-history.com/#openbmb/chatdev&Date)

## 🤝 Pengakuan

<a href="http://nlp.csai.tsinghua.edu.cn/"><img src="../misc/thunlp.png" height=50pt></a>&nbsp;&nbsp;
<a href="https://modelbest.cn/"><img src="../misc/modelbest.png" height=50pt></a>&nbsp;&nbsp;
<a href="https://github.com/OpenBMB/AgentVerse/"><img src="../misc/agentverse.png" height=50pt></a>&nbsp;&nbsp;
<a href="https://aibrb.com/introducing-herbie-your-super-employee-for-streamlined-productivity/"><img src="https://aibrb.com/wp-content/uploads/2023/09/Featured-on-AIBRB.com-white-1.png"  height=50pt></a>

## 📬 Kontak

Jika Anda memiliki pertanyaan, umpan balik, atau ingin menghubungi kami, jangan ragu untuk menghubungi kami melalui email di [chatdev.openbmb@outlook.com](mailto:chatdev.openbmb@outlook.com)
