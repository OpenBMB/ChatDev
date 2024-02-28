## FunctionDef getFilesFromType(sourceDir, filetype)
**getFilesFromType**: 此函数的功能是从指定目录中递归搜索并返回所有指定文件类型的文件列表。

**参数**:
- **sourceDir**: 源目录的路径，函数将从此目录开始递归搜索文件。
- **filetype**: 需要搜索的文件类型，例如 ".txt"、".jpg" 等。

**代码描述**:
`getFilesFromType` 函数通过接收两个参数：源目录路径（`sourceDir`）和文件类型（`filetype`），来搜索并收集特定类型的文件。函数内部使用了 `os.walk` 方法来递归遍历源目录及其所有子目录。对于每个遍历到的目录，`os.walk` 会返回三个值：当前目录的路径（`root`）、当前目录下的所有目录名列表（`directories`）和当前目录下的所有文件名列表（`filenames`）。函数随后检查每个文件名是否以指定的文件类型结束（即文件扩展名匹配），如果是，则将该文件的完整路径添加到结果列表中。最终，函数返回包含所有找到的指定类型文件的完整路径列表。

**注意**:
- 确保传入的源目录路径（`sourceDir`）是有效且可访问的，否则函数可能无法正常工作。
- 文件类型参数（`filetype`）应包括点号（`.`），例如 ".txt" 而不是 "txt"，以确保正确的文件扩展名匹配。
- 此函数依赖于 `os` 模块，因此在使用前需要确保已经导入了 `os` 模块。

**输出示例**:
```python
file_list = getFilesFromType("/path/to/sourceDir", ".txt")
print(file_list)
```
可能的输出结果为：
```python
['/path/to/sourceDir/folder1/note.txt', '/path/to/sourceDir/folder2/info.txt', '/path/to/sourceDir/folder3/data.txt']
```
此输出示例展示了函数如何返回一个包含所有找到的指定类型（在此例中为 `.txt` 文件）的完整路径列表。
## FunctionDef cmd(command)
**cmd**: cmd 函数的功能是执行给定的命令行指令，并返回执行结果。

**参数**:
- `command`: 需要执行的命令行指令，类型为字符串。

**代码描述**: 此函数接收一个命令行指令作为输入参数，使用 `subprocess.run` 方法执行该指令。在执行过程中，设置 `shell=True` 允许命令通过shell来执行，`text=True` 表示将输出以文本形式返回，而 `stdout=subprocess.PIPE` 指定了标准输出的管道，这样可以捕获命令的执行结果。函数最终返回命令的执行输出。

**注意**:
- 使用此函数时，应确保传入的命令行指令是安全的，以避免安全漏洞，如命令注入攻击。
- 由于设置了 `shell=True`，在不同的操作系统中，特定的shell可能会有不同的行为，因此在跨平台使用时需要注意。
- 此函数依赖于 `subprocess` 模块，因此在使用前需要确保已经导入了该模块。

**输出示例**: 假设执行命令 `cmd("echo Hello World")`，函数将打印出 `>> echo Hello World` 并返回 `Hello World\n`。

在项目中，`cmd` 函数被用于执行与版本控制相关的命令，例如在 `ecl/graph.py/Node/create_from_warehouse` 和 `ecl/graph.py/Graph/create_from_warehouse` 中，它被用来执行 `git log --oneline` 和 `git reset --hard` 命令，以获取版本库的提交历史和重置到特定的提交。这表明 `cmd` 函数在项目中主要用于处理与代码仓库管理相关的任务。
## FunctionDef get_easyDict_from_filepath(path)
**get_easyDict_from_filepath**: 该函数的功能是从指定的文件路径加载配置文件，并将其转换为易于访问的字典格式。

**参数**:
- path: 字符串类型，指定配置文件的路径。

**代码描述**:
`get_easyDict_from_filepath` 函数支持从 JSON 或 YAML 格式的配置文件中读取数据。该函数首先检查文件路径的后缀，以确定文件是 JSON 格式还是 YAML 格式。如果文件是 JSON 格式，函数使用 `json.load` 方法读取文件并将其内容转换为字典；如果文件是 YAML 格式，函数则使用 `yaml.load` 方法进行相同的操作。在两种情况下，读取到的字典都会被进一步封装成 `EasyDict` 对象，这样可以通过属性访问的方式来访问字典中的值，而不是标准的字典键值对访问方式。如果路径不以 `.json` 或 `.yaml` 结尾，函数将返回 `None`。

