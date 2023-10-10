# Wiki

<p align="center">
    【<a href="wiki.md">English</a> | Spanish】
</p>

## Inicio Rápido Paso a Paso

### 1. Instala `ChatDev`:

- **Clona el Repositorio de GitHub:** Comienza clonando el repositorio usando el comando:
   ```
   git clone https://github.com/OpenBMB/ChatDev.git
   ```
- **Configura el Entorno Python:** Asegúrate de tener un entorno Python de versión 3.9 o superior. Puedes crear y
  activar este entorno usando los siguientes comandos, reemplazando `ChatDev_conda_env` con el nombre que prefieras para el entorno:
	   
   ```
   conda create -n ChatDev_conda_env python=3.9 -y
   conda activate ChatDev_conda_env
   ```
- **Instala las Dependencias:** Muévete al directorio `ChatDev` e instala las dependencias necesarias ejecutando:
   ```
   cd ChatDev
   pip3 install -r requirements.txt
   ```
- **Establece la Llave de la API de OpenAI:** Exporta tu llave de la API de OpenAI como una variable de entorno. Reemplaza `"your_OpenAI_API_key"` con
  tu llave de la API real. Recuerda que esta variable de entorno es específica para la sesión, así que necesitarás establecerla de nuevo si
  abres una nueva sesión de terminal.
  En Unix/Linux:
   ```
   export OPENAI_API_KEY="your_OpenAI_API_key"
   ```
  En Windows:
   ```
   $env:OPENAI_API_KEY="your_OpenAI_API_key"
   ```

### 2. Comienza a construir software con un solo comando:

- **Construye Tu Software:** Utiliza el siguiente comando para iniciar la construcción de tu software, reemplazando `[description_of_your_idea]` con la descripción de tu idea y `[project_name]` con el nombre de proyecto deseado:
   ```
   python3 run.py --task "[description_of_your_idea]" --name "[project_name]"
   ```

- here is the full params of run.py

    ```commandline
    usage: run.py [-h] [--config CONFIG] [--org ORG] [--task TASK] [--name NAME] [--model MODEL]
    
    argparse
    
    optional arguments:
      -h, --help       show this help message and exit
      --config CONFIG  Name of config, which is used to load configuration under CompanyConfig/; Please see CompanyConfig Section below
      --org ORG        Name of organization, your software will be generated in WareHouse/name_org_timestamp
      --task TASK      Prompt of your idea
      --name NAME      Name of software, your software will be generated in WareHouse/name_org_timestamp
      --model MODEL    GPT Model, choose from {'GPT_3_5_TURBO','GPT_4','GPT_4_32K'}
    ```

### 3. Check your software

- the generated software is under ``WareHouse/NAME_ORG_timestamp``, including:
    - all the files and manuals of this software
    - config files of company which made this software, including three config json files
    - full log of the software building process
    - prompt to make this software
- A case of todo software is just like below, which is located in ``/WareHouse/todo_THUNLP_20230822165503``
    ```
    .
    ├── 20230822165503.log # log file
    ├── ChatChainConfig.json # Configuration
    ├── PhaseConfig.json # Configuration
    ├── RoleConfig.json # Configuration
    ├── todo.prompt # User query prompt
    ├── meta.txt # Software building meta information
    ├── main.py # Generated Software Files
    ├── manual.md # Generated Software Files
    ├── todo_app.py # Generated Software Files
    ├── task.py # Generated Software Files
    └── requirements.txt # Generated Software Files
    ```
- Usually you just need to install requirements and run main.py to use your software
    ```commandline
    cd WareHouse/project_name_DefaultOrganization_timestamp
    pip3 install -r requirements.txt
    python3 main.py
    ```

## Demostración Local

- Puedes iniciar una aplicación Flask para obtener una demostración local, incluyendo registros visualizados mejorados, demostración de repetición, y un simple
  Visualizador de ChatChain.

```
python3 online_log/app.py
```

