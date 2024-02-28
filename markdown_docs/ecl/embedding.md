## ClassDef OpenAIEmbedding
**OpenAIEmbedding**: OpenAIEmbedding类的功能是获取文本或代码的嵌入表示。

**属性**:
- code_prompt_tokens: 用于记录获取代码嵌入时OpenAI API使用的提示令牌数。
- text_prompt_tokens: 用于记录获取文本嵌入时OpenAI API使用的提示令牌数。
- code_total_tokens: 用于记录获取代码嵌入时OpenAI API使用的总令牌数。
- text_total_tokens: 用于记录获取文本嵌入时OpenAI API使用的总令牌数。
- prompt_tokens: 用于记录所有嵌入获取操作中OpenAI API使用的提示令牌总数。
- total_tokens: 用于记录所有嵌入获取操作中OpenAI API使用的总令牌数。

**代码描述**:
OpenAIEmbedding类提供了两个主要方法：`get_text_embedding`和`get_code_embedding`，用于分别获取文本和代码的嵌入表示。这些方法通过OpenAI API发送请求，获取输入文本或代码的嵌入向量，并记录API使用的令牌数。如果输入文本或代码长度超过8191字符，它们会被截断以符合API的限制。这些方法使用了重试机制，以指数退避的方式等待重试，最多尝试10次，以增加请求成功的机会。

在项目中，`OpenAIEmbedding`类被`Experience`和`MemoryBase`类实例化用于获取嵌入表示。在`Experience`类中，它被用来初始化`embedding_method`属性，以便后续获取图中节点的文本或代码嵌入。在`MemoryBase`类中，根据配置文件决定是否使用`OpenAIEmbedding`作为嵌入方法，如果使用，则实例化并赋值给`embedding_method`属性，用于后续的文本或代码检索任务。

**注意**:
- 使用这个类之前，需要确保已经设置了`OPENAI_API_KEY`和`BASE_URL`（如果有的话），以便能够通过OpenAI API进行请求。
- 文本或代码的长度不能超过8191字符，否则会被自动截断。
- API请求可能会失败，因此使用了重试机制来增加成功的机会。调用者应当准备处理可能的异常。

**输出示例**:
调用`get_text_embedding`或`get_code_embedding`方法将返回一个嵌入向量，例如：
```python
[0.012, 0.234, ..., 0.789]  # 假设的嵌入向量示例
```
### FunctionDef __init__(self)
**__init__**: 该函数用于初始化OpenAIEmbedding类的实例。

**参数**:
- **params**: 一个接收任意数量关键字参数的字典。这些参数用于配置实例，但在当前代码实现中未直接使用。

**代码描述**:
`__init__` 函数是OpenAIEmbedding类的构造函数，负责初始化类实例时的基本设置。在这个函数中，主要完成了以下几个实例变量的初始化：

- `self.code_prompt_tokens`：初始化为0，用于记录代码提示的token数量。
- `self.text_prompt_tokens`：初始化为0，用于记录文本提示的token数量。
- `self.code_total_tokens`：初始化为0，用于记录代码总的token数量。
- `self.text_total_tokens`：初始化为0，用于记录文本总的token数量。
- `self.prompt_tokens`：初始化为0，这个变量可能用于记录所有类型提示的总token数量。
- `self.total_tokens`：初始化为0，这个变量可能用于记录所有类型文本的总token数量。

这些变量的初始化为0是为了在实例创建时提供一个清晰的起点，确保在后续的操作中，这些变量可以被正确地更新和使用。

**注意**:
- 尽管`__init__`函数接收`**params`作为参数，当前的实现中并没有使用这些额外的参数。这意味着，如果在实例化OpenAIEmbedding类时传入了额外的关键字参数，这些参数将不会被直接用于初始化过程中。开发者在使用时需要注意这一点，确保不依赖于未被使用的参数进行逻辑判断或配置。
- 初始化的变量主要与token计数相关，这暗示了OpenAIEmbedding类可能与文本或代码的处理、分析有关，特别是在处理自然语言处理或代码生成任务时对token的数量进行追踪。开发者在使用该类时，应当注意这些变量的更新和使用，以确保正确地反映了处理过程中的状态。
***
### FunctionDef get_text_embedding(self, text)
**get_text_embedding**: 该函数的功能是获取文本的嵌入向量。