在项目中，`get_easyDict_from_filepath` 函数被多个对象调用，用于加载配置文件并初始化各个类的配置。例如，在 `Codes` 类的 `__init__` 方法中，通过调用此函数加载 `config.yaml` 文件，以获取临时目录、主脚本等配置信息。在 `Experience` 类和 `MemoryBase` 类的初始化过程中，也通过调用此函数来加载配置，以获取经验阈值、上限值、检索参数等配置信息。这表明 `get_easyDict_from_filepath` 函数在项目中扮演着重要的角色，是实现配置管理和灵活访问配置信息的关键。

**注意**:
- 确保传入的路径正确且文件存在，否则函数可能返回 `None`。
- 当处理 YAML 文件时，需要确保 `yaml` 模块已被安装和导入。
- 使用 `EasyDict` 可以方便地通过属性访问配置项，但要注意避免与现有方法或属性名冲突。

**输出示例**:
假设 `config.yaml` 文件内容如下：
```yaml
experience:
  threshold: 0.5
  upper_limit: 10
```
调用 `get_easyDict_from_filepath("./config.yaml")` 将返回一个 `EasyDict` 对象，可以通过 `cfg.experience.threshold` 访问阈值，通过 `cfg.experience.upper_limit` 访问上限值。
## FunctionDef calc_max_token(messages, model)
**calc_max_token**: 此函数的功能是计算给定模型在处理一系列消息时，可以接受的最大完成令牌数。

**参数**:
- **messages**: 包含消息内容的字典列表，每个消息都应包含一个`content`键。
- **model**: 一个字符串，表示使用的模型名称，该名称决定了可用的最大令牌数。

**代码描述**:
`calc_max_token`函数首先将传入的消息列表（`messages`）中的每个消息内容（`message["content"]`）合并成一个单独的字符串，每个消息之间用换行符("\n")分隔。然后，它使用`encoding_for_model`函数（假设来自`tiktoken`库）来获取针对指定模型的编码器，并使用此编码器来编码合并后的字符串，以计算出其代表的令牌数量（`num_prompt_tokens`）。

为了考虑发送和接收之间可能存在的额外令牌需求，函数在计算出的令牌数量上额外加上一个固定值（`gap_between_send_receive`），默认为50个令牌。

接下来，函数定义了一个字典（`num_max_token_map`），映射了不同模型名称到它们能处理的最大令牌数。根据传入的模型名称（`model`），函数从这个映射中查找相应模型可以处理的最大令牌数（`num_max_token`）。

最后，函数计算出在考虑了输入令牌数量后，模型还能处理的最大完成令牌数（`num_max_completion_tokens`），即从模型的最大令牌容量中减去已用的令牌数量，并将这个值返回。

**注意**:
- 确保传入的`messages`参数格式正确，每个元素都应包含一个`content`键。
- 传入的模型名称需要是`num_max_token_map`中定义的模型之一，否则会导致查找失败。

**输出示例**:
假设传入的消息列表包含总共使用了100个令牌，且模型为`gpt-3.5-turbo`，则函数将返回：
```
3996
```
这表示在考虑输入令牌和发送接收间隙后，`gpt-3.5-turbo`模型还可以接受最多3996个完成令牌。
## ClassDef ModelBackend
**ModelBackend**: ModelBackend 的功能是提供不同模型后端的基类。这可能是 OpenAI API、本地大型语言模型(LLM)、单元测试的存根等。

**属性**: 由于ModelBackend是一个抽象基类(ABC)，它本身不直接定义属性，但要求继承它的子类实现特定的方法。

**代码描述**: ModelBackend 类是一个抽象基类，定义了与模型后端交互的基本框架。它通过定义一个抽象方法 `run` 来要求所有继承自该类的子类必须实现这个方法。`run` 方法的目的是执行对后端模型的查询，并且必须返回一个字典，该字典遵循 OpenAI 格式。这种设计使得不同的模型后端可以通过实现相同的接口来被透明地使用和交换，增加了代码的模块化和可重用性。

