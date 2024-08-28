# Communicative Agents for Software Development

<p align="center">
  <img src='../misc/logo1.png' width=550>
</p>
<p align="center">
    【English   | <a href="readme/README-Chinese.md">Chinese</a> | <a href="readme/README-Japanese.md">Japanese</a> | <a href="readme/README-Korean.md">Korean</a> | <a href="readme/README-Filipino.md">Filipino</a> | <a href="readme/README-French.md">French</a> | <a href="readme/README-Slovak.md">Slovak</a> | <a href="readme/README-Portuguese.md">Portuguese</a> | <a href="readme/README-Spanish.md">Spanish</a> | <a href="readme/README-Dutch.md">Dutch</a> | <a href="readme/README-Turkish.md">Turkish</a> | <a href="readme/README-Hindi.md">Hindi</a> | <a href="readme/README-Bahasa-Indonesia.md">Bahasa Indonesia</a> | <a href="readme/README-Russian.md">Russian</a> | <a href="readme/README-Urdu.md">Urdu</a>】
</p>

<p align="center">
    【📚 <a href="../wiki.md">Wiki</a> | 🚀 <a href="../wiki.md#visualizer">Visualizer</a> | 👥 <a href="../Contribution.md">Community Built Software</a> | 🔧 <a href="../wiki.md#customization">Customization</a>】
</p>

## 📖 Overview

- **ChatDev** es una **empresa de software virtual** que opera a través de varios **agentes inteligentes** que desempeñan diferentes roles, incluyendo al Director Ejecutivo <img src='../visualizer/static/figures/ceo.png' height=20>, Director de Producto <img src='../visualizer/static/figures/cpo.png' height=20>, Director Tecnológico <img src='../visualizer/static/figures/cto.png' height=20>, programador <img src='../visualizer/static/figures/programmer.png' height=20>, revisor <img src='../visualizer/static/figures/reviewer.png' height=20>, tester <img src='../visualizer/static/figures/tester.png' height=20>, diseñador de arte <img src='../visualizer/static/figures/designer.png' height=20>. Estos agentes forman una estructura organizacional multi-agente y están unidos por una misión de "revolucionar el mundo digital a través de la programación." Los agentes dentro de ChatDev **colaboran** participando en seminarios funcionales especializados, incluyendo tareas como diseñar, codificar, probar y documentar.
- El objetivo principal de ChatDev es ofrecer un marco de trabajo **fácil de usar**, **altamente personalizable** y **extensible**, que se basa en modelos de grandes modelos de lenguaje (LLMs, por sus siglas en inglés) y sirve como un escenario ideal para estudiar la inteligencia colectiva.
<p align="center">
  <img src='../misc/company.png' width=600>
</p>

## 🎉 Noticias

* **25 de septiembre de 2023: La característica **Git** ya está disponible**, permite al programador <img src='../visualizer/static/figures/programmer.png' height=20> utilizar GitHub para el control de versiones. Para habilitar esta función, simplemente asigna el valor ``"True"`` igual a ``"git_management"`` en ``ChatChainConfig.json``.
  <p align="center">
  <img src='../misc/github.png' width=600>
  </p>
