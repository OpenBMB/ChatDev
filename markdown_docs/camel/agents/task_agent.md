## ClassDef TaskSpecifyAgent
**TaskSpecifyAgent**: TaskSpecifyAgent 的功能是通过提示用户提供更多细节来指定给定的任务提示。

**属性**:
- **DEFAULT_WORD_LIMIT (int)**: 任务提示的默认字数限制。
- **task_specify_prompt (TextPrompt)**: 指定任务的提示。

**代码描述**:
TaskSpecifyAgent 类继承自 ChatAgent 类，用于生成更具体的任务描述。它通过接收模型类型、任务类型、模型配置、任务指定提示以及字数限制作为参数来初始化。如果未提供任务指定提示，则会根据任务类型生成默认的任务指定提示模板，并根据字数限制进行格式化。此外，该类还提供了一个 step 方法，用于根据原始任务提示和可选的元数据字典来生成更详细的任务提示。

在初始化过程中，如果未提供模型配置，则会使用默认的 ChatGPTConfig 配置，并设置系统消息以初始化 ChatAgent 基类。系统消息包括角色名称（"Task Specifier"）、角色类型（RoleType.ASSISTANT）和内容（"You can make a task more specific."），用于在聊天界面中指示该代理的角色和目的。

step 方法接收原始任务提示和可选的元数据字典作为参数，重置代理到其初始状态，并使用提供的信息来格式化任务指定提示。如果提供了元数据字典，将使用该字典中的信息进一步格式化任务指定提示。然后，该方法生成一个用户聊天消息，调用 ChatAgent 的 step 方法来处理该消息，并生成指定的任务提示。如果在处理过程中遇到任何问题（例如，未能生成响应或任务指定过程被终止），则会抛出运行时错误。

**注意**:
- 使用 TaskSpecifyAgent 时，需要确保提供有效的任务类型和模型配置。
- 默认字数限制为 50，但可以根据需要进行调整。
- 如果提供了元数据字典，它将用于进一步定制任务指定提示。

**输出示例**:
假设原始任务提示为 "编写一个聊天机器人"，且没有提供元数据字典，TaskSpecifyAgent 可能会返回一个 TextPrompt，内容为 "请提供更多细节，以便更具体地描述您想要编写的聊天机器人任务。字数限制为50。"。这个输出示例展示了如何通过 TaskSpecifyAgent 使任务提示更加具体和详细。
### FunctionDef __init__(self, model, task_type, model_config, task_specify_prompt, word_limit)
**__init__**: 此函数的功能是初始化 TaskSpecifyAgent 类的实例。

**参数**:
- model: 可选参数，指定模型的类型，类型为 ModelType 或 None，默认值为 None。
- task_type: 指定任务的类型，类型为 TaskType，其默认值为 TaskType.AI_SOCIETY。
- model_config: 可选参数，指定模型配置，类型为任意类型，默认值为 None。
- task_specify_prompt: 可选参数，指定任务指定提示，类型为字符串或 TextPrompt，默认值为 None。
- word_limit: 指定字数限制，类型为整型，默认值为 DEFAULT_WORD_LIMIT。

**代码描述**:
此函数首先检查 `task_specify_prompt` 是否为 None。如果是，它会使用 `PromptTemplateGenerator` 类的 `get_task_specify_prompt` 方法根据 `task_type` 获取任务指定提示模板，并使用 `word_limit` 格式化这个模板，然后将结果赋值给 `self.task_specify_prompt`。如果 `task_specify_prompt` 不为 None，则直接将其赋值给 `self.task_specify_prompt`。

接下来，如果 `model_config` 为 None，则使用 `ChatGPTConfig` 类创建一个默认的模型配置，其中温度参数设置为 1.0。

然后，创建一个 `SystemMessage` 实例，指定角色名称为 "Task Specifier"，角色类型为 `RoleType.ASSISTANT`，并设置内容为 "You can make a task more specific."。这个系统消息用于初始化 TaskSpecifyAgent 类的基类。

