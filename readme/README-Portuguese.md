# Communicative Agents for Software Development

<p align="center">
  <img src='../misc/logo1.png' width=550>
</p>


<p align="center">
    【📚 <a href="../wiki.md">Wiki</a> | 🚀 <a href="../wiki.md#local-demo">Demo Local</a> | 👥 <a href="../Contribution.md">Software Construído pela Comunidade</a> | 🔧 <a href="../wiki.md#customization">Personalização</a>】
</p>

## 📖 Overview

- **ChatDev** é uma **empresa de software virtual** que opera por meio de vários **agentes inteligentes** desempenhando
diferentes papéis, incluindo Diretor Executivo <img src='../online_log/static/figures/ceo.png' height=20>, Diretor de Produtos <img src='../online_log/static/figures/cpo.png' height=20>, Diretor de Tecnologia <img src='../online_log/static/figures/cto.png' height=20>, programador <img src='../online_log/static/figures/programmer.png' height=20>, revisor <img src='../online_log/static/figures/reviewer.png' height=20>, testador <img src='../online_log/static/figures/tester.png' height=20>, designer de arte <img src='../online_log/static/figures/designer.png' height=20>. Esses
agentes formam uma estrutura organizacional multiagente e estão unidos por uma missão de "revolucionar o mundo digital
por meio da programação." Os agentes dentro do ChatDev **colaboram** participando de seminários funcionais especializados,
incluindo tarefas como design, codificação, teste e documentação.

- O objetivo principal do ChatDev é oferecer um framework **fácil de usar**, **altamente personalizável** e **extensível**, baseado em modelos de linguagem grandes (LLMs) e que serve como um cenário ideal para estudar a inteligência coletiva.

<p align="center">
  <img src='../misc/company.png' width=600>
</p>

## 🎉 Notícias

* **25 de setembro de 2023: A funcionalidade Git agora está disponível**, permitindo que o programador <img src='../online_log/static/figures/programmer.png' height=20> utilize o GitHub para controle de versão. Para ativar essa funcionalidade, basta definir ``"git_management"`` para ``"True"`` no arquivo ``ChatChainConfig.json``.
  <p align="center">
  <img src='../misc/github.png' width=600>
  </p>
