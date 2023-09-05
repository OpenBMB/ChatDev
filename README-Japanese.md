# Communicative Agents for Software Development

<p align="center">
  <img src='./misc/logo1.png' width=600>
</p>

<p align="center">
    【<a href="README.md">English</a> | <a href="README-Chinese.md">Chinese</a> | Japanese】
</p>

## 📖 概要

- **ChatDev** は、最高経営責任者（CEO）、最高技術責任者（CTO）、プログラマー、テスターなど、さまざまな役割を持つ**インテリジェントエージェント**によって運営される**バーチャルソフトウェア企業**です。これらのエージェントは、マルチエージェントの組織構造を形成し、"プログラミングを通じてデジタル世界に革命を起こす"というミッションで団結しています。ChatDev 内のエージェントは、設計、コーディング、テスト、ドキュメント作成などのタスクを含む専門的な機能セミナーに参加することで、**共同作業** を行います。
- ChatDev の主な目的は、**使いやすく**、**高度にカスタマイズ可能**で**拡張可能**なフレームワークを提供することであり、これは大規模言語モデル（LLM）に基づいており、集合知を研究するための理想的なシナリオとして機能します。


## 📰 ニュース

* **2023年9月1日: Art モードが利用可能になりました！``python3 run.py --config "Art"``。** こちら[example](WareHouse/gomokugameArtExample_THUNLP_20230831122822)を参照してください。
* 2023年8月28日: システムは一般公開されました。
* 2023年8月17日: V1.0.0 のリリース準備が整いました。
* 2023年7月30日: ユーザーは、ChatChain、Phase、Role の設定をカスタマイズすることができます。さらに、オンラインログモードとリプレイモードの両方がサポートされました。
* 2023年7月16日: このプロジェクトに関連した[プレプリント論文](https://arxiv.org/abs/2307.07924)が発表された。
* 2023年6月30日: `ChatDev` リポジトリの初期バージョンがリリースされました。


## ❓ ChatDev は何ができるのか？

![intro](misc/intro.png)




https://github.com/OpenBMB/ChatDev/assets/11889052/80d01d2f-677b-4399-ad8b-f7af9bb62b72




## ⚡️ クイックスタート

開始するには、以下の手順に従ってください:

1. **GitHub リポジトリのクローン:** コマンドを使ってリポジトリのクローンを作成する:
   ```
   git clone https://github.com/OpenBMB/ChatDev.git
   ```
2. **Python 環境のセットアップ:** バージョン 3.9 以上の Python 環境があることを確認してください。`ChatDev_conda_env` をお好みの環境名に置き換え、以下のコマンドを使用してこの環境を作成し、有効化することができます:
   ```
   conda create -n ChatDev_conda_env python=3.9 -y
   conda activate ChatDev_conda_env
   ```
3. **依存関係のインストール:** `ChatDev` ディレクトリに移動し、以下のコマンドを実行して必要な依存関係をインストールする:
   ```
   cd ChatDev
   pip3 install -r requirements.txt
   ```
4. **OpenAI API キーの設定:** OpenAI API key を環境変数としてエクスポートします。`"your_OpenAI_API_key"` を実際の API キーに置き換えてください。この環境変数はセッション固有なので、新しいターミナルセッションを開くときに再度設定する必要があることを覚えておいてください。
   Unix/Linux 上では:
   ```
   export OPENAI_API_KEY="your_OpenAI_API_key"
   ```
   Windows 上では:
   ```
   $env:OPENAI_API_KEY="your_OpenAI_API_key"
   ```
5. **ソフトウェアの構築:** 次のコマンドを使用して、ソフトウェアのビルドを開始する。`[description_of_your_idea]` をあなたのアイデアの説明に、`[project_name]` を希望するプロジェクト名に置き換える:
   ```
   python3 run.py --task "[description_of_your_idea]" --name "[project_name]"
   ```
6. **ソフトウェアの実行:** 生成されたソフトウェアは、`Project_name_DefaultOrganization_timestamp` のような特定のプロジェクトフォルダの下の `WareHouse` ディレクトリにあります。そのディレクトリで以下のコマンドを使ってソフトウェアを実行してください:
   ```
   cd WareHouse/project_name_DefaultOrganization_timestamp
   python3 main.py
   ```

## ✨️ 高度なスキル

より詳細な情報については、私たちの [Wiki](wiki.md) を参照してください:

- すべてのコマンド実行パラメータの紹介
- 強化されたビジュアライズされたログ、リプレイデモ、シンプルな ChatChain ビジュアライザを含む、ローカルウェブデモをセットアップするための簡単なガイド。
- ChatDev フレームワークの概要
- ChatChain 設定の高度なパラメータの包括的な紹介。
- ChatDev をカスタマイズするためのガイドです:
    - ChatChain: 独自のソフトウェア開発プロセス（または他のプロセス）を設計します。例えば ``DemandAnalysis -> Coding -> Testing -> Manual`` などです。
    - Phase: ``DemandAnalysis``のように、ChatChain 内で独自のフェーズを設計する。
    - Role: 最高経営責任者 ``Chief Executive Officer`` のように、社内の様々なエージェントを定義する。


## 🤗 ソフトウェアを共有する！

**コード**: 私たちは、あなたが私たちのオープンソースプロジェクトに参加してくださることに熱意をもっています。もし何か問題があれば、遠慮なく報告してください。問い合わせがある場合、または私たちと仕事を共有する用意がある場合は、遠慮なくプルリクエストを作成してください！あなたのコントリビュートは高く評価されます。また、何かありましたらお知らせください！

**カンパニー**: カスタマイズした "ChatDev Company" の作成は簡単です。このパーソナライズされたセットアップには、3つの簡単な設定JSONファイルが必要です。``CompanyConfig/Default`` ディレクトリで提供されている例をチェックしてください。カスタマイズの詳細については [Wiki](wiki.md) を参照してください。

**ソフトウェア**: ChatDev を使ってソフトウェアを開発すると、必要な情報を含むフォルダが作成されます。プルリクエストを行うだけで、あなたの作品を共有することができます。コマンド ``python3 run.py --task "design a 2048 game" --name "2048" --org "THUNLP" --config "Default"`` を実行してください。これでソフトウェアパッケージが作成され、``/WareHouse/2048_THUNLP_timestamp`` という名前のフォルダが生成されます。内部には:
- 2048 ゲームソフトウェアに関連するすべてのファイルとドキュメント
- ``CompanyConfig/Default`` にある 3 つの JSON 設定ファイルを含む、このソフトウェアを開発した会社の設定ファイル
- リプレイに使用できる、このソフトウェアのビルドプロセスの詳細なログ（``timestamp.log``）
- このソフトウェアを作成するために使用された最初のプロンプト (``2048.prompt``)

ChatDev によって作成された例をいくつか紹介します:

<table style="width:100%">
<thead>
  <tr>
    <th>コントリビューター</th>
    <th>ソフトウェア</th>
    <th>スクリーンショット</th>
    <th>ステータス</th>
    <th>大規模言語モデル</th>
  </tr>
</thead>
<tbody>
  <tr>
    <td rowspan="4"><a href="https://github.com/qianc62" target="_blank" rel="noopener noreferrer">https://github.com/qianc62</a></td>
    <td><a href="WareHouse/Website_THUNLP_20230725154612" target="_blank" rel="noopener noreferrer">A simple website</a></td>
    <td><img src="misc/website.png" width="200px"></td>
    <td>Perfect</td>
    <td>GPT3.5</td>
  </tr>
  <tr>
    <td><a href="WareHouse/FlappyBird_THUNLP_20230726121145" target="_blank" rel="noopener noreferrer">FlappyBirds Game</a></td>
    <td><img src="misc/flappy_bird.png" width="200px"></td>
    <td>Perfect</td>
    <td>GPT3.5</td>
  </tr>
  <tr>
    <td><a href="WareHouse/Gomoku_THUNLP_20230625201030" target="_blank" rel="noopener noreferrer">A Gomoku Game</a></td>
    <td><img src="misc/gomoku.png" width="200px"></td>
    <td>Perfect</td>
    <td>GPT3.5</td>
  </tr>
  <tr>
    <td><a href="WareHouse/Calculator_THUNLP_20230628184918" target="_blank" rel="noopener noreferrer">A calculator with bottom icons generated by Agents</a></td>
    <td><img src="misc/calc.jpg" width="200px"></td>
    <td>Perfect</td>
    <td>GPT3.5</td>
  </tr>
  <tr>
    <td rowspan="17"><a href="https://github.com/thinkwee" target="_blank" rel="noopener noreferrer">https://github.com/thinkwee</a></td>
    <td><a href="WareHouse/ArtCanvas_THUNLP_20230825093558" target="_blank" rel="noopener noreferrer">Painter</a></td>
    <td><img src="misc/paint.png" width="200px"></td>
    <td>Perfect</td>
    <td>GPT3.5</td>
  </tr>
  <tr>
    <td><a href="WareHouse/pingpong_THUNLP_20230817193956" target="_blank" rel="noopener noreferrer">PingPong Game</a></td>
    <td><img src="misc/pingpong.jpg" width="200px"></td>
    <td>Biased</td>
    <td>GPT3.5</td>
  </tr>
  <tr>
    <td><a href="WareHouse/PixelRunner_THUNLP_20230825072339" target="_blank" rel="noopener noreferrer">PixelRunner</a></td>
    <td><img src="misc/jump_game.png" width="200px"></td>
    <td>Runnable</td>
    <td>GPT3.5</td>
  </tr>
  <tr>
    <td><a href="WareHouse/MoneyCtrl_THUNLP_20230825093546" target="_blank" rel="noopener noreferrer">BudgetControl</a></td>
    <td><img src="misc/budget.png" width="200px"></td>
    <td>Biased</td>
    <td>GPT3.5</td>
  </tr>
  <tr>
    <td><a href="WareHouse/PixelCraft_THUNLP_20230825072340" target="_blank" rel="noopener noreferrer">PixelCraft</a></td>
    <td><img src="misc/pixel_art.png" width="200px"></td>
    <td>Runnable</td>
    <td>GPT3.5</td>
  </tr>
  <tr>
    <td><a href="WareHouse/MazeGenerator_THUNLP_20230825093601" target="_blank" rel="noopener noreferrer">MazeGenerator</a></td>
    <td><img src="misc/maze_generator.png" width="200px"></td>
    <td>Perfect</td>
    <td>GPT3.5</td>
  </tr>
  <tr>
    <td><a href="WareHouse/Matchy_Match_THUNLP_20230825101854" target="_blank" rel="noopener noreferrer">Matchy_Match</a></td>
    <td><img src="misc/memory_card_game.png" width="200px"></td>
    <td>Perfect</td>
    <td>GPT3.5</td>
  </tr>
  <tr>
    <td><a href="WareHouse/PasswordGenerator_THUNLP_20230825072337" target="_blank" rel="noopener noreferrer">Password Generator</a></td>
    <td><img src="misc/password_generator.png" width="200px"></td>
    <td>Perfect</td>
    <td>GPT3.5</td>
  </tr>
  <tr>
    <td><a href="WareHouse/ToDo_THUNLP_20230825072331" target="_blank" rel="noopener noreferrer">Todo</a></td>
    <td><img src="misc/todo.png" width="200px"></td>
    <td>Perfect</td>
    <td>GPT3.5</td>
  </tr>
  <tr>
    <td><a href="WareHouse/ExpenseEase_THUNLP_20230825093604" target="_blank" rel="noopener noreferrer">Expensechart</a></td>
    <td><img src="misc/expense_visualizer.png" width="200px"></td>
    <td>Perfect</td>
    <td>GPT3.5</td>
  </tr>
  <tr>
    <td><a href="WareHouse/2048_THUNLP_20230822144615" target="_blank" rel="noopener noreferrer">2048 Game</a></td>
    <td><img src="misc/2048.png" width="200px"></td>
    <td>Perfect</td>
    <td>GPT3.5</td>
  </tr>
  <tr>
    <td><a href="WareHouse/WordExpand_THUNLP_20230825093623" target="_blank" rel="noopener noreferrer">WordExpand</a></td>
    <td><img src="misc/vocab.png" width="200px"></td>
    <td>Perfect</td>
    <td>GPT3.5</td>
  </tr>
  <tr>
    <td><a href="WareHouse/Fish_Tycoon_THUNLP_20230825093543" target="_blank" rel="noopener noreferrer">Fish Tycoon</a></td>
    <td><img src="misc/aquarium.png" width="200px"></td>
    <td>Biased</td>
    <td>GPT3.5</td>
  </tr>
  <tr>
    <td><a href="WareHouse/DigitalClock_THUNLP_20230825093556" target="_blank" rel="noopener noreferrer">Digital Clock</a></td>
    <td><img src="misc/clock.png" width="200px"></td>
    <td>Perfect</td>
    <td>GPT3.5</td>
  </tr>
  <tr>
    <td><a href="WareHouse/CurrencyWiz_THUNLP_20230825101851" target="_blank" rel="noopener noreferrer">CurrencyWiz</a></td>
    <td><img src="misc/currency_converter.png" width="200px"></td>
    <td>Perfect</td>
    <td>GPT3.5</td>
  </tr>
  <tr>
    <td><a href="WareHouse/DesignDream_THUNLP_20230825072340" target="_blank" rel="noopener noreferrer">Design Dream</a></td>
    <td><img src="misc/home_design.png" width="200px"></td>
    <td>Biased</td>
    <td>GPT3.5</td>
  </tr>
  <tr>
    <td><a href="WareHouse/DiceRollingSimulator_THUNLP_20230825072338" target="_blank" rel="noopener noreferrer">DiceRollingSimulator</a></td>
    <td><img src="misc/dice.png" width="200px"></td>
    <td>Perfect</td>
    <td>GPT3.5</td>
  </tr>
  <tr>
    <td rowspan="6"><a href="https://github.com/NA-Wen" target="_blank" rel="noopener noreferrer">https://github.com/NA-Wen</a></td>
    <td><a href="WareHouse/md2html_THUNLP_md2html" target="_blank" rel="noopener noreferrer">md2html</a></td>
    <td><img src="misc/markdown2html.png" width="200px"></td>
    <td>Runnable</td>
    <td>GPT3.5</td>
  </tr>
  <tr>
    <td><a href="WareHouse/Gomoku_THUNLP_20230625201030" target="_blank" rel="noopener noreferrer">A Gomoku Game with assets generated by Agent</a></td>
    <td><img src="misc/gomoku_art.png" width="200px"></td>
    <td>Perfect</td>
    <td>GPT4</td>
  </tr>
  <tr>
    <td><a href="WareHouse/mspaint_THUNLP_20230821204606" target="_blank" rel="noopener noreferrer">MsPaint</a></td>
    <td><img src="misc/mspaint.png" width="200px"></td>
    <td>Runnable</td>
    <td>GPT3.5</td>
  </tr>
  <tr>
    <td><a href="WareHouse/ImgEditor_THUNLP_20230824142740" target="_blank" rel="noopener noreferrer">Image Editor</a></td>
    <td><img src="misc/image_editor.png" width="200px"></td>
    <td>Perfect</td>
    <td>GPT3.5</td>
  </tr>
  <tr>
    <td><a href="WareHouse/ArtCanvas_THUNLP_20230825093558" target="_blank" rel="noopener noreferrer">ArtCanvas</a></td>
    <td><img src="misc/paint.png" width="200px"></td>
    <td>Perfect</td>
    <td>GPT3.5</td>
  </tr>
  <tr>
    <td><a href="WareHouse/TicTacToe_THUNLP_20230825093547" target="_blank" rel="noopener noreferrer">TicTacToe</a></td>
    <td><img src="misc/tictactoe.png" width="200px"></td>
    <td>Runnable</td>
    <td>GPT3.5</td>
  </tr>
  <tr>
    <td rowspan="5"><a href="https://github.com/lijiahao2022" target="_blank" rel="noopener noreferrer">https://github.com/lijiahao2022</a></td>
    <td><a href="WareHouse/musicplayer_THUNLP_20230824113404" target="_blank" rel="noopener noreferrer">Music Player</a></td>
    <td><img src="misc/music_player.png" width="200px"></td>
    <td>Perfect</td>
    <td>GPT4</td>
  </tr>
  <tr>
    <td><a href="WareHouse/Typing_THUNLP_20230824105537" target="_blank" rel="noopener noreferrer">Typing Test</a></td>
    <td><img src="misc/typing_test.png" width="200px"></td>
    <td>Perfect</td>
    <td>GPT3.5</td>
  </tr>
  <tr>
    <td><a href="WareHouse/videoplayer_THUNLP_20230824233151" target="_blank" rel="noopener noreferrer">Video Player</a></td>
    <td><img src="misc/video_player.png" width="200px"></td>
    <td>Runnable</td>
    <td>GPT3.5</td>
  </tr>
  <tr>
    <td><a href="WareHouse/timer_THUNLP_20230823091709" target="_blank" rel="noopener noreferrer">Timer</a></td>
    <td><img src="misc/timer.png" width="200px"></td>
    <td>Perfect</td>
    <td>GPT3.5</td>
  </tr>
  <tr>
    <td><a href="WareHouse/BookBreeze_THUNLP_20230825072339" target="_blank" rel="noopener noreferrer">BookBreeze</a></td>
    <td><img src="misc/ebook_reader.png" width="200px"></td>
    <td>Runnable</td>
    <td>GPT3.5</td>
  </tr>
</tbody>
</table>

## 📑 引用

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

## ⚖️ ライセンス

- ChatDev の目的は研究目的のみです。
- ソースコードは Apache 2.0 でライセンスされています。
- データセットのライセンスは CC BY NC 4.0 であり、非商用目的でのみ使用できる。これらのデータセットを使用して学習されたモデルは、研究以外の目的で使用されないようご注意ください。