在项目中，`OpenAIModel` 类是 `ModelBackend` 的一个具体实现，它封装了对 OpenAI API 的调用。`OpenAIModel` 通过重写 `run` 方法来实现具体的逻辑，包括与 OpenAI API 的交互、处理 API 响应以及错误处理。这表明 `ModelBackend` 类的设计允许不同的后端模型以统一的方式被集成和使用，而不需要调用者关心具体的后端实现细节。

**注意**: 使用 `ModelBackend` 或其子类时，开发者需要确保实现了 `run` 方法，并且该方法能够返回一个符合预期的字典格式。对于任何继承自 `ModelBackend` 的类，如果 `run` 方法的实现没有按照约定返回一个字典，或者返回的字典格式不正确，都可能导致运行时错误。

**输出示例**: 由于 `ModelBackend` 是一个抽象类，它本身不会直接被实例化或调用。但是，继承自 `ModelBackend` 的子类（例如 `OpenAIModel`）的 `run` 方法可能会返回类似于以下的字典：

```python
{
    "choices": [
        {
            "text": "这是模型生成的文本。",
            "index": 0,
            "logprobs": null,
            "finish_reason": "length"
        }
    ],
    "usage": {
        "prompt_tokens": 10,
        "completion_tokens": 15,
        "total_tokens": 25
    }
}
```

这个返回值遵循 OpenAI API 的响应格式，其中包含了模型生成的文本、使用的令牌数量等信息。
### FunctionDef run(self)
**run**: run函数的功能是执行对后端模型的查询。

**参数**:
- *args: 可变位置参数，用于传递给函数的不定数量的参数。
- **kwargs: 可变关键字参数，用于传递给函数的不定数量的键值对参数。

**代码描述**:
run函数是ModelBackend类的一个方法，旨在执行对后端模型的查询操作。该方法接受任意数量的位置参数(*args)和关键字参数(**kwargs)，使其具有很高的灵活性和适应性。函数的返回类型被明确指定为字典(Dict[str, Any])，这意味着无论后端模型的具体实现如何，run函数都必须返回一个字典，其中包含了查询的结果。

在执行查询的过程中，如果从OpenAI API返回的值不是预期的字典格式，函数将抛出一个RuntimeError异常。这是一个重要的错误处理机制，确保了函数的健壮性和可靠性。通过这种方式，开发者可以在调用run函数时，更加安全地处理潜在的错误情况。

**注意**:
- 开发者在使用run函数时，需要注意异常处理。特别是当与OpenAI API交互时，应确保捕获并适当处理RuntimeError异常，以避免程序意外终止。
- 返回值必须遵循OpenAI格式的字典，这一点对于确保后续处理的一致性和可预测性至关重要。

**输出示例**:
```python
{
    "response": "查询结果",
    "status": "成功",
    "data": {
        "key1": "value1",
        "key2": "value2",
        ...
    }
}
```
以上示例展示了run函数可能返回的字典格式。实际的返回值将根据后端模型的具体实现和查询参数的不同而有所差异。
***
## ClassDef OpenAIModel
**OpenAIModel**: OpenAIModel 类的功能是将 OpenAI API 封装在统一的 ModelBackend 接口中。

**属性**:
- `model_type`: 模型类型，用于指定使用的 OpenAI 模型。
- `model_config_dict`: 模型配置字典，包含调用 OpenAI API 时使用的参数，如温度（temperature）、顶部概率（top_p）等。
- `prompt_tokens`: 记录发送给模型的提示令牌数量。
- `completion_tokens`: 记录模型生成的完成令牌数量。
- `total_tokens`: 记录总共使用的令牌数量。

**代码描述**:
OpenAIModel 类继承自 ModelBackend 类，提供了对 OpenAI API 的具体实现。在初始化时，该类接受模型类型和可选的模型配置字典。如果未提供模型配置字典，将使用默认配置。该类重写了 ModelBackend 的 `run` 方法，用于执行对 OpenAI API 的调用，并处理响应。