最后，调用基类的 `__init__` 方法，传入系统消息、模型和模型配置。

**注意**:
- 在使用此函数时，应确保传入的 `task_type` 是有效的 `TaskType` 枚举值之一。
- 如果需要自定义模型配置，可以通过 `model_config` 参数传入自定义的配置。如果不传入，将使用默认配置。
- `task_specify_prompt` 参数允许开发者自定义任务指定提示。如果不提供，将根据任务类型自动生成提示。
- 此函数在初始化 TaskSpecifyAgent 实例时自动调用，用于设置任务指定代理的基本属性和行为。
***
### FunctionDef step(self, original_task_prompt, meta_dict)
**step**: 此函数的功能是通过提供更多细节来指定给定的任务提示。

**参数**:
- `original_task_prompt`: 原始任务提示，可以是字符串或TextPrompt对象。
- `meta_dict`: 包含在提示中包含的附加信息的字典，可选参数，默认为None。

**代码描述**: `step` 函数首先调用 `reset` 方法重置任务指定代理到其初始状态，然后使用 `task_specify_prompt` 属性格式化原始任务提示。如果提供了 `meta_dict`，则使用其内容进一步格式化任务提示。接着，创建一个 `UserChatMessage` 实例，模拟任务指定者发出的聊天消息，并将其传递给父类的 `step` 方法以获取指定任务的响应。如果响应中没有消息或任务指定过程被终止，则抛出运行时错误。最后，从响应中提取指定的任务消息，并将其内容封装在 `TextPrompt` 对象中返回。

**注意**:
- 在调用此函数之前，确保 `original_task_prompt` 已正确初始化，且其内容符合任务指定的要求。
- `meta_dict` 是可选的，但在需要传递额外信息以丰富任务提示时，合理使用此参数可以提高任务指定的准确性和相关性。
- 此函数可能抛出运行时错误，表示任务指定失败，调用者应当处理这些异常情况。

**输出示例**: 假设 `original_task_prompt` 为 "请描述天气情况"，`meta_dict` 包含 `{"location": "北京"}`，则此函数可能返回一个 `TextPrompt` 对象，其内容为 "请描述北京的天气情况"。
***
## ClassDef TaskPlannerAgent
**TaskPlannerAgent**: TaskPlannerAgent 类的功能是基于输入的任务提示，帮助将任务划分为子任务。

**属性**:
- **task_planner_prompt (TextPrompt)**: 用于指导代理将任务划分为子任务的提示。

**代码描述**:
TaskPlannerAgent 类继承自 ChatAgent 类，专门用于处理任务规划的场景。它通过接收一个任务提示，利用内部模型将该任务细化为更具体的子任务。该类在初始化时，会设置一个用于任务规划的提示模板，并根据输入的任务提示动态生成具体的任务规划提示。此外，TaskPlannerAgent 类还会初始化一个系统消息，用于定义代理在任务规划过程中的角色和行为。

在执行任务规划时，TaskPlannerAgent 类的 `step` 方法会被调用。该方法接收一个任务提示（可以是字符串或 TextPrompt 对象），并根据这个提示生成子任务。这一过程涉及到调用父类 ChatAgent 的 `step` 方法来处理实际的任务规划逻辑，包括生成子任务的提示、处理任务规划的终止逻辑等。

**注意**:
- 在使用 TaskPlannerAgent 类时，需要确保提供有效的任务提示。
- TaskPlannerAgent 类依赖于其父类 ChatAgent 的实现，因此在使用时应确保 ChatAgent 类及其依赖的模型和配置正确设置且可用。
- 该类的 `step` 方法可能会抛出异常，例如在未能生成子任务提示或任务规划失败时。