Luego ve a [Sitio Web de Demostración Local](http://127.0.0.1:8000/) para ver una versión visualizada en línea de los registros, como

![demo](misc/demo.png)

- También puedes ir al [Visualizador de ChatChain](http://127.0.0.1:8000/static/chain_visualizer.html) en esta página y
  cargar cualquier archivo ``ChatChainConfig.json`` bajo ``CompanyConfig/`` para obtener una visualización de esta cadena, como:

![Visualizador de ChatChain](misc/chatchain_vis.png)

- También puedes ir a la página de Replay de Chat para reproducir el archivo de registro en la carpeta del software.
    - Haz clic en el botón ``File Upload`` para cargar un registro, luego haz clic en ``Replay``.
    - La repetición solo muestra los diálogos en lenguajes naturales entre los agentes, no contendrá registros de depuración.

![Replay](misc/replay.gif)

## Personalización

- Puedes personalizar tu empresa con tres tipos de granularidad:
    - Personalizar ChatChain
    - Personalizar Fase
    - Personalizar Rol
- Aquí está la arquitectura general de ChatDev, que ilustra las relaciones entre las tres clases mencionadas:

![arch](misc/arch.png)

### Personalizar ChatChain

- Ver ``CompanyConfig/Default/ChatChainConfig.json``
- Puedes seleccionar y organizar fácilmente las fases para formular un ChatChain a partir de todas las fases (de ``chatdev/phase.py``
  o ``chatdev/composed_phase.py``)
  modificando el archivo json de configuración de ChatChain.

### Personalizar Fase

- Esta es la única parte que requiere modificar el código, y aporta mucha flexibilidad para la personalización.
- Solo necesitas
    - implementar tu clase de fase (en el caso más simple, solo una función necesita ser modificada) extendiendo la clase ``Phase``
    - configurar esta fase en ``PhaseConfig.json``, incluyendo escribir el prompt de fase y asignar roles para esta fase
																												  
- Personalizar SimplePhase
    - ver ``CompanyConfig/Default/PhaseConfig.json`` para la configuración, ver ``chatdev/phase.py`` para implementar tu
      propia fase
    - cada fase contiene tres pasos:
        - generar el ambiente de fase a partir del ambiente completo de chatchain
        - usar el ambiente de fase para controlar el prompt de fase y ejecutar la conversación entre los roles en esta fase (que
          usualmente no necesita ser modificado)
        - obtener una conclusión del seminario de la conversación, y usarlo para actualizar el ambiente completo de chatchain
    - a continuación se muestra un ejemplo simple de fase sobre la elección del lenguaje de programación del software:
        - generar ambiente de fase: elegimos tarea, modalidad e ideas del ambiente de chatchain
        - ejecutar la fase: no necesita implementación, ya que está definido en la clase Phase
        - actualizar el ambiente de chatchain: obtenemos la conclusión del seminario (cuál lenguaje) y actualizamos la clave 'language' en el
          ambiente de chatchain
          ```python
          class LanguageChoose(Phase):
              def __init__(self, **kwargs):
                  super().__init__(**kwargs)

              def update_phase_env(self, chat_env):
                  self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                                         "modality": chat_env.env_dict['modality'],
                                         "ideas": chat_env.env_dict['ideas']})

              def update_chat_env(self, chat_env) -> ChatEnv:
                  if len(self.seminar_conclusion) > 0 and "<INFO>" in self.seminar_conclusion:
                      chat_env.env_dict['language'] = self.seminar_conclusion.split("<INFO>")[-1].lower().replace(".", "").strip()
                  elif len(self.seminar_conclusion) > 0:
                      chat_env.env_dict['language'] = self.seminar_conclusion
                  else:
                      chat_env.env_dict['language'] = "Python"
                  return chat_env
          ```
          La configuración de esta fase es como:
          ```json
          "LanguageChoose": {
            "assistant_role_name": "Chief Technology Officer",
            "user_role_name": "Chief Executive Officer",
            "phase_prompt": [
              "According to the new user's task and some creative brainstorm ideas listed below: ",
              "Task: \"{task}\".",
              "Modality: \"{modality}\".",
              "Ideas: \"{ideas}\".",
              "We have decided to complete the task through an executable software implemented via a programming language. ",
              "As the {assistant_role}, to satisfy the new user's demand and make the software realizable, you should propose a concrete programming language. If python can complete this task via Python, please answer Python; otherwise, answer another programming language (e.g., Java, C++, etc,).",
              "Note that we must ONLY discuss the target programming language and do not discuss anything else! Once we all have expressed our opinion(s) and agree with the results of the discussion unanimously, any of us must actively terminate the discussion and conclude the best programming language we have discussed without any other words or reasons, using the format: \"<INFO> *\" where \"*\" represents a programming language."
            ]
          }
          ```
    - Personalizar ComposePhase
        - ver ``CompanyConfig/Default/ChatChainConfig.json`` para la configuración y ver ``chatdev/composed_phase.py`` para
          la implementación.
        - **⚠️ Atención** Todavía no soportamos Composición Anidada, así que no coloques ComposePhase dentro de ComposePhase.
        - ComposePhase contiene múltiples SimplePhase, y se puede ejecutar en bucle.
        - ComposePhase no tiene un archivo json de Phase pero en el archivo json de chatchain puedes definir cuál SimplePhase está en esta
          ComposePhase, como:
      ```json
        {
          "phase": "CodeReview",
          "phaseType": "ComposedPhase",
          "cycleNum": 2,
          "Composition": [
            {
              "phase": "CodeReviewComment",
              "phaseType": "SimplePhase",
              "max_turn_step": -1,
              "need_reflect": "False"
            },
            {
              "phase": "CodeReviewModification",
              "phaseType": "SimplePhase",
              "max_turn_step": -1,
              "need_reflect": "False"
            }
          ]
        }
      ```
		- También necesitas implementar tu propia clase ComposePhase, en la que necesitas decidir la actualización de phase_env y
		  la actualización de chat_env (lo mismo que SimplePhase, pero para toda la ComposePhase) y la condición para detener el
		  bucle (opcional):

      ```python
      class Test(ComposedPhase):
          def __init__(self, **kwargs):
              super().__init__(**kwargs)

          def update_phase_env(self, chat_env):
              self.phase_env = dict()

          def update_chat_env(self, chat_env):
              return chat_env

          def break_cycle(self, phase_env) -> bool:
              if not phase_env['exist_bugs_flag']:
                  log_and_print_online(f"**[Test Info]**\n\nAI User (Software Test Engineer):\nTest Pass!\n")
                  return True
              else:
                  return False
      ```

### Personalizar Rol

- Ver ``CompanyConfig/Default/RoleConfig.json``
- Puedes usar marcadores de posición para utilizar el ambiente de fase, que es lo mismo que PhaseConfig.json
- **⚠️ Atención** Necesitas mantener al menos "Chief Executive Officer" y "Counselor" en tu propio ``RoleConfig.json``
  para que Reflection funcione.

## Parámetros de ChatChain

- *clear_structure*: limpia las carpetas de caché.
- *brainstorming*: Por definir
- *gui_design*: si crear o no una interfaz gráfica para el software.
- *git_management*: activar o no la gestión de git en el proyecto de software.
- *self_improve*: bandera para auto-mejoramiento en el prompt de entrada del usuario. Es una conversación especial en la que el LLM actúa como un ingeniero de prompts para mejorar el prompt de entrada del usuario. **⚠️ Atención** Los prompts generados por el modelo contienen incertidumbre y puede haber una desviación del significado del requisito contenido en el prompt original.
																															
																			   
- parámetros en SimplePhase:
    - *max_turn_step*: Número máximo de turnos de conversación. Puedes aumentar max_turn_step para obtener un mejor rendimiento pero tomará más tiempo terminar la fase.
    - *need_reflect*: Bandera para reflexión. La reflexión es una fase especial que se ejecuta automáticamente después de una fase. Iniciará una conversación entre el consejero y el CEO para refinar la conclusión de la conversación de la fase.
																													  
																								 
- parámetros en ComposedPhase:
    - *cycleNum*: Número de ciclos para ejecutar SimplePhase en esta ComposedPhase.

## Estructura del Proyecto

```commandline
├── CompanyConfig # Archivos de configuración para ChatDev, incluyendo configuración de ChatChain, Phase y Role en json.
├── WareHouse # Carpeta para el software generado
├── camel # Componente Camel RolePlay
├── chatdev # Código central de ChatDev
├── misc # activos de ejemplo y demostración
├── online_log # Carpeta Demo
├── run.py # Entrada de ChatDev
├── requirements.txt
├── README.md
└── wiki.md
```

## CompanyConfig

### Default
![demo](misc/ChatChain_Visualization_Default.png)
- Como se muestra en la visualización de ChatChain de la configuración predeterminada, ChatDev producirá un software en el orden de:
    - Análisis de Demanda: decidir la modalidad del software
    - Elección del Lenguaje: decidir el lenguaje de programación
    - Codificación: escribir el código
    - CodeCompleteAll: completar la función/clase faltante
    - Revisión de Código: revisar y modificar el código
    - Prueba: ejecutar el software y modificar el código basado en el informe de prueba
    - Documentación del Entorno: escribir la documentación del entorno
    - Manual: escribir el manual
- Puedes usar la configuración predeterminada ejecutando ``python3 run.py --config "Default"``.

### Arte
![demo](misc/ChatChain_Visualization_Art.png)
- Comparado con Default, la configuración Art añade una fase antes de CodeCompleteAll llamada Art.
- La fase Art primero discutirá el nombre y la descripción de los activos de imágenes, luego usará ``openai.Image.create`` para generar las imágenes basadas en la descripción.
- Puedes usar la configuración predeterminada ejecutando ``python3 run.py --config "Art"`` o simplemente ignorar el parámetro de configuración.

### Interacción Humano-Agente
![demo](misc/ChatChain_Visualization_Human.png)
- Comparado con Default, en el modo ***Human-Agent-Interaction*** puedes actuar como revisor y pedir al agente programador que modifique el código basado en tus comentarios.
- Se añade una Fase llamada HumanAgentInteraction después de la Fase de CodeReview.
- Puedes usar la configuración ***Human-Agent-Interaction*** ejecutando ``python3 run.py --config "Human"``.
- Cuando chatdev ejecuta hasta esta Fase, en la interfaz de comandos verás una pista que pide una entrada.
- Puedes ejecutar tu software en la carpeta ``WareHouse/`` y ver si satisface tus necesidades. Luego puedes escribir cualquier cosa que desees (corrección de errores o nueva característica) en la interfaz de comandos, y luego presionar Enter:
  ![Human_command](misc/Human_command.png)
- Por ejemplo:
    - Primero ejecutamos ChatDev con la tarea "diseñar un juego de gomoku".
    - Luego escribimos "Please add a restart button" (Por favor, añade un botón de reinicio) en la Fase de HumanAgentInteraction, añadiendo la primera característica.
    - En el segundo bucle de HumanAgentInteraction, añadimos otra característica escribiendo "Please add a current status bar showing whose turn it is" (Por favor, añade una barra de estado actual que muestre de quién es el turno).
    - Al final, salimos temprano de este modo escribiendo "End" (Fin).
    - Abajo se muestran las tres versiones.
        - <img src='misc/Human_v1.png' height=250>&nbsp;&nbsp;&nbsp;&nbsp;<img src='misc/Human_v2.png' height=250>&nbsp;&nbsp;&nbsp;&nbsp;<img src='misc/Human_v3.png' height=250>