在 `run` 方法中，首先根据是否提供了 BASE_URL 来创建 OpenAI 客户端实例。然后，将消息列表转换为字符串，并使用 tiktoken 库为模型类型编码这些字符串，以计算提示令牌的数量。此外，根据模型类型，确定最大令牌数量，并据此计算最大完成令牌数量。

调用 OpenAI API 后，方法会更新 prompt_tokens、completion_tokens 和 total_tokens 属性，记录令牌使用情况。最后，`run` 方法返回 OpenAI API 的响应。

**注意**:
- 使用 OpenAIModel 时，需要确保提供有效的 OpenAI API 密钥（OPENAI_API_KEY）和模型类型（model_type）。
- 该类通过重试装饰器实现了对 API 调用的简单重试逻辑，以处理可能的暂时性错误。
- 在处理 OpenAI API 的响应时，如果响应格式不符合预期，将抛出 RuntimeError 异常。

**输出示例**:
调用 `run` 方法可能会返回如下格式的字典：

```python
{
    "choices": [
        {
            "message": {
                "content": "这是模型生成的文本。"
            }
        }
    ],
    "usage": {
        "prompt_tokens": 10,
        "completion_tokens": 15,
        "total_tokens": 25
    }
}
```

此输出示例遵循 OpenAI API 的响应格式，其中包含了模型生成的文本内容以及使用的令牌数量等信息。
### FunctionDef __init__(self, model_type, model_config_dict)
**__init__**: 该函数用于初始化OpenAIModel类的实例。

**参数**:
- `model_type`: 指定模型的类型。
- `model_config_dict`: 一个字典，用于指定模型的配置参数。默认为None。

**代码描述**:
`__init__`函数是OpenAIModel类的构造函数，负责初始化类的实例。在这个函数中，首先通过`super().__init__()`调用基类的构造函数。然后，将传入的`model_type`参数赋值给实例变量`self.model_type`，这样可以在类的其他方法中使用指定的模型类型。

对于`model_config_dict`参数，这是一个字典，用于配置模型的具体参数，如温度（temperature）、top_p值、生成文本的数量（n）、是否流式处理（stream）、频率惩罚（frequency_penalty）、存在惩罚（presence_penalty）以及logit偏置（logit_bias）。如果在初始化时没有提供`model_config_dict`（即为None），则会使用一个默认的配置字典。这个默认字典包含了一组预设的参数值，旨在为大多数情况提供一个合理的起点。

此外，`__init__`函数还初始化了三个用于跟踪令牌使用情况的变量：`self.prompt_tokens`、`self.completion_tokens`和`self.total_tokens`。这些变量分别用于记录提示部分的令牌数量、生成的完成部分的令牌数量以及总的令牌数量。这些信息对于管理和优化模型的令牌使用非常有用。

**注意**:
- 在使用OpenAIModel类时，需要注意`model_type`参数必须正确指定，因为它决定了模型的基本行为和功能。
- 虽然提供了默认的`model_config_dict`配置，但用户可以根据需要提供自定义配置以满足特定的需求或优化性能。
- 令牌使用的跟踪对于避免超出API的令牌限制非常重要，尤其是在大规模文本生成任务中。
***
### FunctionDef run(self, messages)
**run**: 此函数的功能是执行与OpenAI API的交互，发送消息并接收响应。

**参数**:
- messages: 包含要发送给OpenAI API的消息的列表，每个消息是一个字典，包含至少一个"content"键。

**代码描述**:
此函数首先检查是否设置了`BASE_URL`。如果设置了，它将使用该URL和`OPENAI_API_KEY`创建一个`openai.OpenAI`客户端实例；如果没有设置，它将仅使用`OPENAI_API_KEY`创建实例。接着，函数定义了一个重试机制，最大重试次数为5次。

函数将`messages`列表中的所有消息内容连接成一个字符串，然后使用`tiktoken.encoding_for_model`函数根据模型类型对该字符串进行编码，以计算提示令牌的数量。此外，它还计算了发送和接收消息之间的时间间隔所需的额外令牌数量，并将这些令牌数量加到提示令牌数量上。