**参数**:
- text: 需要获取嵌入向量的文本，数据类型为字符串。

**代码描述**:
`get_text_embedding` 函数首先检查是否设置了 `BASE_URL`。如果设置了，它将使用该 URL 和 `OPENAI_API_KEY` 创建一个 `openai.OpenAI` 客户端实例；如果没有设置，它将仅使用 `OPENAI_API_KEY` 创建客户端实例。接着，函数会检查输入文本的长度是否超过8191个字符，如果超过，它将截断文本以符合限制。之后，使用 `client.embeddings.create` 方法调用 OpenAI 的 API，传入文本和模型 "text-embedding-ada-002"，获取文本的嵌入向量。函数还会调用 `log_and_print_online` 函数，打印并记录模型使用的信息，包括模型名称、提示符使用的令牌数和总令牌数。最后，函数更新类实例的相关属性，记录提示符令牌和总令牌的使用情况，并返回文本的嵌入向量。

**注意**:
- 输入文本的长度不能超过8191个字符，如果超过，文本将被截断。
- 需要确保 `OPENAI_API_KEY` 和 `BASE_URL`（如果有）已正确设置。
- 此函数会更新类实例的 `text_prompt_tokens`、`text_total_tokens`、`prompt_tokens` 和 `total_tokens` 属性，记录令牌使用情况。
- 使用此函数前，确保已经正确配置了日志记录系统，以便能够记录和打印信息。

**输出示例**:
调用 `get_text_embedding` 函数可能返回一个浮点数列表，代表文本的嵌入向量，例如：
```python
[0.01234, -0.5678, 0.91011, ..., 0.12345]
```
这个列表的长度和具体值取决于模型的输出。
***
### FunctionDef get_code_embedding(self, code)
**get_code_embedding**: 此函数的功能是获取代码片段的嵌入向量。

**参数**:
- code: 字符串类型，表示需要获取嵌入向量的代码片段。

**代码描述**:
`get_code_embedding`函数首先检查是否设置了`BASE_URL`。如果设置了，它会使用`BASE_URL`和`OPENAI_API_KEY`创建一个`openai.OpenAI`客户端实例；如果没有设置，它将仅使用`OPENAI_API_KEY`创建客户端。接下来，函数会检查输入的代码长度。如果代码长度为0，它会将代码设置为一个井号("#")；如果代码长度超过8191个字符，它会截取前8190个字符。之后，函数使用`client.embeddings.create`方法，传入代码和模型名称"text-embedding-ada-002"，来创建代码的嵌入向量。获取到响应后，它从响应中提取出嵌入向量，并使用`log_and_print_online`函数打印模型信息和使用的令牌数量。最后，函数更新类实例中关于令牌使用情况的统计信息，并返回提取的嵌入向量。

**注意**:
- 输入的代码片段应该是有效的代码，以确保生成的嵌入向量有意义。
- 由于OpenAI API的限制，代码长度不能超过8191个字符。如果超过这个长度，代码会被截断。
- 需要确保`OPENAI_API_KEY`是有效的，并且有足够的权限来调用嵌入向量生成接口。
- 此函数会增加类实例中关于OpenAI API令牌使用情况的统计信息，这对于监控API使用情况很有帮助。

**输出示例**:
调用`get_code_embedding`函数可能会返回如下形式的嵌入向量（示例中的数字是随机生成的，实际输出会根据输入的代码片段变化）:
```python
[0.01234, -0.05678, 0.12345, ..., 0.67890]
```
这个嵌入向量是一个浮点数列表，代表输入代码片段在模型空间中的位置。
***