**输出示例**:
假设输入的任务提示为“组织一次团队建设活动”，TaskPlannerAgent 类的 `step` 方法可能会返回一个 TextPrompt 对象，内容为“1. 确定活动日期和时间；2. 选择活动地点；3. 准备活动所需物资；4. 发送活动邀请函。”，这表示将原始任务细化为了四个具体的子任务。
### FunctionDef __init__(self, model, model_config)
**__init__**: 该函数用于初始化TaskPlannerAgent类的实例。

**参数**:
- model: 可选参数，用于指定模型的类型，其类型为ModelType或None。ModelType是一个枚举类，定义了不同类型的模型标识符。
- model_config: 用于指定模型配置的参数，其类型为任意类型。该参数允许用户为模型提供额外的配置信息。

**代码描述**:
该初始化函数首先创建了一个TextPrompt实例，用于生成任务规划的文本提示。这个文本提示的内容是"Divide this task into subtasks: {task}. Be concise."，旨在引导用户或系统将一个任务分解为更小的子任务，并要求描述要简洁。

接着，函数创建了一个SystemMessage实例，用于定义系统消息。这个系统消息包含角色名称（"Task Planner"），角色类型（RoleType.ASSISTANT），以及消息内容（"You are a helpful task planner."）。RoleType是一个枚举类，其中定义了系统中不同角色的类型，如助理、用户等。在这里，RoleType.ASSISTANT表示该系统消息是由助理角色发送的。

最后，通过调用父类的__init__方法，将系统消息、模型类型和模型配置传递给父类进行进一步的初始化。这一步骤确保了TaskPlannerAgent类的实例能够正确地继承并使用父类提供的功能。

**注意**:
- 在使用TaskPlannerAgent类时，开发者应当注意model参数和model_config参数的正确使用。model参数允许指定使用的模型类型，而model_config参数则提供了一种方式来为模型提供额外的配置信息。这两个参数共同决定了任务规划代理的行为和性能。
- TextPrompt和SystemMessage类的使用展示了如何在任务规划代理中生成和管理文本提示以及系统消息。这两个类的正确使用对于实现高效、准确的任务规划至关重要。
- 在初始化TaskPlannerAgent实例时，应确保提供的角色类型与系统设计一致。RoleType.ASSISTANT在此处用于标识任务规划代理的角色类型，开发者在扩展或修改代码时应保持角色类型的准确性。
***
### FunctionDef step(self, task_prompt)
**step**: 此函数的功能是基于输入的任务提示生成子任务。

**参数**:
- `task_prompt (Union[str, TextPrompt])`: 用于被分解成子任务的任务提示。

**代码描述**: `step` 函数首先调用 `reset` 方法重置代理到其初始状态，然后使用 `task_planner_prompt` 属性格式化任务提示。此过程中，`task_planner_prompt` 可能包含用于生成子任务的模板。接着，创建一个 `UserChatMessage` 实例，其中 `role_name` 设置为 `"Task Planner"`，并将格式化后的任务提示作为消息内容。此消息随后被传递给 `super().step` 方法，以生成子任务。如果 `super().step` 方法返回的响应中没有消息 (`msgs` 为 `None`)，或者任务规划被标记为已终止 (`terminated` 为 `True`)，则分别抛出运行时错误。最后，从响应中提取第一条消息的内容，并将其封装在 `TextPrompt` 对象中返回。

**注意**:
- 在调用此函数之前，确保 `task_prompt` 参数已经正确初始化，且能够代表一个有效的任务提示。
- 此函数依赖于 `UserChatMessage` 类和 `TextPrompt` 类的正确实现。`UserChatMessage` 用于创建代表任务规划者发送的消息，而 `TextPrompt` 用于封装和返回子任务提示。
- 函数中的错误处理确保了在子任务生成过程中遇到的任何异常情况都能被及时识别和报告。

**输出示例**: 假设输入的 `task_prompt` 为 `"设计一个聊天机器人"`，并且此任务被成功分解为子任务 `"确定机器人的功能范围"`。那么，函数将返回一个 `TextPrompt` 对象，其内容为 `"确定机器人的功能范围"`。
***