根据模型类型，函数从一个预定义的字典中获取最大令牌数，并通过OpenAI客户端发送消息，请求模型生成完成。生成的响应包含生成的文本、使用的令牌数量等信息。

函数更新模型配置字典中的`max_tokens`键值，以反映最大完成令牌数。然后，它调用`log_and_print_online`函数记录OpenAI API的使用信息，并更新模型的提示令牌、完成令牌和总令牌计数。

最后，函数检查响应是否为字典类型，如果不是，则抛出运行时错误。如果一切正常，它将返回响应。

**注意**:
- 使用此函数时，需要确保已正确设置`OPENAI_API_KEY`和`BASE_URL`（如果有）。
- 函数内部的重试机制目前未被使用，但可以在将来需要处理网络请求失败时启用。
- 函数假设`messages`参数是正确格式的列表，其中每个元素都是包含至少一个"content"键的字典。

**输出示例**:
假设函数成功执行并从OpenAI API接收到响应，返回值可能如下所示：
```python
{
    "choices": [
        {
            "message": {
                "content": "这是生成的回复文本。"
            }
        }
    ],
    "usage": {
        "prompt_tokens": 100,
        "completion_tokens": 150,
        "total_tokens": 250
    }
}
```
此示例展示了函数返回的响应结构，其中包含生成的文本和使用的令牌数量。
***
## FunctionDef now
**now**: 此函数的功能是获取当前的本地时间，并以特定的格式返回。

**参数**: 此函数不接受任何参数。

**代码描述**: `now` 函数使用了Python的`time`模块来获取当前的本地时间，并通过`strftime`方法将时间格式化为"年月日时分秒"的形式，格式为"YYYYMMDDHHMMSS"。这种时间格式广泛用于日志记录、文件命名等需要时间戳的场景，因为它既能提供足够的时间信息，又能避免使用特殊字符，便于文件系统处理。在项目中，尽管`ecl/ecl.py`对象调用了`now`函数的具体情况没有提供，但可以推测，`now`函数可能被用于生成时间戳，以便于在不同的模块或功能中进行时间相关的操作或记录。

**注意**: 使用此函数时，需要确保系统的本地时间是准确的，因为返回的时间值直接依赖于系统时间。此外，返回的时间格式是固定的，如果需要不同的时间格式，可能需要对函数进行适当的修改或在函数调用后对返回值进行进一步的处理。

**输出示例**: 假设当前时间是2023年4月1日15时30分45秒，函数的返回值将会是"20230401153045"。
## FunctionDef log_and_print_online(content)
**log_and_print_online**: 该函数的功能是打印内容并记录日志。

**参数**:
- content: 可选参数，表示要打印和记录日志的内容。

**代码描述**:
`log_and_print_online`函数主要用于在控制台打印信息并通过`logging`模块将相同的信息记录到日志文件中。这个函数接受一个可选参数`content`，如果`content`不为`None`，则将其内容既打印到控制台，也记录到日志中。这个函数在项目中多处被调用，用于输出重要的运行时信息，以便于开发者和用户能够实时地获取程序的状态和进展，同时也便于后期的问题追踪和日志分析。

在项目中，`log_and_print_online`函数被多个对象调用，包括但不限于`memorize`、`OpenAIEmbedding`类的`get_text_embedding`和`get_code_embedding`方法、`Experience`类的多个方法以及`Graph`类的方法中。这些调用场景涵盖了从日志记录配置信息、嵌入向量获取过程的信息反馈，到图结构的构建过程和经验提取过程的关键信息输出。通过这种方式，`log_and_print_online`函数为项目提供了一个统一的信息输出和记录机制，极大地方便了信息的管理和查阅。

**注意**:
- 使用`log_and_print_online`函数时，需要确保`logging`模块已经被正确配置，包括日志级别、日志格式和输出目标等，以保证日志信息能够被正确记录。
- 考虑到`content`参数是可选的，调用此函数时应注意是否传入了有效的内容，以避免打印空信息或记录空日志。
- 在设计日志记录策略时，应合理安排日志的详细程度和记录频率，避免产生大量冗余信息，影响日志文件的管理和分析效率。
