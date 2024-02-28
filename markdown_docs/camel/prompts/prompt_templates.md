## ClassDef PromptTemplateGenerator
**PromptTemplateGenerator**: 该类的功能是为不同任务类型生成提示模板。

**属性**:
- `task_prompt_template_dict`: 一个可选的字典，包含每种任务类型的提示模板。如果未提供，则默认使用一个空字典。

**代码描述**:
`PromptTemplateGenerator` 类提供了一种机制，用于根据任务类型和关键字生成文本提示。这个类主要用于生成和任务相关的提示，以便在与用户的交互中使用。它通过几个方法实现了这一功能：

1. `__init__` 方法接受一个可选的任务提示模板字典。如果未提供，则使用一个空的任务提示模板字典作为默认值。
2. `get_prompt_from_key` 方法根据提供的任务类型和关键字生成文本提示。如果无法使用指定的任务类型和关键字生成提示，则会抛出 `KeyError` 异常。
3. `get_system_prompt` 方法生成系统角色的文本提示，使用指定的任务类型和角色类型。如果无法生成提示，将发出警告并返回一个默认提示。
4. `get_generate_tasks_prompt` 方法获取给定任务类型的生成任务提示。
5. `get_task_specify_prompt` 方法获取给定任务类型的指定任务提示。

在项目中，`PromptTemplateGenerator` 被多个对象调用，以生成特定场景下的提示。例如，在 `TaskSpecifyAgent` 的初始化中，使用 `get_task_specify_prompt` 方法来获取指定任务类型的任务指定提示。在 `SystemMessageGenerator` 的初始化中，使用 `get_system_prompt` 方法来为不同的角色类型生成系统提示。这些调用表明 `PromptTemplateGenerator` 在项目中扮演着生成任务和系统提示的核心角色，以便在与用户的交互中使用。

**注意**:
- 使用 `PromptTemplateGenerator` 时，需要确保提供的任务类型和关键字在 `task_prompt_template_dict` 中有对应的条目，否则会抛出 `KeyError` 异常。
- 在生成系统提示时，如果无法找到特定的提示模板，将发出警告并使用默认提示。

**输出示例**:
假设有一个任务类型为 `TaskType.AI_SOCIETY` 和关键字为 `generate_tasks` 的调用，`get_generate_tasks_prompt` 方法可能返回如下文本提示：
```
"请生成10个关于人工智能社会影响的任务。"
```
### FunctionDef __init__(self, task_prompt_template_dict)
**__init__**: 此函数的功能是初始化PromptTemplateGenerator实例。

**参数**:
- task_prompt_template_dict: 可选参数，类型为TaskPromptTemplateDict或None，默认值为None。用于指定任务提示模板字典。

**代码描述**:
此构造函数用于创建PromptTemplateGenerator类的实例。它接受一个可选参数task_prompt_template_dict，该参数允许用户提供一个TaskPromptTemplateDict实例或None。如果用户未提供TaskPromptTemplateDict实例（即参数为None），构造函数将创建一个新的TaskPromptTemplateDict实例并将其赋值给实例变量self.task_prompt_template_dict。这个过程确保了PromptTemplateGenerator实例总是有一个有效的任务提示模板字典可用。

TaskPromptTemplateDict是一个特殊的字典，用于将不同的任务类型映射到其对应的文本提示模板字典。这个映射关系在TaskPromptTemplateDict的初始化过程中通过预定义的任务类型和提示模板字典实例被自动填充。因此，通过提供TaskPromptTemplateDict实例给PromptTemplateGenerator，可以根据不同的任务类型快速获取到相应的提示模板，进而生成具体的任务提示。

**注意**:
- 在使用PromptTemplateGenerator时，应当注意task_prompt_template_dict参数的提供。如果有特定的任务提示模板需求，可以通过创建TaskPromptTemplateDict实例并预先填充所需的映射关系，然后将此实例传递给PromptTemplateGenerator。这样可以确保生成的任务提示符合特定需求。
- TaskPromptTemplateDict类是基于Python字典实现的，因此它继承了字典的所有属性和方法。在扩展或修改任务类型与提示模板的映射关系时，可以利用这些字典操作来进行。
- 正确使用TaskPromptTemplateDict对于确保任务提示的准确性和一致性至关重要。在实际应用中，应当根据项目需求对TaskPromptTemplateDict进行适当的扩展或修改。
***
### FunctionDef get_prompt_from_key(self, task_type, key)
**get_prompt_from_key**: 此函数的功能是根据指定的任务类型和键生成文本提示。