* 20 de septiembre de 2023: ¡El modo **Interacción Humano-Agente** ya está disponible! Puedes involucrarte con el equipo de ChatDev asumiendo el rol de revisor <img src='../visualizer/static/figures/reviewer.png' height=20> y haciendo sugerencias al programador <img src='../visualizer/static/figures/programmer.png' height=20>;
  prueba ``python3 run.py --task [description_of_your_idea] --config "Human"``. Consulta la [guía](../wiki.md#human-agent-interaction) y el [ejemplo](../WareHouse/Gomoku_HumanAgentInteraction_20230920135038).
  <p align="center">
  <img src='../misc/Human_intro.png' width=600>
  </p>
* 1 de septiembre de 2023: ¡El modo **Arte** ya está disponible! Puedes activar al agente de diseño <img src='../visualizer/static/figures/designer.png' height=20> para generar imágenes utilizadas en el software;
  prueba ``python3 run.py --task [description_of_your_idea] --config "Art"``. Consulta la [guía](../wiki.md#art) y el [ejemplo](../WareHouse/gomokugameArtExample_THUNLP_20230831122822).
* 28 de agosto de 2023: El sistema está disponible al público.
* 17 de agosto de 2023: La versión v1.0.0 estaba lista para ser lanzada.
* 30 de julio de 2023: Los usuarios pueden personalizar los ajustes de ChatChain, Phase, y Role. Además, ahora se soportan tanto el modo Log en línea como el modo de repetición.
* 16 de julio de 2023: Se publicó el [artículo preprint](https://arxiv.org/abs/2307.07924) asociado con este proyecto.
* 30 de junio de 2023: Se lanzó la versión inicial del repositorio de ChatDev.

## ❓ ¿Que puede hacer ChatDev?

![intro](../misc/intro.png)

https://github.com/OpenBMB/ChatDev/assets/11889052/80d01d2f-677b-4399-ad8b-f7af9bb62b72

## ⚡️ Inicio Rápido

Para comenzar, sigue estos pasos:

1. **Clonar el Repositorio de GitHub:** Empieza clonando el repositorio utilizando el comando:
   ```
   git clone https://github.com/OpenBMB/ChatDev.git
   ```
2. **Configurar el Entorno Python:** Asegúrate de tener un entorno Python versión 3.9 o superior. Puedes crear y
   activar este entorno usando los siguientes comandos, reemplazando `ChatDev_conda_env` con el nombre que prefieras para el entorno:
   ```
   conda create -n ChatDev_conda_env python=3.9 -y
   conda activate ChatDev_conda_env
   ```
3. **Instalar Dependencias:** Mueve al directorio `ChatDev` e instala las dependencias necesarias ejecutando:
   ```
   cd ChatDev
   pip3 install -r requirements.txt
   ```
4. **Establecer la Llave de la API de OpenAI:** Exporta tu llave de la API de OpenAI como una variable de entorno. Reemplaza `"your_OpenAI_API_key"` con
   tu llave de la API real. Recuerda que esta variable de entorno es específica de la sesión, así que necesitas establecerla de nuevo si
   abres una nueva sesión de terminal.
   En Unix/Linux:
   ```
   export OPENAI_API_KEY="tu_llave_de_OpenAI_API"
   ```
   En Windows:
   ```
   $env:OPENAI_API_KEY="tu_llave_de_OpenAI_API"
   ```
5. **Construye Tu Software:** Usa el siguiente comando para iniciar la construcción de tu software,
   reemplazando `[description_of_your_idea]` con la descripción de tu idea y `[project_name]` con el nombre deseado para tu proyecto:
   En Unix/Linux:
   ```
   python3 run.py --task "[description_de_tu_idea]" --name "[nombre_del_proyecto]"
   ```
   En Windows:
   ```
   python run.py --task "[description_de_tu_idea]" --name "[nombre_del_proyecto]"
   ```
6. **Ejecuta Tu Software:** Una vez generado, puedes encontrar tu software en el directorio `WareHouse` bajo una carpeta de proyecto específica,
   como `nombre_proyecto_OrganizationDefault_timestamp`. Ejecuta tu software usando el siguiente comando dentro de ese directorio:
   En Unix/Linux:
   ```
   cd WareHouse/nombre_proyecto_OrganizationDefault_timestamp
   python3 main.py
   ```
   En Windows:
   ```
   cd WareHouse/nombre_proyecto_OrganizationDefault_timestamp
   python main.py
   ```

## ✨️ Habilidades Avanzadas

Para obtener información más detallada, por favor refiérese a nuestro [Wiki](../wiki.md), donde puede encontrar:

- Una introducción a todos los parámetros de ejecución de comandos.
- Una guía sencilla para configurar una demostración web local, que incluye registros visualizados mejorados, una demostración de repetición y un
  sencillo Visualizador de ChatChain.
- Un resumen del marco de trabajo de ChatDev.
- Una introducción exhaustiva a todos los parámetros avanzados en la configuración de ChatChain.
- Guías para personalizar ChatDev, incluyendo:
    - ChatChain: Diseña tu propio proceso de desarrollo de software (o cualquier otro proceso), tal
      como ``DemandAnalysis -> Coding -> Testing -> Manual``.
    - Fase: Diseña tu propia fase dentro de ChatChain, como ``DemandAnalysis``.
    - Rol: Definiendo los diversos agentes en tu empresa, como el ``Chief Executive Officer``.

## 🤗 ¡Comparte Tu Software!

**Código**: Estamos entusiasmados con tu interés en participar en nuestro proyecto de código abierto. Si te encuentras con algún
problema, no dudes en reportarlo. ¡Siéntete libre de crear una solicitud de extracción si tienes alguna pregunta o si estás
preparado para compartir tu trabajo con nosotros! Tus contribuciones son muy valoradas. ¡Avísame si hay algo más en lo que
necesitas ayuda!

**Empresa**: Crear tu propia "Empresa ChatDev" personalizada es muy fácil. Esta configuración personalizada involucra tres simples
archivos JSON de configuración. Echa un vistazo al ejemplo proporcionado en el directorio ``CompanyConfig/Default``. Para instrucciones
detalladas sobre la personalización, consulta nuestro [Wiki](../wiki.md).

**Software**: Cada vez que desarrolles software usando ChatDev, se generará una carpeta correspondiente que contiene toda la
información esencial. Compartir tu trabajo con nosotros es tan simple como hacer una solicitud de extracción. Aquí hay un ejemplo: ejecuta el
comando ``python3 run.py --task "diseña un juego del a 2048 game" --name "2048"  --org "THUNLP" --config "Default"``. Esto creará
un paquete de software y generará una carpeta llamada ``/WareHouse/2048_THUNLP_timestamp``. Dentro, encontrarás:

- Todos los archivos y documentos relacionados con el software del juego 2048
- Archivos de configuración de la empresa responsable de este software, incluyendo los tres archivos JSON de configuración
  de ``CompanyConfig/Default``
- Un registro comprensivo que detalla el proceso de construcción del software que se puede utilizar para reproducir (``timestamp.log``)
- El prompt inicial utilizado para crear este software (``2048.prompt``)

**¡Ve el software contribuido por la comunidad [aquí](../Contribution.md)!**

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
<a href="https://github.com/Aizhouym"><img src="https://avatars.githubusercontent.com/u/105852026?v=4" alt="Contributor" style="width:5%; border-radius: 50%;"/></a>

## 🔎 Citación

```
@misc{qian2023communicative,
      title={Agentes Comunicativos para Desarrollo de Software}, 
      author={Chen Qian y Xin Cong y Wei Liu y Cheng Yang y Weize Chen y Yusheng Su y Yufan Dang y Jiahao Li y Juyuan Xu y Dahai Li y Zhiyuan Liu y Maosong Sun},
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

## ⚖️ Licencia

- Licencia del Código Fuente: El código fuente de nuestro proyecto está licenciado bajo la Licencia Apache 2.0. Esta licencia permite el uso, modificación y distribución del código, sujeto a ciertas condiciones descritas en la Licencia Apache 2.0.
- Licencia de Datos: Los datos relacionados utilizados en nuestro proyecto están licenciados bajo CC BY-NC 4.0. Esta licencia permite explícitamente el uso no comercial de los datos. Queremos enfatizar que cualquier modelo entrenado utilizando estos conjuntos de datos debe adherirse estrictamente a la restricción de uso no comercial y debe ser empleado exclusivamente para propósitos de investigación.



## 🤝 Agradecimientos
<a href="http://nlp.csai.tsinghua.edu.cn/"><img src="../misc/thunlp.png" height=50pt></a>&nbsp;&nbsp;
<a href="https://modelbest.cn/"><img src="../misc/modelbest.png" height=50pt></a>&nbsp;&nbsp;
<a href="https://github.com/OpenBMB/AgentVerse/"><img src="../misc/agentverse.png" height=50pt></a>&nbsp;&nbsp;
<a href="https://aibrb.com/introducing-herbie-your-super-employee-for-streamlined-productivity/"><img src="https://aibrb.com/wp-content/uploads/2023/09/Featured-on-AIBRB.com-white-1.png"  height=50pt></a>

## 📬 Contacto

Si tienes alguna pregunta, comentarios, o deseas ponerte en contacto, no dudes en enviarnos un correo electrónico a [qianc62@gmail.com](mailto:qianc62@gmail.com)