* 20 de setembro de 2023: O modo **Interação Humano-Agent** agora está disponível! Você pode se envolver com a equipe do ChatDev desempenhando o papel de revisor <img src='../online_log/static/figures/reviewer.png' height=20> e fazendo sugestões ao programador <img src='../online_log/static/figures/programmer.png' height=20>;
  tente ``python3 run.py --task [descrição_da_sua_ideia] --config "Human"``. Veja [guia](../wiki.md#human-agent-interaction) e [exemplo](../WareHouse/Gomoku_HumanAgentInteraction_20230920135038).
<p align="center">
<img src='../misc/Human_intro.png' width=600>
</p>

* 1º de setembro de 2023: O modo **Arte** está disponível agora! Você pode ativar o agente designer <img src='../online_log/static/figures/designer.png' height=20> para gerar imagens usadas no software;
  try ``python3 run.py --task [descrição_da_sua_ideia] --config "Art"``. Veja o [guia](../wiki.md#art) e o [exemplo](../WareHouse/gomokugameArtExample_THUNLP_20230831122822).
* 28 de agosto de 2023: O sistema está disponível publicamente.
* 17 de agosto de 2023: A versão v1.0.0 estava pronta para ser lançada.
* 30 de julho de 2023: Os usuários podem personalizar as configurações do * ChatChain, Fase e Papel. Além disso, o modo de Log online e o modo de replay * agora são suportados.
* 16 de julho de 2023: O artigo preliminar associado a este projeto foi * publicado.
* 30 de junho de 2023: A versão inicial do repositório do ChatDev foi lançada.

## ❓ O Que o ChatDev Pode Fazer?

![Introdução](../misc/intro.png)

https://github.com/OpenBMB/ChatDev/assets/11889052/80d01d2f-677b-4399-ad8b-f7af9bb62b72

## ⚡️ Início Rápido

Para começar, siga estas etapas:

1. **Clone o Repositório do GitHub:** Comece clonando o repositório usando o comando:
   ```
   git clone https://github.com/OpenBMB/ChatDev.git
   ```
2. **Configurar o Ambiente Python:** Verifique se você tem um ambiente Python versão 3.9 ou superior. Você pode criar e
   ativar este ambiente usando os seguintes comandos, substituindo `ChatDev_conda_env` pelo nome do ambiente de sua
   preferência:
   ```
   conda create -n ChatDev_conda_env python=3.9 -y
   conda activate ChatDev_conda_env
   ```
3. **Instalar Dependências:** Mova-se para o diretório `ChatDev` e instale as dependências necessárias executando:
   ```
   cd ChatDev
   pip3 install -r requirements.txt
   ```
4. **Inicializando as chaves da OpenAI API:** Exporte sua chave OpenAI API como uma variável de ambiente. Substitua `"your_OpenAI_API_key"` com sua chave API atual. Lembre-se de que esta variável de ambiente é apenas para esta sessão, portanto, você precisa defini-la novamente se abrir uma nova sessão de terminal.
   No Unix/Linux:
   ```
   export OPENAI_API_KEY="your_OpenAI_API_key"
   ```
   No Windows:
   ```
   $env:OPENAI_API_KEY="your_OpenAI_API_key"
   ```
5. **Construir o Seu Software:** Use o seguinte comando para iniciar a construção do seu software, substituindo
   `[descrição_da_sua_ideia]` pela descrição da sua ideia e `[nome_do_projeto]` pelo nome do projeto desejado:
   No Unix/Linux:
   ```
   python3 run.py --task "[descrição_da_sua_ideia]" --name "[nome_do_projeto]"
   ```
   No Windows:
   ```
   python run.py --task "[descrição_da_sua_ideia]" --name "[nome_do_projeto]"
   ```
6. **Executar o Seu Software:** Uma vez gerado, você pode encontrar seu software no diretório `WareHouse` sob uma pasta
   de projeto específica, como `project_name_DefaultOrganization_timestamp`. Execute seu software usando o seguinte
   comando dentro desse diretório:
   No Unix/Linux:
   ```
   cd WareHouse/project_name_DefaultOrganization_timestamp
   python3 main.py
   ```
   No Windows:
   ```
   cd WareHouse/project_name_DefaultOrganization_timestamp
   python main.py
   ```

## ✨️ Habilidades Avançadas

Para obter informações mais detalhadas, consulte nossa Wiki, onde você pode encontrar:

- Uma introdução a todos os parâmetros de execução de comandos.
- Um guia direto para configurar um demo web local, que inclui logs visualizados aprimorados, um demo de replay e um ChatChain Visualizer simples.
- Uma visão geral do framework ChatDev.
- Uma introdução abrangente a todos os parâmetros avançados na configuração do ChatChain.
- Guias para personalizar o ChatDev, incluindo:
  - ChatChain: Projete seu próprio processo de desenvolvimento de software (ou qualquer outro processo), como ``Análise de Demanda -> Codificação -> Teste -> Manual``.
  - Fase: Projete sua própria fase dentro do ChatChain, como ``Análise de Demanda``.
  -  Papel: Defina os diversos agentes em sua empresa, como ``Diretor Executivo``.

## 🤗 Compartilhe seu Software!

**Código**: Estamos entusiasmados com seu interesse em participar de nosso projeto de código aberto. Se você encontrar algum problema, não hesite em relatá-lo. Sinta-se à vontade para criar uma solicitação pull se tiver alguma dúvida ou se estiver pronto para compartilhar seu trabalho conosco! Suas contribuições são altamente valorizadas. Por favor, avise se houver mais alguma coisa que você precisa de ajuda!

**Empresa**: Criar sua própria "Empresa ChatDev" personalizada é fácil. Essa configuração personalizada envolve três arquivos JSON de configuração simples. Confira o exemplo fornecido no diretório ``CompanyConfig/Default``. Para instruções detalhadas sobre personalização, consulte nossa [Wiki](../wiki.md).

**Software**: Sempre que você desenvolve software usando o ChatDev, é gerada uma pasta correspondente contendo todas as informações essenciais. Compartilhar seu trabalho conosco é tão simples quanto criar uma solicitação pull. Aqui está um exemplo: execute o comando ``python3 run.py --task "design a 2048 game" --name "2048"  --org "THUNLP" --config "Default"``. Isso criará um pacote de software e gerará uma pasta chamada ``/WareHouse/2048_THUNLP_timestamp``. Dentro dela, você encontrará:

- Todos os arquivos e documentos relacionados ao software do jogo 2048
- Arquivos de configuração da empresa responsável por este software, incluindo os três arquivos JSON de configuração de ``CompanyConfig/Default``
- Um registro abrangente detalhando o processo de construção do software que pode ser usado para replay (``timestamp.log``)
- A prompt inicial usada para criar este software (``2048.prompt``)

**Veja o software contribuído pela comunidade [aqui](../Contribution.md)!**

## 👨‍💻‍ Contribuidores de Software

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

## 🔎 Citação

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

## ⚖️ Licença

- Licenciamento de Código Fonte: O código fonte de nosso projeto está licenciado sob a Licença Apache 2.0. Esta licença permite o uso, modificação e distribuição do código, sujeito a certas condições delineadas na Licença Apache 2.0.
- Status de Código Aberto do Projeto: O projeto é de fato de código aberto; no entanto, essa designação se destina principalmente a fins não comerciais. Embora encorajemos a colaboração e contribuições da comunidade para fins de pesquisa e aplicações não comerciais, é importante observar que qualquer uso dos componentes do projeto para fins comerciais requer acordos de licenciamento separados.
- Licenciamento de Dados: Os dados relacionados usados em nosso projeto estão licenciados sob CC BY-NC 4.0. Esta licença permite explicitamente o uso não comercial dos dados. Gostaríamos de enfatizar que qualquer modelo treinado usando esses conjuntos de dados deve aderir estritamente à restrição de uso não comercial e deve ser usado exclusivamente para fins de pesquisa.

## 🌟 Histórico de Estrelas

[![Star History Chart](https://api.star-history.com/svg?repos=openbmb/chatdev&type=Date)](https://star-history.com/#openbmb/chatdev&Date)


## 🤝 Agradecimentos
<a href="http://nlp.csai.tsinghua.edu.cn/"><img src="../misc/thunlp.png" height=50pt></a>&nbsp;&nbsp;
<a href="https://modelbest.cn/"><img src="../misc/modelbest.png" height=50pt></a>&nbsp;&nbsp;
<a href="https://github.com/OpenBMB/AgentVerse/"><img src="../misc/agentverse.png" height=50pt></a>&nbsp;&nbsp;
<a href="https://aibrb.com/introducing-herbie-your-super-employee-for-streamlined-productivity/"><img src="https://aibrb.com/wp-content/uploads/2023/09/Featured-on-AIBRB.com-white-1.png"  height=50pt></a>

## 📬 Contato

Se você tiver alguma dúvida, feedback ou gostaria de entrar em contato, não hesite em nos enviar um e-mail para [chatdev.openbmb@outlook.com](mailto:chatdev.openbmb@outlook.com)