**参数**:
- task_type (TaskType): 任务的类型。
- key (Any): 用于生成提示的键。

**代码描述**:
`get_prompt_from_key` 函数是 `PromptTemplateGenerator` 类的一个方法，它使用指定的任务类型（`task_type`）和键（`key`）来生成一个文本提示（`TextPrompt`）。这个方法首先尝试从 `task_prompt_template_dict` 字典中，使用 `task_type` 和 `key` 作为索引来获取相应的文本提示。如果成功，该文本提示将被返回。如果指定的 `task_type` 和 `key` 无法在字典中找到对应的文本提示，函数将抛出一个 `KeyError` 异常，提示无法使用指定的 `task_type` 和 `key` 生成提示模板。

此方法在项目中的作用是根据不同的任务类型和上下文（通过 `key` 表示）动态生成相应的文本提示，以适应不同的任务需求和场景。例如，它可以用于生成系统提示、任务生成提示或任务指定提示等。

**注意**:
- 使用此函数时，需要确保传入的 `task_type` 是有效的 `TaskType` 枚举值之一。
- 传入的 `key` 应该是能够在 `task_prompt_template_dict` 字典中找到对应值的有效键。
- 如果函数抛出 `KeyError` 异常，开发者需要检查传入的 `task_type` 和 `key` 是否正确，以及 `task_prompt_template_dict` 字典是否已正确初始化并包含了所有必要的键值对。

**输出示例**:
假设 `task_prompt_template_dict` 字典中包含一个键为 `TaskType.CODE` 和 `key` 为 `"generate_tasks"` 的条目，其值为 `"请生成编程相关的任务"`。当调用 `get_prompt_from_key(TaskType.CODE, "generate_tasks")` 时，函数将返回一个 `TextPrompt` 实例，其内容为 `"请生成编程相关的任务"`。
***
### FunctionDef get_system_prompt(self, task_type, role_type)
**get_system_prompt**: 此函数的功能是根据指定的任务类型和角色类型生成系统文本提示。

**参数**:
- task_type (TaskType): 指定的任务类型。
- role_type (RoleType): 指定的角色类型，可以是“USER”或“ASSISTANT”。

**代码描述**:
`get_system_prompt` 函数是 `PromptTemplateGenerator` 类的一个方法，旨在根据给定的任务类型（`task_type`）和角色类型（`role_type`）生成相应的文本提示（`TextPrompt`）。函数首先尝试调用 `get_prompt_from_key` 方法，使用 `task_type` 和 `role_type` 作为参数来获取文本提示。如果成功，该文本提示将被返回。如果在尝试获取文本提示时遇到 `KeyError` 异常，即无法使用指定的 `task_type` 和 `role_type` 生成提示，函数将发出警告，并将文本提示设置为默认值 "You are a helpful assistant."，然后返回这个默认文本提示。

此函数在项目中的作用是动态生成适应不同任务和角色需求的系统提示，以便在不同的交互场景中使用。例如，在系统消息生成器（`SystemMessageGenerator`）初始化过程中，可以根据不同的任务类型和角色类型调用此函数来生成相应的系统提示模板。

**注意**:
- 开发者在使用此函数时，需要确保传入的 `task_type` 和 `role_type` 是有效的枚举值，且已在项目中定义。
- 如果在 `get_prompt_from_key` 方法中找不到对应的文本提示，将会发出警告并返回默认提示。开发者应注意检查是否正确设置了任务类型和角色类型的映射关系。

**输出示例**:
假设调用 `get_system_prompt(TaskType.CODE, RoleType.ASSISTANT)`，并且在内部映射中存在对应的文本提示模板，则可能返回一个 `TextPrompt` 实例，内容为 "Please provide assistance with coding tasks."。如果没有找到对应的模板，则返回的 `TextPrompt` 实例内容为 "You are a helpful assistant."。
***
### FunctionDef get_generate_tasks_prompt(self, task_type)
**get_generate_tasks_prompt**: 此函数的功能是根据给定的任务类型获取生成任务的文本提示。

**参数**:
- task_type (TaskType): 指定的任务类型。

**代码描述**:
`get_generate_tasks_prompt` 函数是 `PromptTemplateGenerator` 类的一个方法，它接受一个 `TaskType` 枚举值作为参数，用于指定需要生成文本提示的任务类型。该函数通过调用 `get_prompt_from_key` 方法，并将 `task_type` 和固定的键 `"generate_tasks"` 作为参数传递，来获取相应的文本提示。`get_prompt_from_key` 方法负责根据提供的任务类型和键从预定义的文本提示模板字典中查找并返回相应的文本提示。如果找到匹配的文本提示，该文本提示将被封装为一个 `TextPrompt` 实例并返回；如果没有找到匹配项，将抛出 `KeyError` 异常。

此函数的主要作用是动态生成针对不同任务类型的文本提示，以便在项目中根据不同的任务需求生成相应的任务提示信息。例如，在生成人工智能社会相关任务或编码任务时，可以通过传递相应的 `TaskType` 枚举值（如 `TaskType.AI_SOCIETY` 或 `TaskType.CODE`）来获取特定类型的任务生成提示。

**注意**:
- 使用此函数时，必须确保传入的 `task_type` 参数是有效的 `TaskType` 枚举值之一。
- 如果传入的任务类型在文本提示模板字典中没有对应的条目，函数将抛出 `KeyError` 异常，因此在使用时需要确保相关的文本提示模板已经被正确定义和初始化。

**输出示例**:
假设文本提示模板字典中包含了一个针对编码任务的条目，其键为 `TaskType.CODE` 和 `"generate_tasks"`，值为 `"请生成编程相关的任务"`。当调用 `get_generate_tasks_prompt(TaskType.CODE)` 时，函数将返回一个 `TextPrompt` 实例，其内容为 `"请生成编程相关的任务"`。

在项目中，此函数被用于不同的任务提示生成器中，如 `AISocietyTaskPromptGenerator` 和 `CodeTaskPromptGenerator`，它们分别在初始化时调用此函数，传入相应的 `TaskType` 枚举值（例如 `TaskType.AI_SOCIETY` 或 `TaskType.CODE`），以获取并设置生成特定类型任务的提示。这样，根据不同的任务类型动态生成的文本提示能够有效地指导用户或系统生成相应类型的任务。
***
### FunctionDef get_task_specify_prompt(self, task_type)
**get_task_specify_prompt**: 此函数的功能是根据给定的任务类型获取指定任务的文本提示。

**参数**:
- task_type (TaskType): 指定的任务类型。

**代码描述**: `get_task_specify_prompt` 函数是 `PromptTemplateGenerator` 类的一个方法，它接受一个 `TaskType` 枚举类型的参数 `task_type`，用于指定任务的类型。此函数通过调用 `get_prompt_from_key` 方法，并传入 `task_type` 和固定的键 `"task_specify_prompt"`，来获取与特定任务类型相关的文本提示。`get_prompt_from_key` 方法会根据提供的任务类型和键，从预定义的文本提示模板字典中检索相应的文本提示。如果找到匹配的文本提示，则返回该文本提示；如果未找到，会抛出 `KeyError` 异常。返回的文本提示是一个 `TextPrompt` 类的实例，这是一个扩展了字符串功能的类，专门用于表示文本提示，并提供了额外的属性和方法，如获取提示中的关键词集合。

**注意**:
- 在使用此函数时，需要确保传入的 `task_type` 是有效的 `TaskType` 枚举值之一。
- 此函数依赖于 `get_prompt_from_key` 方法和 `TextPrompt` 类，因此在使用前应确保相关的模板字典已正确初始化，并且包含了所有必要的键值对。
- 如果在模板字典中未找到对应的文本提示，函数将抛出 `KeyError` 异常，开发者需要检查传入的 `task_type` 和键值是否正确。

**输出示例**: 假设对于任务类型 `TaskType.CODE`，模板字典中存在键为 `"task_specify_prompt"` 的条目，其值为 `"请详细描述编程任务"`。当调用 `get_task_specify_prompt(TaskType.CODE)` 时，函数将返回一个 `TextPrompt` 实例，内容为 `"请详细描述编程任务"`。

此函数在项目中的应用场景包括但不限于初始化任务指定代理（TaskSpecifyAgent）时，根据任务类型动态生成任务指定的文本提示。这有助于创建更具体、更符合任务需求的提示信息，从而提高任务指定的准确性和用户体验。
***
